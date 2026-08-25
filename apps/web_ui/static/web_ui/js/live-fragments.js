(() => {
  document.querySelectorAll("[data-live-fragment]").forEach((region) => {
    let inFlight = false;
    const refresh = async () => {
      if (inFlight || document.hidden) return;
      inFlight = true;
      try {
        const response = await fetch(region.dataset.liveFragmentUrl, {
          headers: {"X-Requested-With": "XMLHttpRequest"},
        });
        if (response.ok) {
          const documentText = await response.text();
          const parsed = new DOMParser().parseFromString(documentText, "text/html");
          const replacement = parsed.querySelector(`#${region.id}`);
          if (replacement) {
            const openDetails = [...region.querySelectorAll("details[open]")]
              .map((detail) => detail.dataset.liveDetail)
              .filter(Boolean);
            // Capture the panel state immediately before replacement so a click made
            // while the request was in flight is not overwritten by an old snapshot.
            const openLogPanels = new Map(
              [...region.querySelectorAll('[data-job-log-panel][data-open="true"]')].map((panel) => [
                panel.dataset.demandId,
                panel.querySelector("[data-job-log-body]")?.innerHTML || "",
              ]),
            );
            region.dispatchEvent(new CustomEvent("joblog:before-refresh", {bubbles: true}));
            region.innerHTML = replacement.innerHTML;
            region.querySelectorAll("details").forEach((detail) => {
              if (openDetails.includes(detail.dataset.liveDetail)) {
                detail.open = true;
              }
            });
            region.querySelectorAll("[data-job-log-panel]").forEach((panel) => {
              const body = openLogPanels.get(panel.dataset.demandId);
              if (body !== undefined) {
                panel.dataset.open = "true";
                const panelBody = panel.querySelector("[data-job-log-body]");
                if (panelBody) panelBody.innerHTML = body;
                const toggle = region.querySelector(
                  `[data-job-log-toggle][data-demand-id="${panel.dataset.demandId}"]`
                );
                if (toggle) toggle.setAttribute("aria-expanded", "true");
              }
            });
            region.dispatchEvent(new CustomEvent("joblog:refreshed", {bubbles: true}));
          }
        }
      } catch {
        // Keep the last successful fragment when Django cannot be reached.
      } finally {
        inFlight = false;
      }
    };
    window.setInterval(refresh, Number(region.dataset.liveFragmentInterval || 30000));
  });
})();
