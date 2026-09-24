(function () {
  const form = document.getElementById("chat-form");
  const thread = document.getElementById("thread");
  const input = document.getElementById("chat-message");
  const tone = document.getElementById("tone");
  const easy = document.getElementById("chat-easy-read");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
  const airaIcon = thread.dataset.airaIcon || "";
  const col = document.getElementById("thread-col") || thread;
  const send = form.querySelector(".composer__send");

  let conversationId = thread.dataset.conversationId || "";
  const conversationUrl = thread.dataset.conversationUrl || "/chat/0/";

  function urlFor(id) {
    return conversationUrl.replace(/0\/$/, `${id}/`);
  }

  /* Put this conversation at the top of "Today" in the history list. */
  function touchHistory(id, title) {
    const list = document.getElementById("convos-list");
    if (!list) return;
    const emptyNote = document.getElementById("convos-empty");
    if (emptyNote) emptyNote.remove();

    let group = list.querySelector('[data-group="Today"]');
    if (!group) {
      group = document.createElement("div");
      group.className = "convos__group";
      group.dataset.group = "Today";
      group.innerHTML = "<h3>Today</h3><ul></ul>";
      list.prepend(group);
    }
    const ul = group.querySelector("ul");
    const href = urlFor(id);
    let li = list.querySelector(`a[href="${href}"]`)?.closest("li");
    if (!li) {
      li = document.createElement("li");
      li.className = "convo";
      const a = document.createElement("a");
      a.href = href;
      a.textContent = title || "New conversation";
      li.appendChild(a);
    }
    const oldGroup = li.closest(".convos__group");
    ul.prepend(li);
    if (oldGroup && oldGroup !== group && !oldGroup.querySelector("li")) oldGroup.remove();

    list.querySelectorAll("li.convo").forEach((el) => {
      const on = el === li;
      el.classList.toggle("is-active", on);
      const link = el.querySelector("a");
      if (on) link.setAttribute("aria-current", "page"); else link.removeAttribute("aria-current");
    });
    const fresh = document.querySelector(".convos__new");
    if (fresh) fresh.removeAttribute("aria-current");
  }

  function scrollToEnd() {
    thread.scrollTop = thread.scrollHeight;
  }

  const USER_ICON = `
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="8.2" r="3.4" fill="currentColor"/>
      <path d="M5.2 19.2c1.1-3.2 3.6-4.8 6.8-4.8s5.7 1.6 6.8 4.8"
            stroke="currentColor" stroke-width="1.8" stroke-linecap="round"
            fill="none"/>
    </svg>`;

  function avatarEl(role) {
    const avatar = document.createElement("span");
    avatar.className = `msg__avatar msg__avatar--${role === "user" ? "user" : "aira"}`;
    avatar.setAttribute("aria-hidden", "true");
    if (role === "user") {
      avatar.innerHTML = USER_ICON;
    } else {
      const img = document.createElement("img");
      img.src = airaIcon;
      img.alt = "";
      img.width = 32;
      img.height = 32;
      avatar.appendChild(img);
    }
    return avatar;
  }

  function clearFollowUps() {
    col.querySelectorAll(".follow-ups").forEach((el) => el.remove());
  }

  function addFollowUps(row, questions) {
    if (!questions || !questions.length) return;
    const box = document.createElement("div");
    box.className = "follow-ups";
    box.setAttribute("aria-label", "Suggested next questions");
    const label = document.createElement("span");
    label.className = "follow-ups__label";
    label.textContent = "You could ask";
    box.appendChild(label);
    questions.forEach((q) => {
      const b = document.createElement("button");
      b.type = "button";
      b.dataset.ask = q;
      b.textContent = q;
      box.appendChild(b);
    });
    (row.querySelector(".msg__body") || row).appendChild(box);
    scrollToEnd();
  }

  function nearBottom() {
    return thread.scrollHeight - thread.scrollTop - thread.clientHeight < 120;
  }

  /*
   * Reveal a finished, safety-checked reply word by word at a calm reading pace.
   * Screen readers get the whole reply at once (sr-only copy); the animated text
   * is aria-hidden so it isn't announced word by word.
   */
  function typeOut(bubble, text) {
    return new Promise((resolve) => {
      if (reduceMotion || !text) {
        bubble.appendChild(document.createTextNode(text));
        resolve();
        return;
      }
      const full = document.createElement("span");
      full.className = "sr-only";
      full.textContent = text;
      const shown = document.createElement("span");
      shown.setAttribute("aria-hidden", "true");
      shown.className = "typing-text is-typing";
      bubble.appendChild(full);
      bubble.appendChild(shown);

      const tokens = text.split(/(\s+)/);
      const words = tokens.filter((t) => t.trim()).length;
      const duration = Math.min(4000, Math.max(700, words * 32));
      const start = performance.now();
      let done = 0;
      let finished = false;

      function finish() {
        if (finished) return;
        finished = true;
        shown.textContent = text;
        shown.classList.remove("is-typing");
        document.removeEventListener("aira:finish-typing", finish);
        resolve();
      }
      document.addEventListener("aira:finish-typing", finish);

      function frame(now) {
        if (finished) return;
        const target = Math.min(tokens.length, Math.ceil(((now - start) / duration) * tokens.length));
        if (target > done) {
          const follow = nearBottom();
          shown.textContent = tokens.slice(0, target).join("");
          done = target;
          if (follow) scrollToEnd();
        }
        if (done >= tokens.length) finish();
        else requestAnimationFrame(frame);
      }
      requestAnimationFrame(frame);
    });
  }

  function addBubble(role, text, escalated) {
    const empty = thread.querySelector(".thread-empty");
    if (empty) empty.remove();

    const row = document.createElement("div");
    row.className = `msg msg--${role}${escalated ? " msg--escalated" : ""}`;

    const bubble = document.createElement("article");
    bubble.className = escalated
      ? "escalation-card"
      : `bubble bubble--${role}`;
    const who = document.createElement("span");
    who.className = "sr-only";
    who.textContent = role === "user" ? "You: " : "Aira: ";
    bubble.appendChild(who);
    if (text !== null) bubble.appendChild(document.createTextNode(text));

    if (role === "user") {
      const body = document.createElement("div");
      body.className = "msg__body msg__body--user";
      if (text) body.appendChild(bubble);
      row.appendChild(body);
    } else {
      row.appendChild(avatarEl("assistant"));
      const body = document.createElement("div");
      body.className = "msg__body";
      body.appendChild(bubble);
      row.appendChild(body);
    }

    col.appendChild(row);
    scrollToEnd();
    return row;
  }

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const THINKING = [
    [0, "Aira is reading your message…"],
    [2500, "Looking through your visits and documents…"],
    [6000, "Putting it into plain words…"],
    [12000, "Still with you, almost there…"],
  ];
  let thinkingTimers = [];

  function showTyping() {
    hideTyping();
    const empty = thread.querySelector(".thread-empty");
    if (empty) empty.remove();

    const row = document.createElement("div");
    row.className = "msg msg--assistant msg--typing";
    row.id = "aira-typing";

    const body = document.createElement("div");
    body.className = "msg__body";
    const bubble = document.createElement("div");
    bubble.className = "bubble bubble--assistant bubble--typing";
    bubble.innerHTML =
      '<span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>' +
      '<span class="thinking-text" role="status"></span>';
    body.appendChild(bubble);

    row.appendChild(avatarEl("assistant"));
    row.appendChild(body);
    col.appendChild(row);
    scrollToEnd();

    const label = bubble.querySelector(".thinking-text");
    thinkingTimers = THINKING.map(([delay, text]) =>
      setTimeout(() => {
        label.classList.remove("is-in");
        void label.offsetWidth; // restart the fade
        label.textContent = text;
        label.classList.add("is-in");
      }, delay)
    );
  }

  function hideTyping() {
    thinkingTimers.forEach(clearTimeout);
    thinkingTimers = [];
    const el = document.getElementById("aira-typing");
    if (el) el.remove();
  }

  /* ——— Attachments: pick, photograph, drop or paste ——— */
  const MAX_FILES = 3;
  const MAX_BYTES = 15 * 1024 * 1024;
  const OK_EXT = /\.(pdf|docx|txt|png|jpe?g|webp|heic)$/i;
  const tray = document.getElementById("att-tray");
  const attError = document.getElementById("att-error");
  const fileInput = document.getElementById("file-input");
  const captureInput = document.getElementById("capture-input");
  let pending = []; // [{file, url}]

  function prettySize(n) {
    if (n < 1024 * 1024) return `${Math.max(1, Math.round(n / 1024))} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  function showAttError(text) {
    if (!attError) return;
    attError.textContent = text || "";
    attError.hidden = !text;
  }

  function renderTray() {
    if (!tray) return;
    tray.innerHTML = "";
    tray.hidden = pending.length === 0;
    pending.forEach((item, i) => {
      const chip = document.createElement("div");
      chip.className = "att-chip";
      if (item.url) {
        const img = document.createElement("img");
        img.src = item.url;
        img.alt = "";
        chip.appendChild(img);
      } else {
        const icon = document.createElement("span");
        icon.className = "att-chip__icon";
        icon.textContent = (item.file.name.split(".").pop() || "file").toUpperCase().slice(0, 4);
        chip.appendChild(icon);
      }
      const meta = document.createElement("span");
      meta.className = "att-chip__meta";
      const nm = document.createElement("strong");
      nm.textContent = item.file.name;
      const sz = document.createElement("span");
      sz.textContent = prettySize(item.file.size);
      meta.append(nm, sz);
      chip.appendChild(meta);
      const rm = document.createElement("button");
      rm.type = "button";
      rm.className = "att-chip__rm";
      rm.setAttribute("aria-label", `Remove ${item.file.name}`);
      rm.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
      rm.addEventListener("click", () => {
        if (item.url) URL.revokeObjectURL(item.url);
        pending.splice(i, 1);
        renderTray();
        syncSend();
        input.focus();
      });
      chip.appendChild(rm);
      tray.appendChild(chip);
    });
  }

  function addFiles(list) {
    showAttError("");
    for (const file of Array.from(list || [])) {
      if (pending.length >= MAX_FILES) {
        showAttError(`You can share up to ${MAX_FILES} files at a time.`);
        break;
      }
      if (!OK_EXT.test(file.name) && !/^image\//.test(file.type)) {
        showAttError(`“${file.name}” isn’t a type Aira can read. Use a photo, PDF, Word file, or text file.`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        showAttError(`“${file.name}” is over 15 MB. Try a smaller photo or a shorter PDF.`);
        continue;
      }
      let named = file;
      if (!OK_EXT.test(file.name)) {
        // Pasted/camera images can arrive as "image.png" or with no name at all.
        const ext = (file.type.split("/")[1] || "jpg").replace("jpeg", "jpg");
        named = new File([file], `photo-${Date.now()}.${ext}`, { type: file.type });
      }
      const isImg = /^image\/(png|jpe?g|webp)$/.test(named.type);
      pending.push({ file: named, url: isImg ? URL.createObjectURL(named) : "" });
    }
    renderTray();
    syncSend();
  }

  document.getElementById("attach-btn")?.addEventListener("click", () => fileInput.click());
  fileInput?.addEventListener("change", () => { addFiles(fileInput.files); fileInput.value = ""; });
  captureInput?.addEventListener("change", () => { addFiles(captureInput.files); captureInput.value = ""; });

  // Paste a screenshot or photo straight into the message box.
  input.addEventListener("paste", (e) => {
    const files = Array.from(e.clipboardData?.files || []);
    if (files.length) { e.preventDefault(); addFiles(files); }
  });

  // Drag and drop anywhere on the conversation.
  const veil = document.getElementById("drop-veil");
  const chatEl = document.querySelector(".chat");
  let dragDepth = 0;
  chatEl?.addEventListener("dragenter", (e) => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault(); dragDepth += 1; if (veil) veil.hidden = false;
  });
  chatEl?.addEventListener("dragover", (e) => { if (e.dataTransfer?.types?.includes("Files")) e.preventDefault(); });
  chatEl?.addEventListener("dragleave", () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth && veil) veil.hidden = true; });
  chatEl?.addEventListener("drop", (e) => {
    if (!e.dataTransfer?.files?.length) return;
    e.preventDefault(); dragDepth = 0; if (veil) veil.hidden = true;
    addFiles(e.dataTransfer.files);
  });

  /* Camera: phones use the native camera; desktops get an in-page webcam view. */
  const cam = document.getElementById("cam");
  const video = document.getElementById("cam-video");
  const canvas = document.getElementById("cam-canvas");
  const still = document.getElementById("cam-still");
  const snapBtn = document.getElementById("cam-snap");
  const useBtn = document.getElementById("cam-use");
  const retakeBtn = document.getElementById("cam-retake");
  let camStream = null;
  let camBlob = null;
  const coarse = window.matchMedia("(pointer: coarse)").matches;

  function camMode(showing) {
    video.hidden = showing; still.hidden = !showing;
    snapBtn.hidden = showing; useBtn.hidden = !showing; retakeBtn.hidden = !showing;
  }

  async function openCamera() {
    if (coarse || !navigator.mediaDevices?.getUserMedia) { captureInput.click(); return; }
    try {
      camStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: { ideal: 1920 }, height: { ideal: 1080 } }, audio: false,
      });
    } catch {
      captureInput.click(); // permission denied or no webcam: fall back to the file picker
      return;
    }
    video.srcObject = camStream;
    await video.play().catch(() => {});
    camMode(false);
    cam.hidden = false;
    snapBtn.focus();
  }

  function closeCamera() {
    camStream?.getTracks().forEach((t) => t.stop());
    camStream = null; camBlob = null;
    if (still.src) URL.revokeObjectURL(still.src);
    still.removeAttribute("src");
    cam.hidden = true;
    document.getElementById("camera-btn")?.focus();
  }

  document.getElementById("camera-btn")?.addEventListener("click", openCamera);
  document.getElementById("cam-close")?.addEventListener("click", closeCamera);
  cam?.addEventListener("click", (e) => { if (e.target === cam) closeCamera(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && cam && !cam.hidden) closeCamera(); });
  snapBtn?.addEventListener("click", () => {
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => {
      camBlob = blob;
      still.src = URL.createObjectURL(blob);
      camMode(true);
      useBtn.focus();
    }, "image/jpeg", 0.9);
  });
  retakeBtn?.addEventListener("click", () => { if (still.src) URL.revokeObjectURL(still.src); camBlob = null; camMode(false); });
  useBtn?.addEventListener("click", () => {
    if (camBlob) addFiles([new File([camBlob], `photo-${Date.now()}.jpg`, { type: "image/jpeg" })]);
    closeCamera();
    input.focus();
  });

  function renderAttachments(row, items) {
    if (!items || !items.length) return;
    const grid = document.createElement("div");
    grid.className = "att-grid";
    items.forEach((a) => {
      const link = document.createElement("a");
      if (a.is_image && (a.url || a.localUrl)) {
        link.className = "att att--img";
        link.href = a.url || a.localUrl;
        link.target = "_blank";
        link.rel = "noopener";
        const img = document.createElement("img");
        img.src = a.localUrl || a.url;
        img.alt = `Photo you shared: ${a.name}`;
        link.appendChild(img);
      } else {
        link.className = "att att--file";
        link.href = a.detail_url || "#";
        link.innerHTML = '<span class="att__icon" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3.5H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-10z"/><path d="M14 3.5v5h5"/></svg></span>';
        const meta = document.createElement("span");
        meta.className = "att__meta";
        const nm = document.createElement("strong");
        nm.textContent = a.name;
        const sz = document.createElement("span");
        sz.textContent = a.size ? prettySize(a.size) : "Saved to Documents";
        meta.append(nm, sz);
        link.appendChild(meta);
      }
      grid.appendChild(link);
    });
    const body = row.querySelector(".msg__body") || row;
    body.prepend(grid);
    return grid;
  }

  function syncSend() {
    if (send) send.disabled = form.dataset.busy === "1" || (!input.value.trim() && !pending.length);
  }

  function setBusy(busy) {
    input.disabled = busy;
    syncSend();
  }

  function applyEasyRead(on) {
    document.documentElement.dataset.easyRead = on ? "on" : "off";
    document.documentElement.dataset.easy = on ? "on" : "off";
    if (easy) easy.setAttribute("aria-pressed", on ? "true" : "false");
  }

  if (easy) {
    easy.addEventListener("click", () => {
      applyEasyRead(document.documentElement.dataset.easyRead !== "on");
    });
  }

  if (tone) {
    tone.addEventListener("change", () => {
      if (tone.value === "Geriatric") applyEasyRead(true);
    });
  }

  function resizeComposer() {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 176)}px`;
  }

  input.addEventListener("input", () => { resizeComposer(); syncSend(); });
  syncSend();
  resizeComposer();
  scrollToEnd();

  // Enter sends; Shift+Enter inserts a newline.
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    if (event.isComposing) return;
    event.preventDefault();
    form.requestSubmit();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.dispatchEvent(new Event("aira:finish-typing"));
  });
  thread.addEventListener("click", (e) => {
    if (e.target.closest(".typing-text.is-typing")) document.dispatchEvent(new Event("aira:finish-typing"));
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.dataset.busy === "1") return;
    const message = input.value.trim();
    if (!message && !pending.length) return;
    clearFollowUps();
    showAttError("");
    const sending = pending;
    pending = [];
    renderTray();
    const userRow = addBubble("user", message, false);
    const localGrid = renderAttachments(userRow, sending.map((p) => ({
      name: p.file.name, is_image: !!p.url, localUrl: p.url, size: p.file.size,
    })));
    input.value = "";
    resizeComposer();
    form.dataset.busy = "1";
    setBusy(true);
    showTyping();
    const body = new FormData();
    body.append("message", message);
    body.append("tone", tone.value);
    if (conversationId) body.append("conversation_id", conversationId);
    sending.forEach((p) => body.append("files", p.file, p.file.name));
    try {
      const res = await fetch("/api/send-chat/", {
        method: "POST",
        headers: { "X-CSRFToken": csrf },
        body,
      });
      const data = await res.json();
      hideTyping();
      if (data.attachments && data.attachments.length && localGrid) {
        // Swap the local previews for the saved, private copies.
        localGrid.remove();
        renderAttachments(userRow, data.attachments.map((a, i) => ({
          ...a, localUrl: sending[i]?.url || "", size: sending[i]?.file.size,
        })));
      }
      if (!res.ok && !data.conversation_id && sending.length) {
        // Rejected before anything was saved: give the files back so nothing is lost.
        pending = sending;
        renderTray();
      }
      if (data.conversation_id) {
        const isNew = String(data.conversation_id) !== String(conversationId);
        conversationId = String(data.conversation_id);
        thread.dataset.conversationId = conversationId;
        if (isNew) {
          history.replaceState(null, "", urlFor(conversationId));
          const h1 = document.getElementById("chat-title");
          if (h1 && data.title) h1.textContent = data.title;
          document.title = `${data.title || "Ask Aira"} · Aira`;
        }
        touchHistory(conversationId, data.title);
      }
      if (!res.ok) {
        addBubble("assistant", data.error || "Aira couldn’t reply just then. Try again.", false);
        return;
      }
      if (data.escalated) {
        // Safety redirects appear at once and calmly; no typing effect.
        const row = addBubble("assistant", data.reply, true);
        row.classList.add("is-arriving");
      } else {
        const row = addBubble("assistant", null, false);
        await typeOut(row.querySelector(".bubble"), data.reply || "");
        addFollowUps(row, data.follow_ups);
      }
    } catch {
      hideTyping();
      addBubble("assistant", "The connection dropped. Try sending that again.", false);
    } finally {
      form.dataset.busy = "0";
      setBusy(false);
      input.focus();
    }
  });
})();
