(function () {
  const form = document.getElementById("chat-form");
  const thread = document.getElementById("thread");
  const input = document.getElementById("chat-message");
  const tone = document.getElementById("tone");
  const easy = document.getElementById("chat-easy-read");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;
  const airaIcon = thread.dataset.airaIcon || "";

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

  function addBubble(role, text, escalated) {
    const empty = thread.querySelector(".thread-empty");
    if (empty) empty.remove();

    const row = document.createElement("div");
    row.className = `msg msg--${role}${escalated ? " msg--escalated" : ""}`;

    const bubble = document.createElement("article");
    bubble.className = escalated
      ? "escalation-card"
      : `bubble bubble--${role}`;
    bubble.textContent = text;

    if (role === "user") {
      row.appendChild(bubble);
      row.appendChild(avatarEl("user"));
    } else {
      row.appendChild(avatarEl("assistant"));
      row.appendChild(bubble);
    }

    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
  }

  function showTyping() {
    hideTyping();
    const empty = thread.querySelector(".thread-empty");
    if (empty) empty.remove();

    const row = document.createElement("div");
    row.className = "msg msg--assistant msg--typing";
    row.id = "aira-typing";
    row.setAttribute("aria-live", "polite");
    row.setAttribute("aria-label", "Aira is typing");

    const bubble = document.createElement("div");
    bubble.className = "bubble bubble--assistant bubble--typing";
    bubble.innerHTML =
      '<span class="typing-dots" aria-hidden="true">' +
      '<span></span><span></span><span></span>' +
      "</span>";

    row.appendChild(avatarEl("assistant"));
    row.appendChild(bubble);
    thread.appendChild(row);
    thread.scrollTop = thread.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById("aira-typing");
    if (el) el.remove();
  }

  function setBusy(busy) {
    input.disabled = busy;
    const send = form.querySelector(".composer__send");
    if (send) send.disabled = busy;
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
    input.style.height = `${Math.min(input.scrollHeight, 144)}px`;
  }

  input.addEventListener("input", resizeComposer);

  // Enter sends; Shift+Enter inserts a newline.
  input.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey) return;
    if (event.isComposing) return;
    event.preventDefault();
    form.requestSubmit();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (form.dataset.busy === "1") return;
    const message = input.value.trim();
    if (!message) return;
    addBubble("user", message, false);
    input.value = "";
    resizeComposer();
    form.dataset.busy = "1";
    setBusy(true);
    showTyping();
    const body = { message, tone: tone.value };
    try {
      const res = await fetch("/api/send-chat/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrf,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      hideTyping();
      if (!res.ok) {
        addBubble("assistant", data.error || "Aira couldn’t reply just then. Try again.", false);
        return;
      }
      addBubble("assistant", data.reply, data.escalated);
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
