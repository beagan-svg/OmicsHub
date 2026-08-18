document.querySelectorAll("[data-disclosure]").forEach((toggle) => {
  const panel = document.getElementById(toggle.dataset.disclosure);
  if (!panel) return;

  const setOrigin = () => {
    const button = toggle.getBoundingClientRect();
    const box = panel.getBoundingClientRect();
    panel.style.setProperty("--origin-x", `${button.left + button.width / 2 - box.left}px`);
  };

  setOrigin();
  window.addEventListener("resize", setOrigin, {passive: true});
  toggle.addEventListener("click", () => {
    const open = panel.dataset.open !== "true";
    setOrigin();
    panel.dataset.open = String(open);
    toggle.setAttribute("aria-expanded", String(open));
  });
});
