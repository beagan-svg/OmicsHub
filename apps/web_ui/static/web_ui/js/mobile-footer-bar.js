// Pins a page's selection-summary/pagination footer to the bottom of the screen on mobile,
// the way a native list view keeps its selection toolbar reachable without scrolling to it --
// rather than leaving it as one more section at the end of a long scrolling page. Desktop is
// untouched: outside the mobile breakpoint this never moves or resizes anything.
(() => {
  const bar = document.querySelector("[data-mobile-footer-bar]");
  if (!bar) return;

  const home = {parent: bar.parentNode, next: bar.nextSibling};
  const mq = window.matchMedia("(max-width: 767.98px)");
  // The scrollable table area on this page, if it has one (Configs and other pages this
  // script also runs on harmlessly don't). Its own mobile max-height used to be a flat
  // `100svh minus a guessed constant`, which assumed a fixed amount of chrome above it --
  // wrong the moment that chrome's real height differs (a longer page description, a
  // second toolbar row), and silently wrong in a way that reads as "the bar covers the
  // table" rather than an obvious error. Measuring both the bar's real height and the
  // table's real on-screen position and computing what's actually left avoids guessing
  // entirely.
  const tableScroll = document.querySelector(".table-scroll");

  let isMobile = null;

  function layout() {
    document.documentElement.style.setProperty(
      "--mobile-footer-bar-height",
      isMobile ? `${bar.offsetHeight}px` : "0px",
    );
    if (!tableScroll) return;
    if (!isMobile) {
      tableScroll.style.maxHeight = "";
      return;
    }
    const GAP = 12;
    const top = tableScroll.getBoundingClientRect().top;
    const available = window.innerHeight - top - bar.offsetHeight - GAP;
    // No floor under this: a floor that ignores what's actually left is exactly how the
    // bar ended up covering the table in the first place. A cramped table is a real
    // problem to go fix (a shorter bar, less chrome above it) -- not one to paper over
    // here by claiming space back that isn't there, which just brings the overlap back.
    tableScroll.style.maxHeight = `${Math.max(0, available)}px`;
  }

  // Refires on anything that can change how much vertical room is left: the bar's own
  // height (a cart confirmation message adds a line; Dashboard's bar starts taller than
  // Data Locations' to begin with) and whatever sits above the table (a sync-status pill
  // wrapping differently, a filter row changing height).
  const resizeObserver = new ResizeObserver(layout);

  function apply() {
    if (mq.matches === isMobile) return;
    isMobile = mq.matches;
    if (isMobile) {
      // Same reason mobile-filter-sheet.js moves its own overlay to body: the bar's
      // current position is inside .card, which sets `contain: layout`, and that gives
      // `position: fixed` descendants a containing block scoped to the card's own box
      // instead of the viewport.
      document.body.append(bar);
      bar.classList.add("mobile-footer-bar--fixed");
    } else {
      bar.classList.remove("mobile-footer-bar--fixed");
      home.parent.insertBefore(bar, home.next);
    }
    layout();
  }

  apply();
  // Only the bar itself is observed here, not anything above the table: that would
  // include table-scroll's own box in most page layouts, and setting its max-height in
  // layout() changes that box's size -- feeding straight back into the observer in a loop.
  resizeObserver.observe(bar);
  mq.addEventListener("change", apply);
  window.addEventListener("resize", apply, {passive: true});
})();
