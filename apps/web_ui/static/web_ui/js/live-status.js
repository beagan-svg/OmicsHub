(() => {
  const cells = () => [...document.querySelectorAll("[data-live-stage-status]")];
  const mapping = {
    COMPLETED: "done",
    ARCHIVED: "done",
    INGEST_COMPLETE: "done",
    SUBMITTED: "running",
    SUBMITTING: "running",
    IN_PROGRESS: "running",
    PENDING: "queued",
    AWAITING_TRIGGER: "queued",
    CANCELLED: "queued",
    FAILED: "fail",
    ABORTED: "fail",
  };
  let inFlight = false;

  const update = (cell, status) => {
    const badge = cell.querySelector(".state");
    if (!badge) return;
    badge.textContent = status;
    badge.dataset.state = mapping[status] || "unknown";
  };

  const refresh = async () => {
    if (inFlight || document.hidden) return;
    const visibleCells = cells();
    const names = [...new Set(visibleCells.map((cell) => cell.dataset.liveStageStatus.split("|")[0]))];
    if (!names.length) return;
    const url = document.querySelector("[data-live-status-url]")?.dataset.liveStatusUrl;
    if (!url) return;
    inFlight = true;
    const query = new URLSearchParams();
    names.forEach((name) => query.append("fastq_names", name));
    try {
      const response = await fetch(`${url}?${query}`, {headers: {"X-Requested-With": "XMLHttpRequest"}});
      if (!response.ok) return;
      const rows = (await response.json()).rows;
      visibleCells.forEach((cell) => {
        const [name, stage] = cell.dataset.liveStageStatus.split("|");
        update(cell, rows[name]?.[stage]?.status || "NOT COMPLETED");
      });
    } catch {
      // Keep the last database values when a local poll cannot reach Django.
    } finally {
      inFlight = false;
    }
  };

  const host = document.querySelector("[data-live-status-url]");
  if (!host) return;
  refresh();
  window.setInterval(refresh, Number(host.dataset.liveStatusInterval || 30000));
})();
