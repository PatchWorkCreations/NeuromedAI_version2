/*
 * reCAPTCHA v3: fetch a token for this form's action right before it submits.
 * Runs after the browser's own validation (on "submit", not on button click).
 * If Google's script is blocked or slow, the form still submits and the server decides.
 */
(function () {
  document.querySelectorAll("input[data-recaptcha-action]").forEach((field) => {
    const form = field.form;
    if (!form) return;
    const key = field.dataset.siteKey;
    const action = field.dataset.recaptchaAction;
    const button = form.querySelector('[type="submit"]');
    let pending = false;

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (pending) return;
      pending = true;
      if (button) button.disabled = true;

      let done = false;
      const go = (token) => {
        if (done) return;
        done = true;
        field.value = token || "";
        form.submit();
      };
      setTimeout(() => go(""), 8000);
      if (!window.grecaptcha || !window.grecaptcha.ready) {
        go("");
        return;
      }
      window.grecaptcha.ready(() => {
        window.grecaptcha.execute(key, { action }).then(go, () => go(""));
      });
    });

    // Coming back with the Back button: allow a fresh try.
    window.addEventListener("pageshow", () => {
      pending = false;
      field.value = "";
      if (button) button.disabled = false;
    });
  });
})();
