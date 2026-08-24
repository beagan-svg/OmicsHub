document.querySelectorAll("[data-tabs]").forEach((group) => {
  const name = group.dataset.tabs;
  const buttons = group.querySelectorAll("[data-tab-value]");
  const panels = document.querySelectorAll(`[data-tab-group="${name}"]`);

  const activate = (value) => {
    buttons.forEach((button) => {
      const active = button.dataset.tabValue === value;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.tabPanel !== value;
    });
  };

  buttons.forEach((button) => {
    button.addEventListener("click", () => activate(button.dataset.tabValue));
  });
});
