(function () {
  "use strict";
  var root = document.documentElement;
  var KEY = "aira-reading";

  function load() {
    try { return JSON.parse(localStorage.getItem(KEY) || "{}") || {}; }
    catch (e) { return {}; }
  }
  function save(state) {
    try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {}
  }

  var state = load();
  var DEFAULTS = { size: 16, theme: "light", easy: false };
  state = {
    size: Number(state.size) || DEFAULTS.size,
    theme: ["light", "dark", "contrast"].indexOf(state.theme) > -1 ? state.theme : DEFAULTS.theme,
    easy: state.easy === true
  };

  var plainNodes = [].slice.call(document.querySelectorAll("[data-plain]"));
  plainNodes.forEach(function (el) { el.setAttribute("data-rich", el.innerHTML); });

  function applyEasy(on) {
    plainNodes.forEach(function (el) {
      el.innerHTML = on ? el.getAttribute("data-plain") : el.getAttribute("data-rich");
    });
    root.setAttribute("data-easy", on ? "on" : "off");
    var sw = document.getElementById("easy-read");
    if (sw) {
      sw.setAttribute("aria-pressed", on ? "true" : "false");
      sw.setAttribute("aria-label", on ? "Turn Easy Read off" : "Turn Easy Read on");
    }
    var t = document.getElementById("demo-try");
    if (t) t.innerHTML = on ? "Switch back →" : "Try Easy Read →";
  }

  function applySize(px) {
    root.style.setProperty("--step", px + "px");
    [].forEach.call(document.querySelectorAll("[data-size]"), function (b) {
      b.setAttribute("aria-pressed", Number(b.dataset.size) === px ? "true" : "false");
    });
  }

  function applyTheme(name) {
    root.setAttribute("data-theme", name);
    [].forEach.call(document.querySelectorAll("[data-theme-set]"), function (b) {
      b.setAttribute("aria-pressed", b.dataset.themeSet === name ? "true" : "false");
    });
  }

  function commit() { save(state); }

  applySize(state.size);
  applyTheme(state.theme);
  applyEasy(state.easy);

  [].forEach.call(document.querySelectorAll("[data-size]"), function (b) {
    b.addEventListener("click", function () { state.size = Number(b.dataset.size); applySize(state.size); commit(); });
  });
  [].forEach.call(document.querySelectorAll("[data-theme-set]"), function (b) {
    b.addEventListener("click", function () { state.theme = b.dataset.themeSet; applyTheme(state.theme); commit(); });
  });

  function toggleEasy() { state.easy = !state.easy; applyEasy(state.easy); commit(); }
  var easyBtn = document.getElementById("easy-read");
  if (easyBtn) easyBtn.addEventListener("click", toggleEasy);
  var demoTry = document.getElementById("demo-try");
  if (demoTry) demoTry.addEventListener("click", toggleEasy);

  var reset = document.getElementById("reader-reset");
  if (reset) reset.addEventListener("click", function () {
    state = { size: DEFAULTS.size, theme: DEFAULTS.theme, easy: DEFAULTS.easy };
    applySize(state.size); applyTheme(state.theme); applyEasy(state.easy); commit();
  });

  var rBtn = document.getElementById("reader-btn");
  var rPanel = document.getElementById("reader-panel");
  function setReader(open) {
    if (!rPanel || !rBtn) return;
    rPanel.classList.toggle("open", open);
    rBtn.setAttribute("aria-expanded", open ? "true" : "false");
  }
  if (rBtn && rPanel) {
    rBtn.addEventListener("click", function (e) {
      e.stopPropagation();
      setReader(!rPanel.classList.contains("open"));
    });
    rPanel.addEventListener("click", function (e) { e.stopPropagation(); });
    document.addEventListener("click", function () { setReader(false); });
  }

  var header = document.getElementById("site-header");
  function onScroll() {
    if (header) header.classList.toggle("scrolled", window.scrollY > 4);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  var menu = document.getElementById("mobile-menu");
  var burger = document.getElementById("hamburger");
  var mClose = document.getElementById("m-close");
  function setMenu(open) {
    if (!menu || !burger) return;
    menu.classList.toggle("open", open);
    burger.classList.toggle("is-open", open);
    burger.setAttribute("aria-expanded", open ? "true" : "false");
    document.body.style.overflow = open ? "hidden" : "";
  }
  if (burger) burger.addEventListener("click", function () { setMenu(!menu.classList.contains("open")); });
  if (mClose) mClose.addEventListener("click", function () { setMenu(false); });
  if (menu) {
    menu.addEventListener("click", function (e) { if (e.target === menu) setMenu(false); });
    [].forEach.call(menu.querySelectorAll("a"), function (a) {
      a.addEventListener("click", function () { setMenu(false); });
    });
  }
  window.addEventListener("resize", function () { if (window.innerWidth >= 1040) setMenu(false); });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { setReader(false); setMenu(false); }
  });

  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var items = [].slice.call(document.querySelectorAll(".reveal"));
  if (items.length) {
    if (reduce || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("in"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
        });
      }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
      items.forEach(function (el, i) {
        el.style.transitionDelay = (Math.min(i % 4, 3) * 70) + "ms";
        io.observe(el);
      });
    }
  }
})();
