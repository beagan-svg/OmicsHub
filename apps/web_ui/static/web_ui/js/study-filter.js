document.querySelectorAll("[data-study-toggle]").forEach((toggle) => {
  const menu = toggle.nextElementSibling;
  if (!menu) return;

  const options = () => [...menu.querySelectorAll(".study-filter__option")];
  const summary = toggle.querySelector("[data-study-summary]");
  const menuSummary = menu.querySelector("[data-study-menu-summary]");
  const action = menu.querySelector("[data-study-action]");
  const filterLabel = menu.dataset.filterLabel || "study sets";

  const updateSummary = () => {
    const allOptions = options();
    const selected = allOptions.filter((option) => option.checked).length;
    const allSelected = allOptions.length > 0 && selected === allOptions.length;
    if (summary) summary.textContent = selected ? `${selected} selected` : "All";
    if (menuSummary) menuSummary.textContent = selected ? `${selected} selected` : `All ${filterLabel}`;
    if (action) {
      action.textContent = allSelected ? "Select none" : "Select all";
      action.setAttribute("aria-label", allSelected ? `Select no ${filterLabel}` : `Select all ${filterLabel}`);
      action.disabled = allOptions.length === 0;
    }
  };

  action?.addEventListener("click", () => {
    const allOptions = options();
    const allSelected = allOptions.length > 0 && allOptions.every((option) => option.checked);
    allOptions.forEach((option) => { option.checked = !allSelected; });
    updateSummary();
  });
  options().forEach((option) => option.addEventListener("change", updateSummary));
});
