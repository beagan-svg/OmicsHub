// A "select all" checkbox paired with the per-row checkboxes sharing its
// data-tristate-group name. Owns exactly the checked/indeterminate bookkeeping and
// "select all toggles every row" mechanic that the dashboard's sample table and
// checkout's cart table were each hand-rolling identically. Toggling a row through
// select-all dispatches a real "change" event on it, so whatever a page already listens
// for on that row (staging it for the cart, tracking it for submission) fires exactly as
// it would from a direct click, with no separate bulk-toggle code path to keep in sync.
document.querySelectorAll("[data-tristate-group]").forEach((selectAll) => {
  const group = selectAll.dataset.tristateGroup;
  const rows = () => document.querySelectorAll(`[data-tristate-row="${group}"]`);

  const update = () => {
    const boxes = [...rows()];
    const checkedCount = boxes.filter((box) => box.checked).length;
    selectAll.checked = boxes.length > 0 && checkedCount === boxes.length;
    selectAll.indeterminate = checkedCount > 0 && checkedCount < boxes.length;
  };

  rows().forEach((box) => box.addEventListener("change", update));

  selectAll.addEventListener("change", () => {
    // Captured once: a row's own "change" listener can be `update` itself (added below),
    // which reads and rewrites selectAll.checked as each row is dispatched. Comparing
    // against the live property here would compare each row against whatever the
    // previous row's dispatch just left it at, not against the click that started this.
    const target = selectAll.checked;
    rows().forEach((box) => {
      if (box.checked === target) return;
      box.checked = target;
      box.dispatchEvent(new Event("change", { bubbles: true }));
    });
    update();
  });

  update();
});
