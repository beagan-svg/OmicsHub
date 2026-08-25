// Delegated on `document`, not bound per-element at load: a toggle inside content that
// gets replaced wholesale later (the Job Monitor and Failures pages' periodic table
// refresh does exactly this, via innerHTML) would otherwise end up as a fresh DOM node
// with no listener at all -- a click on it would silently do nothing forever after the
// first refresh. Delegation means it doesn't matter when or how a `[data-disclosure]`
// element entered the page; the listener that fires is looked up at click time.
const setOrigin = (toggle, panel) => {
  const button = toggle.getBoundingClientRect();
  const box = panel.getBoundingClientRect();
  panel.style.setProperty("--origin-x", `${button.left + button.width / 2 - box.left}px`);
};

document.addEventListener("click", (event) => {
  const toggle = event.target.closest("[data-disclosure]");
  if (!toggle) return;
  const panel = document.getElementById(toggle.dataset.disclosure);
  if (!panel) return;

  const open = panel.dataset.open !== "true";
  setOrigin(toggle, panel);
  panel.dataset.open = String(open);
  toggle.setAttribute("aria-expanded", String(open));
});

// Keeps the grow-from-click-position animation origin correct on resize, for whichever
// panels happen to be open right now -- re-queried each time rather than captured once,
// for the same reason the click handler above is delegated.
window.addEventListener(
  "resize",
  () => {
    document.querySelectorAll("[data-disclosure]").forEach((toggle) => {
      const panel = document.getElementById(toggle.dataset.disclosure);
      if (panel && panel.dataset.open === "true") {
        setOrigin(toggle, panel);
      }
    });
  },
  {passive: true}
);
