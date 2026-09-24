(function () {
  const consentStep = document.getElementById("consent-step");
  const recordStep = document.getElementById("record-step");
  const consentYes = document.getElementById("consent-yes");
  const stopBtn = document.getElementById("stop-btn");
  const discardBtn = document.getElementById("discard-btn");
  const statusEl = document.getElementById("record-status");
  const transcriptEl = document.getElementById("transcript");
  const cfg = window.AIRA_VISIT || {};

  let visitId = null;
  let recorder = null;
  let stream = null;
  let transcript = "";

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  async function transcribe(blob) {
    const body = new FormData();
    body.append("audio", blob, "chunk.webm");
    const res = await fetch(cfg.transcribeUrl, {
      method: "POST",
      headers: { "X-CSRFToken": cfg.csrf },
      body,
    });
    const data = await res.json();
    if (data.text) {
      transcript = `${transcript} ${data.text}`.trim();
      transcriptEl.textContent = transcript;
    }
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
    const data = await res.json();
    visitId = data.visit_id;
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    recorder = new MediaRecorder(stream);
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size) transcribe(event.data);
    });
    recorder.start(6000);
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
    } catch {
      consentYes.disabled = false;
      setStatus("Couldn’t open the microphone. Check browser permission and try again.");
      recordStep.hidden = false;
      consentStep.hidden = true;
    }
  });

  stopBtn.addEventListener("click", async () => {
    stopBtn.disabled = true;
    setStatus("Summarizing…");
    if (recorder && recorder.state !== "inactive") recorder.stop();
    if (stream) stream.getTracks().forEach((t) => t.stop());
    if (!visitId) return;
    const res = await fetch(`/visits/${visitId}/summarize/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": cfg.csrf,
      },
      body: JSON.stringify({ transcript }),
    });
    if (res.ok) {
      window.location.href = `/visits/${visitId}/`;
    } else {
      setStatus("The summary didn’t come through. Your transcript is still here — try again in a moment.");
      stopBtn.disabled = false;
    }
  });

  discardBtn.addEventListener("click", () => {
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
