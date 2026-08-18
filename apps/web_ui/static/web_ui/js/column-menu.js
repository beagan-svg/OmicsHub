(() => {
  const menu = document.querySelector(".column-menu");
  if (!menu) return;

  const toggle = menu.querySelector("#column-menu-toggle");
  const filter = menu.querySelector("#column-filter");
  const options = [...menu.querySelectorAll("[data-column-option]")];
  const groups = [...menu.querySelectorAll("[data-column-group]")];
  const empty = menu.querySelector("[data-column-empty]");
  const summary = menu.querySelector("[data-column-summary]");
  const countPill = menu.querySelector("[data-column-count]");
  const apply = menu.querySelector("[data-column-apply]");
  const boxes = [...menu.querySelectorAll('input[type="checkbox"]')];
  const defaults = new Set(JSON.parse(document.getElementById("default-column-keys").textContent));
  const locked = menu.querySelectorAll(".column-option--locked").length;
  const total = boxes.length + locked;
  const saved = new Set(boxes.filter((box) => box.checked).map((box) => box.value));

  const chosen = () => new Set(boxes.filter((box) => box.checked).map((box) => box.value));
  const sameAsSaved = (now) => now.size === saved.size && [...now].every((key) => saved.has(key));

  const sync = () => {
    const now = chosen();
    summary.textContent = `${now.size + locked} of ${total} shown`;
    countPill.textContent = now.size + locked;
    apply.disabled = sameAsSaved(now);
    menu.classList.toggle("is-dirty", !sameAsSaved(now));
  };

  const search = () => {
    const query = filter.value.trim().toLowerCase();
    options.forEach((option) => {
      option.hidden = query !== "" && !option.dataset.columnLabel.includes(query);
    });
    groups.forEach((group) => {
      group.hidden = ![...group.querySelectorAll("[data-column-option]")].some((option) => !option.hidden);
    });
    empty.hidden = groups.some((group) => !group.hidden);
  };

  const revert = () => {
    boxes.forEach((box) => { box.checked = saved.has(box.value); });
    filter.value = "";
    search();
    sync();
  };

  boxes.forEach((box) => box.addEventListener("change", sync));
  filter.addEventListener("input", search);
  filter.addEventListener("keydown", (event) => {
    if (event.key === "Enter") event.preventDefault();
    if (event.key === "Escape" && filter.value !== "") {
      event.stopPropagation();
      filter.value = "";
      search();
    }
  });

  menu.querySelectorAll("[data-column-all], [data-column-none]").forEach((button) => {
    button.addEventListener("click", () => {
      const checked = button.hasAttribute("data-column-all");
      button.closest("[data-column-group]")
        .querySelectorAll("[data-column-option]:not([hidden]) input[type=checkbox]")
        .forEach((box) => { box.checked = checked; });
      sync();
    });
  });

  menu.querySelector("[data-column-reset]").addEventListener("click", () => {
    filter.value = "";
    search();
    boxes.forEach((box) => { box.checked = defaults.has(box.value); });
    sync();
  });

  menu.querySelector("[data-column-cancel]").addEventListener("click", () => {
    bootstrap.Dropdown.getOrCreateInstance(toggle).hide();
  });

  const panel = menu.querySelector(".column-menu__panel");
  const head = menu.querySelector(".column-menu__head");
  const foot = menu.querySelector(".column-menu__foot");
  const GAP = 12;
  const TALLEST = 560;
  const MIN_LIST = 220;

  const place = () => {
    const anchor = toggle.getBoundingClientRect();
    const chrome = head.offsetHeight + foot.offsetHeight;
    const below = window.innerHeight - anchor.bottom - GAP;
    const above = anchor.top - GAP;
    panel.classList.remove("column-menu__panel--above", "column-menu__panel--pinned");
    panel.style.top = "";
    panel.style.left = "";
    panel.style.transform = "";

    if (Math.max(below, above) >= chrome + MIN_LIST) {
      const useAbove = below < chrome + MIN_LIST;
      panel.classList.toggle("column-menu__panel--above", useAbove);
      panel.style.maxHeight = `${Math.min(TALLEST, useAbove ? above : below)}px`;
      const box = panel.getBoundingClientRect();
      const nudge = box.left < GAP
        ? GAP - box.left
        : Math.min(0, window.innerWidth - GAP - box.right);
      if (nudge) panel.style.transform = `translateX(${Math.round(nudge)}px)`;
      return;
    }

    panel.classList.add("column-menu__panel--pinned");
    panel.style.maxHeight = `${window.innerHeight - GAP * 2}px`;
    panel.style.top = `${GAP}px`;
    panel.style.left = `${Math.min(
      Math.max(GAP, anchor.right - panel.offsetWidth),
      window.innerWidth - panel.offsetWidth - GAP,
    )}px`;
  };

  toggle.addEventListener("hidden.bs.dropdown", () => {
    panel.style.maxHeight = "";
    revert();
  });
  toggle.addEventListener("shown.bs.dropdown", () => {
    place();
    filter.focus();
  });
  ["resize", "scroll"].forEach((event) => {
    window.addEventListener(event, () => {
      if (panel.classList.contains("show")) place();
    }, {passive: true});
  });

  sync();
})();
