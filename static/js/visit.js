(function () {
  const consentStep = document.getElementById("consent-step");
  const recordStep = document.getElementById("record-step");
  const consentYes = document.getElementById("consent-yes");
  const stopBtn = document.getElementById("stop-btn");
  const discardBtn = document.getElementById("discard-btn");
  const statusEl = document.getElementById("record-status");
  const transcriptEl = document.getElementById("transcript");
  const cfg = window.AIRA_VISIT || {};

  const CHUNK_MS = 6000;
  const MIN_BLOB_BYTES = 1500;

  let visitId = null;
  let recorder = null;
  let stream = null;
  let transcript = "";
  let summarizing = false;
  let recordingActive = false;
  let chunkTimer = null;
  let pendingTranscribes = 0;
  let mimeType = "";
  let fileExt = "webm";

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function pickMimeType() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
      "audio/ogg",
    ];
    for (const type of candidates) {
      if (window.MediaRecorder && MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return "";
  }

  function extensionFor(type) {
    const t = (type || "").toLowerCase();
    if (t.includes("mp4") || t.includes("m4a") || t.includes("aac")) return "mp4";
    if (t.includes("ogg") || t.includes("oga")) return "ogg";
    if (t.includes("wav")) return "wav";
    if (t.includes("mpeg") || t.includes("mp3")) return "mp3";
    return "webm";
  }

  async function readJson(res) {
    const text = await res.text();
    try {
      return text ? JSON.parse(text) : {};
    } catch {
      return { error: text || `Request failed (${res.status})` };
    }
  }

  function waitForPendingTranscribes() {
    return new Promise((resolve) => {
      const started = Date.now();
      const tick = () => {
        if (pendingTranscribes <= 0 || Date.now() - started > 20000) {
          resolve();
          return;
        }
        setTimeout(tick, 100);
      };
      tick();
    });
  }

  async function transcribe(blob) {
    if (!cfg.transcribeUrl || !blob || blob.size < MIN_BLOB_BYTES) return;
    pendingTranscribes += 1;
    const body = new FormData();
    body.append("audio", blob, `chunk.${fileExt}`);
    try {
      const res = await fetch(cfg.transcribeUrl, {
        method: "POST",
        headers: { "X-CSRFToken": cfg.csrf },
        body,
      });
      const data = await readJson(res);
      if (!res.ok) {
        // Keep recording; don't replace the transcript UI with a raw API dump.
        console.warn("Transcription chunk failed:", data.error || res.status);
        setStatus("Still recording — one chunk didn’t transcribe; keep talking.");
        return;
      }
      if (data.text) {
        transcript = `${transcript} ${data.text}`.trim();
        transcriptEl.textContent = transcript;
        setStatus("Recording — speak naturally. We’ll write it down as we go.");
      }
    } catch (err) {
      console.warn("Transcription network error:", err);
      setStatus("Couldn’t reach the transcription service. Check your connection.");
    } finally {
      pendingTranscribes -= 1;
    }
  }

  function clearChunkTimer() {
    if (chunkTimer) {
      clearTimeout(chunkTimer);
      chunkTimer = null;
    }
  }

  function startChunkRecorder() {
    if (!recordingActive || !stream) return;

    const options = mimeType ? { mimeType } : undefined;
    try {
      recorder = options ? new MediaRecorder(stream, options) : new MediaRecorder(stream);
    } catch {
      recorder = new MediaRecorder(stream);
    }

    // Prefer the type MediaRecorder actually settled on.
    if (recorder.mimeType) {
      mimeType = recorder.mimeType;
      fileExt = extensionFor(mimeType);
    }

    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size >= MIN_BLOB_BYTES) {
        transcribe(event.data);
      }
    });

    recorder.addEventListener("stop", () => {
      // Start the next complete chunk only while the session is still active.
      if (recordingActive) {
        startChunkRecorder();
      }
    });

    recorder.start(); // no timeslice — each stop yields a complete container file
    chunkTimer = setTimeout(() => {
      if (recorder && recorder.state === "recording") {
        recorder.stop();
      }
    }, CHUNK_MS);
  }

  async function start() {
    const res = await fetch(cfg.startUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cfg.csrf,
      },
      body: "{}",
    });
    const data = await readJson(res);
    if (!res.ok || !data.visit_id) {
      throw new Error(data.error || "Couldn’t start the visit.");
    }
    visitId = data.visit_id;
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mimeType = pickMimeType();
    fileExt = extensionFor(mimeType);
    recordingActive = true;
    startChunkRecorder();
    consentStep.hidden = true;
    recordStep.hidden = false;
    stopBtn.disabled = false;
    discardBtn.disabled = false;
    setStatus("Recording — speak naturally. We’ll write it down as we go.");
  }

  consentYes.addEventListener("click", async () => {
    consentYes.disabled = true;
    try {
      await start();
    } catch (err) {
      consentYes.disabled = false;
      recordingActive = false;
      clearChunkTimer();
      const micDenied =
        err && (err.name === "NotAllowedError" || err.name === "NotFoundError");
      setStatus(
        micDenied
          ? "Couldn’t open the microphone. Check browser permission and try again."
          : err.message || "Couldn’t start recording. Please try again."
      );
      recordStep.hidden = false;
      consentStep.hidden = true;
    }
  });

  stopBtn.addEventListener("click", async () => {
    if (summarizing) return;
    summarizing = true;
    stopBtn.disabled = true;
    setStatus("Finishing the last audio chunk…");

    recordingActive = false;
    clearChunkTimer();

    if (recorder && recorder.state !== "inactive") {
      await new Promise((resolve) => {
        recorder.addEventListener("stop", resolve, { once: true });
        recorder.stop();
      });
    }
    if (stream) stream.getTracks().forEach((t) => t.stop());

    await waitForPendingTranscribes();

    if (!visitId) {
      setStatus("Recording never started — go back and consent again.");
      summarizing = false;
      stopBtn.disabled = false;
      return;
    }
    if (!transcript.trim()) {
      setStatus("No transcript yet. Record a few more seconds of speech, then try again.");
      summarizing = false;
      stopBtn.disabled = false;
      return;
    }

    setStatus("Summarizing…");
    try {
      const res = await fetch(`/visits/${visitId}/summarize/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": cfg.csrf,
        },
        body: JSON.stringify({ transcript }),
      });
      const data = await readJson(res);
      if (res.ok) {
        window.location.href = `/visits/${visitId}/`;
        return;
      }
      setStatus(
        data.error ||
          "The summary didn’t come through. Your transcript is still here — try again in a moment."
      );
      stopBtn.disabled = false;
      summarizing = false;
    } catch {
      setStatus("Couldn’t reach the summary service. Your transcript is still here — try again.");
      stopBtn.disabled = false;
      summarizing = false;
    }
  });

  discardBtn.addEventListener("click", () => {
    recordingActive = false;
    clearChunkTimer();
    if (recorder && recorder.state !== "inactive") recorder.stop();
    if (stream) stream.getTracks().forEach((t) => t.stop());
    if (!visitId) {
      window.location.href = "/visits/";
      return;
    }
    const form = document.createElement("form");
    form.method = "post";
    form.action = `/visits/${visitId}/discard/`;
    const csrf = document.createElement("input");
    csrf.type = "hidden";
    csrf.name = "csrfmiddlewaretoken";
    csrf.value = cfg.csrf;
    form.appendChild(csrf);
    document.body.appendChild(form);
    form.submit();
  });
})();
