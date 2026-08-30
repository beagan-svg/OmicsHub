// Pins a page's selection-summary/pagination footer to the bottom of the screen on mobile,
// the way a native list view keeps its selection toolbar reachable without scrolling to it --
// rather than leaving it as one more section at the end of a long scrolling page. Desktop is
// untouched: outside the mobile breakpoint this never moves or resizes anything.
(() => {
  const bar = document.querySelector("[data-mobile-footer-bar]");
  if (!bar) return;

  const home = {parent: bar.parentNode, next: bar.nextSibling};
  const mq = window.matchMedia("(max-width: 767.98px)");

  // The bar's own height varies (a cart confirmation message appearing adds a line, and
  // Dashboard's bar is taller than Data Locations' to begin with), so this is measured
  // rather than assumed -- table-scroll's mobile max-height reads the same variable to
  // leave exactly enough room for whatever the bar's current height actually is.
  const setHeightVar = () => {
    document.documentElement.style.setProperty(
      "--mobile-footer-bar-height",
      isMobile ? `${bar.offsetHeight}px` : "0px",
    );
  };
  const resizeObserver = new ResizeObserver(setHeightVar);

  let isMobile = null;

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
      resizeObserver.observe(bar);
    } else {
      resizeObserver.unobserve(bar);
      bar.classList.remove("mobile-footer-bar--fixed");
      home.parent.insertBefore(bar, home.next);
    }
    setHeightVar();
  }

  apply();
  mq.addEventListener("change", apply);
  window.addEventListener("resize", apply, {passive: true});
})();
