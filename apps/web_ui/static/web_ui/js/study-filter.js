document.querySelectorAll("[data-study-toggle]").forEach((toggle) => {
  const menu = toggle.nextElementSibling;
  if (!menu) return;

  const options = () => [...menu.querySelectorAll(".study-filter__option")];
  const summary = toggle.querySelector("[data-study-summary]");
  const menuSummary = menu.querySelector("[data-study-menu-summary]");
  const action = menu.querySelector("[data-study-action]");

  const updateSummary = () => {
    const allOptions = options();
    const selected = allOptions.filter((option) => option.checked).length;
    const allSelected = allOptions.length > 0 && selected === allOptions.length;
    if (summary) summary.textContent = selected ? `${selected} selected` : "all";
    if (menuSummary) menuSummary.textContent = selected ? `${selected} selected` : "All study sets";
    if (action) {
      action.textContent = allSelected ? "Select none" : "Select all";
      action.setAttribute("aria-label", allSelected ? "Select no study sets" : "Select all study sets");
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
