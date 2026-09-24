(function () {
  "use strict";

  var CHEVRON =
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 6l4 4 4-4"/></svg>';

  function optionLabel(option) {
    return (option.textContent || option.label || option.value || "").trim();
  }

  function closeAll(except) {
    document.querySelectorAll(".nm-select.is-open").forEach(function (picker) {
      if (except && picker === except) return;
      closePicker(picker);
    });
  }

  function closePicker(picker) {
    var trigger = picker.querySelector(".nm-select__trigger");
    var menu = picker.querySelector(".nm-select__menu");
    picker.classList.remove("is-open");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    if (menu) menu.hidden = true;
  }

  function openPicker(picker) {
    var trigger = picker.querySelector(".nm-select__trigger");
    var menu = picker.querySelector(".nm-select__menu");
    closeAll(picker);
    picker.classList.add("is-open");
    if (trigger) trigger.setAttribute("aria-expanded", "true");
    if (menu) {
      menu.hidden = false;
      var selected = menu.querySelector('[aria-selected="true"]');
      var focusTarget = selected || menu.querySelector('[role="option"]');
      if (focusTarget) focusTarget.focus();
    }
  }

  function syncFromSelect(picker) {
    var select = picker._nmSelect;
    var valueEl = picker.querySelector(".nm-select__value");
    var menu = picker.querySelector(".nm-select__menu");
    if (!select || !valueEl || !menu) return;

    var selected = select.options[select.selectedIndex];
    valueEl.textContent = selected ? optionLabel(selected) : "";

    menu.querySelectorAll('[role="option"]').forEach(function (item) {
      item.setAttribute(
        "aria-selected",
        item.dataset.value === select.value ? "true" : "false"
      );
    });
  }

  function setValue(picker, value) {
    var select = picker._nmSelect;
    if (!select) return;
    select.value = value;
    Array.prototype.forEach.call(select.options, function (option) {
      option.selected = option.value === value;
    });
    syncFromSelect(picker);
    select.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function buildMenu(select, menuId) {
    var menu = document.createElement("ul");
    menu.className = "nm-select__menu";
    menu.id = menuId;
    menu.setAttribute("role", "listbox");
    menu.hidden = true;

    Array.prototype.forEach.call(select.options, function (option) {
      var item = document.createElement("li");
      item.setAttribute("role", "option");
      item.tabIndex = -1;
      item.dataset.value = option.value;
      item.textContent = optionLabel(option);
      item.setAttribute("aria-selected", option.selected ? "true" : "false");
      if (option.disabled) {
        item.setAttribute("aria-disabled", "true");
        item.classList.add("is-disabled");
      }
      menu.appendChild(item);
    });

    return menu;
  }

  function enhanceSelect(select) {
    if (!select || select.dataset.nmSelect === "on" || select.closest(".nm-select")) {
      return;
    }

    var picker = document.createElement("div");
    picker.className = "nm-select";
    if (
      select.classList.contains("nm-select--full") ||
      select.closest(".upload-form, .input-group, .input-row")
    ) {
      picker.classList.add("nm-select--full");
    }

    var selectId = select.id || ("nm-select-" + Math.random().toString(36).slice(2, 9));
    if (!select.id) select.id = selectId;
    var menuId = selectId + "-menu";

    select.dataset.nmSelect = "on";
    select.classList.add("nm-select__native");
    select.tabIndex = -1;
    // Keep the real <select> enabled + named so form posts always include it.
    select.setAttribute("aria-hidden", "true");

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "nm-select__trigger";
    trigger.id = selectId + "-trigger";
    trigger.setAttribute("aria-haspopup", "listbox");
    trigger.setAttribute("aria-expanded", "false");
    trigger.setAttribute("aria-controls", menuId);
    if (select.getAttribute("aria-labelledby")) {
      trigger.setAttribute(
        "aria-labelledby",
        select.getAttribute("aria-labelledby") + " " + trigger.id
      );
    } else if (select.getAttribute("aria-label")) {
      trigger.setAttribute("aria-label", select.getAttribute("aria-label"));
    }

    var valueEl = document.createElement("span");
    valueEl.className = "nm-select__value";

    var chevron = document.createElement("span");
    chevron.className = "nm-select__chevron";
    chevron.setAttribute("aria-hidden", "true");
    chevron.innerHTML = CHEVRON;

    trigger.appendChild(valueEl);
    trigger.appendChild(chevron);

    var menu = buildMenu(select, menuId);
    if (select.getAttribute("aria-labelledby")) {
      menu.setAttribute("aria-labelledby", select.getAttribute("aria-labelledby"));
    }

    var parent = select.parentNode;
    parent.insertBefore(picker, select);
    picker.appendChild(select);
    picker.appendChild(trigger);
    picker.appendChild(menu);
    picker._nmSelect = select;

    syncFromSelect(picker);

    trigger.addEventListener("click", function (event) {
      event.preventDefault();
      event.stopPropagation();
      if (menu.hidden) openPicker(picker);
      else closePicker(picker);
    });

    menu.addEventListener("click", function (event) {
      event.stopPropagation();
      var option = event.target.closest('[role="option"]');
      if (!option || option.getAttribute("aria-disabled") === "true") return;
      setValue(picker, option.dataset.value);
      closePicker(picker);
      trigger.focus();
    });

    select.addEventListener("change", function () {
      syncFromSelect(picker);
    });

    var form = select.closest("form");
    if (form && !form.dataset.nmSelectSubmitBound) {
      form.dataset.nmSelectSubmitBound = "1";
      form.addEventListener("submit", function () {
        form.querySelectorAll(".nm-select").forEach(function (openPicker) {
          var native = openPicker._nmSelect;
          var selectedOpt = openPicker.querySelector('[role="option"][aria-selected="true"]');
          if (native && selectedOpt) {
            native.value = selectedOpt.dataset.value;
            Array.prototype.forEach.call(native.options, function (option) {
              option.selected = option.value === native.value;
            });
          }
          closePicker(openPicker);
        });
      });
    }
  }

  function onKeydown(event) {
    var openPickerEl = document.querySelector(".nm-select.is-open");
    if (!openPickerEl) return;

    var menu = openPickerEl.querySelector(".nm-select__menu");
    var trigger = openPickerEl.querySelector(".nm-select__trigger");
    if (!menu) return;

    if (event.key === "Escape") {
      closePicker(openPickerEl);
      if (trigger) trigger.focus();
      return;
    }

    if (!openPickerEl.contains(document.activeElement)) return;

    var options = Array.prototype.slice.call(
      menu.querySelectorAll('[role="option"]:not([aria-disabled="true"])')
    );
    var index = options.indexOf(document.activeElement);

    if (event.key === "ArrowDown") {
      event.preventDefault();
      var next = options[Math.min(index + 1, options.length - 1)];
      if (next) next.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      var prev = options[Math.max(index - 1, 0)];
      if (prev) prev.focus();
    } else if (
      (event.key === "Enter" || event.key === " ") &&
      document.activeElement &&
      document.activeElement.matches('[role="option"]')
    ) {
      event.preventDefault();
      var option = document.activeElement;
      if (option.getAttribute("aria-disabled") === "true") return;
      setValue(openPickerEl, option.dataset.value);
      closePicker(openPickerEl);
      if (trigger) trigger.focus();
    }
  }

  function init() {
    document.querySelectorAll("select").forEach(enhanceSelect);
  }

  document.addEventListener("click", function (event) {
    if (!event.target.closest(".nm-select")) closeAll();
  });
  document.addEventListener("keydown", onKeydown);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.AiraSelect = { enhanceAll: init, enhance: enhanceSelect };
})();
