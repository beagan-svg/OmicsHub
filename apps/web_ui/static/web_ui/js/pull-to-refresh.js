// A native-feeling pull-to-refresh gesture for mobile, replacing the standalone "Refresh"
// button/row that used to sit in the toolbar (see .toolbar-sync in web_ui.css, which hides
// that button and its sync pill on mobile). It proxies to the exact same refresh mechanism
// that button already posted to -- [data-mobile-refresh-form], the page's existing hidden
// refresh-status form -- so there's no new backend behavior here, only a different,
// native-styled way to trigger it. Desktop keeps the explicit button; this only runs below
// the mobile breakpoint, and only on pages that actually have a refresh form to submit
// (most don't, and no-op harmlessly).
(() => {
  const form = document.querySelector("[data-mobile-refresh-form]");
  if (!form) return;

  const mq = window.matchMedia("(max-width: 767.98px)");

  const indicator = document.createElement("div");
  indicator.className = "pull-refresh-indicator";
  indicator.setAttribute("aria-hidden", "true");
  indicator.innerHTML = '<i class="bi bi-arrow-clockwise" aria-hidden="true"></i>';
  document.body.prepend(indicator);

  const THRESHOLD = 64;
  const scroller = () => document.scrollingElement || document.documentElement;

  // These listeners are on `document`, so a downward drag inside the mobile Filters
  // sheet's own scrollable body -- itself a full-screen overlay, easy to open while the
  // underlying page happens to be scrolled to the top -- would otherwise read as a
  // page-level pull-to-refresh: the indicator would render on top of the open sheet
  // (it's a higher z-index), and releasing past the threshold would submit the refresh
  // form, reloading the whole page and silently discarding whatever the reader hadn't
  // applied yet. mobile-filter-sheet.js adds this class to <body> for exactly as long as
  // the sheet is open, so checking it here is what keeps the two gestures from colliding.
  function sheetOpen() {
    return document.body.classList.contains("mobile-filter-sheet-open");
  }

  let startY = null;
  let pulling = false;
  let armed = false;
  let triggered = false;
  // Set by the touchmove listener, applied to the DOM by the rAF callback -- coalesces
  // however many touchmove events fire within one frame (which can be far more than one
  // on a fast drag) into a single style write instead of one per event.
  let pendingPull = null;
  let frameQueued = false;

  function atTop() {
    return scroller().scrollTop <= 0;
  }

  function applyPull() {
    frameQueued = false;
    if (pendingPull === null) return;
    const {pull, isArmed} = pendingPull;
    indicator.classList.add("is-pulling");
    indicator.classList.toggle("is-armed", isArmed);
    indicator.style.setProperty("--pull", `${pull}px`);
  }

  function reset() {
    indicator.classList.remove("is-pulling", "is-armed");
    indicator.style.removeProperty("--pull");
    pulling = false;
    armed = false;
    startY = null;
    pendingPull = null;
  }

  document.addEventListener("touchstart", (event) => {
    if (!mq.matches || triggered || sheetOpen() || event.touches.length !== 1) return;
    startY = atTop() ? event.touches[0].clientY : null;
  }, {passive: true});

  document.addEventListener("touchmove", (event) => {
    if (startY === null || triggered) return;
    if (sheetOpen()) {
      reset();
      return;
    }
    const delta = event.touches[0].clientY - startY;
    if (delta <= 0 || !atTop()) {
      reset();
      return;
    }
    pulling = true;
    const pull = Math.min(delta * 0.5, THRESHOLD * 1.5);
    armed = pull >= THRESHOLD;
    pendingPull = {pull, isArmed: armed};
    if (!frameQueued) {
      frameQueued = true;
      requestAnimationFrame(applyPull);
    }
  }, {passive: true});

  document.addEventListener("touchend", () => {
    if (!pulling) {
      reset();
      return;
    }
    const shouldRefresh = armed;
    reset();
    if (shouldRefresh) {
      triggered = true;
      indicator.classList.add("is-loading");
      // The form's own submit reloads the page with fresh rows, same as the button it
      // replaces -- there's nothing to reset the indicator back from, since navigation
      // away starts immediately after.
      form.requestSubmit();
    }
  }, {passive: true});
})();
