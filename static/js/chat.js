(function () {
  const form = document.getElementById("chat-form");
  const thread = document.getElementById("thread");
  const input = document.getElementById("chat-message");
  const tone = document.getElementById("tone");
  const easy = document.getElementById("chat-easy-read");
  const csrf = form.querySelector("[name=csrfmiddlewaretoken]").value;

  function addBubble(role, text, escalated) {
    const empty = thread.querySelector(".thread-empty");
    if (empty) empty.remove();
    const el = document.createElement("article");
    el.className = escalated ? "escalation-card" : `bubble bubble--${role}`;
    el.textContent = text;
    thread.appendChild(el);
    thread.scrollTop = thread.scrollHeight;
  }

  function applyEasyRead(on) {
    document.documentElement.dataset.easyRead = on ? "on" : "off";
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

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    addBubble("user", message, false);
    input.value = "";
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
      if (!res.ok) {
        addBubble("assistant", data.error || "Aira couldn’t reply just then. Try again.", false);
        return;
      }
      addBubble("assistant", data.reply, data.escalated);
    } catch {
      addBubble("assistant", "The connection dropped. Try sending that again.", false);
    }
  });
})();
