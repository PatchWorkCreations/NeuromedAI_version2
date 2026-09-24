/* Signed-in shell: account menu. Reading options are handled by shell.js. */
(function () {
  "use strict";
  var btn = document.getElementById("acct-btn");
  var menu = document.getElementById("acct-menu");
  if (!btn || !menu) return;

  function setOpen(open) {
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  btn.addEventListener("click", function (e) {
    e.stopPropagation();
    setOpen(menu.hidden);
  });
  menu.addEventListener("click", function (e) { e.stopPropagation(); });
  document.addEventListener("click", function () { setOpen(false); });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !menu.hidden) { setOpen(false); btn.focus(); }
  });
})();
