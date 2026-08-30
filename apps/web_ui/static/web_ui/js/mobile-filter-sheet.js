// Consolidates a page's scattered filter/action controls (Study Set, More Filters, Clear,
// Apply, Columns, Export CSV) into one bottom sheet on mobile, leaving desktop's toolbar
// exactly as it already renders. Elements aren't duplicated: this relocates the same DOM
// nodes (and any listeners already bound to them) between their desktop position and the
// sheet, so existing behavior -- form submission, the disclosure toggle, the column menu --
// keeps working unmodified regardless of where the node currently lives.
(() => {
  const root = document.querySelector("[data-mobile-filter-root]");
  const sheet = document.getElementById("mobile-filter-sheet");
  if (!root || !sheet) return;

  // .mobile-filter-sheet is meant to cover the full viewport (position: fixed; inset: 0),
  // but the toolbar it's included next to lives inside .card, which sets `contain: layout`
  // (see that rule's own comment) -- and `contain: layout` on an ancestor, like a
  // transform would, gives fixed-position descendants a new containing block scoped to
  // that ancestor's box instead of the viewport. Moving the sheet to be a direct child of
  // body sidesteps that entirely, which is the standard place for an overlay anyway.
  document.body.append(sheet);

  const body = sheet.querySelector("[data-mobile-filter-body]");
  const footer = sheet.querySelector("[data-mobile-filter-footer]");
  const toolbarSlot = document.querySelector("[data-mobile-filter-toolbar-slot]");
  const trigger = document.querySelector("[data-mobile-filter-open]");
  const mq = window.matchMedia("(max-width: 767.98px)");

  // Sheet order (Study Set/Stages, then Columns [and Rows per page, marked from the table
  // pager below the table rather than the toolbar above it], then More Filters) is
  // independent of the desktop toolbar's own DOM order, driven by each element's
  // data-mobile-order instead of where it happens to sit in the template. Array.sort is
  // stable, so elements sharing an order keep their original relative order. Queried from
  // `document`, not `root` (the filter toolbar), since a marked element -- Rows per page --
  // can live outside it, in the footer below the table.
  const bodyItems = [...document.querySelectorAll('[data-mobile-move="sheet-body"]')].sort(
    (a, b) => Number(a.dataset.mobileOrder || 0) - Number(b.dataset.mobileOrder || 0),
  );
  const footerItems = [...document.querySelectorAll('[data-mobile-move="sheet-footer"]')];
  const toolbarItems = [...document.querySelectorAll('[data-mobile-move="toolbar"]')];

  // An advanced-filters disclosure panel travels with its own "More Filters" toggle,
  // found through the toggle's existing data-disclosure attribute rather than a second
  // marker -- disclosure.js looks the panel up by id at click time regardless of where
  // in the DOM either element lives, so moving both together (right after the toggle, so
  // expanding it doesn't visually jump to the wrong spot) is enough to keep it working.
  for (let i = bodyItems.length - 1; i >= 0; i -= 1) {
    const toggle = bodyItems[i].querySelector("[data-disclosure]");
    const panel = toggle && document.getElementById(toggle.dataset.disclosure);
    if (panel && !bodyItems.includes(panel)) bodyItems.splice(i + 1, 0, panel);
  }

  // Recorded once, before anything moves, so a real desktop resize (not just a phone
  // rotating) can put every element back exactly where the template rendered it.
  const homes = new Map();
  [...bodyItems, ...footerItems, ...toolbarItems].forEach((el) => {
    homes.set(el, {parent: el.parentNode, next: el.nextSibling});
  });

  let isMobile = null;

  function apply() {
    if (mq.matches === isMobile) return;
    isMobile = mq.matches;
    if (isMobile) {
      bodyItems.forEach((el) => body.append(el));
      if (footer) footerItems.forEach((el) => footer.append(el));
      if (toolbarSlot) toolbarItems.forEach((el) => toolbarSlot.append(el));
    } else {
      homes.forEach((home, el) => home.parent.insertBefore(el, home.next));
      closeSheet();
    }
  }

  function openSheet() {
    sheet.hidden = false;
    trigger?.setAttribute("aria-expanded", "true");
    document.body.classList.add("mobile-filter-sheet-open");
  }

  function closeSheet() {
    if (sheet.hidden) return;
    sheet.classList.add("is-closing");
    trigger?.setAttribute("aria-expanded", "false");
    document.body.classList.remove("mobile-filter-sheet-open");
    // Matches --t-panel: long enough for the slide/fade-out to finish before this removes
    // the sheet from the render tree; a second call while one is already pending would
    // otherwise double up and hide it early.
    window.setTimeout(() => {
      sheet.hidden = true;
      sheet.classList.remove("is-closing");
    }, 300);
  }

  trigger?.addEventListener("click", openSheet);
  sheet.querySelectorAll("[data-mobile-filter-close]").forEach((el) => {
    el.addEventListener("click", closeSheet);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !sheet.hidden) closeSheet();
  });

  apply();
  mq.addEventListener("change", apply);
  // Belt-and-suspenders alongside the matchMedia listener above: apply() no-ops unless
  // mq.matches actually flipped, so a plain resize (a desktop window dragged across the
  // breakpoint, not just a phone) still gets picked up even in a context where the
  // "change" event on the MediaQueryList doesn't fire for some reason.
  window.addEventListener("resize", apply, {passive: true});
})();
