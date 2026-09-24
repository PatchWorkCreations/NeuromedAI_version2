(function () {
  const root = document.documentElement;
  const FONT_KEY = "aira-font-step";
  const CONTRAST_KEY = "aira-contrast";
  const MIN = 0.9;
  const MAX = 1.4;
  const STEP = 0.1;

  function applyFont(value) {
    const next = Math.min(MAX, Math.max(MIN, value));
    root.style.setProperty("--nm-step", `${next}rem`);
    localStorage.setItem(FONT_KEY, String(next));
  }

  function applyContrast(on) {
    root.dataset.contrast = on ? "high" : "default";
    const toggle = document.getElementById("contrast-toggle");
    if (toggle) toggle.setAttribute("aria-pressed", on ? "true" : "false");
    localStorage.setItem(CONTRAST_KEY, on ? "high" : "default");
  }

  const savedFont = parseFloat(localStorage.getItem(FONT_KEY) || "1");
  applyFont(Number.isFinite(savedFont) ? savedFont : 1);
  applyContrast(localStorage.getItem(CONTRAST_KEY) === "high");

  document.querySelectorAll("[data-font]").forEach((button) => {
    button.addEventListener("click", () => {
      const current = parseFloat(getComputedStyle(root).getPropertyValue("--nm-step")) || 1;
      applyFont(current + Number(button.dataset.font) * STEP);
    });
  });

  const contrastToggle = document.getElementById("contrast-toggle");
  if (contrastToggle) {
    contrastToggle.addEventListener("click", () => {
      applyContrast(root.dataset.contrast !== "high");
    });
  }
})();
