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

  // Toggling every row through "select all" dispatches one "change" per row (see the
  // header comment), and each dispatch would otherwise re-scan every row in the group to
  // recompute this same checked/indeterminate state -- O(rows) work done once per row
  // toggled, so O(rows²) for a full select-all on a large table. Queuing it as a
  // microtask instead collapses however many rows changed in this pass into a single
  // recompute, since microtasks run once after the current synchronous work finishes,
  // not once per event.
  let updateQueued = false;
  const queueUpdate = () => {
    if (updateQueued) return;
    updateQueued = true;
    queueMicrotask(() => {
      updateQueued = false;
      update();
    });
  };

  rows().forEach((box) => box.addEventListener("change", queueUpdate));

  selectAll.addEventListener("change", () => {
    // Captured once rather than read fresh inside the loop below, in case a row's own
    // "change" listener (a page's, not this file's) ever reaches back and touches
    // selectAll.checked itself -- comparing against a live property could then compare
    // each row against whatever an earlier row's dispatch left it at, not the click that
    // started this.
    const target = selectAll.checked;
    rows().forEach((box) => {
      if (box.checked === target) return;
      box.checked = target;
      box.dispatchEvent(new Event("change", { bubbles: true }));
    });
    // queueUpdate, not update: every dispatched row above already queued the same
    // microtask, so calling the synchronous version here on top would recompute the
    // checked/indeterminate state twice for one click.
    queueUpdate();
  });

  update();
});
