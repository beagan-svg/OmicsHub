(() => {
  document.querySelectorAll("[data-live-fragment]").forEach((region) => {
    let inFlight = false;
    const refresh = async () => {
      if (inFlight || document.hidden) return;
      inFlight = true;
      const openDetails = [...region.querySelectorAll("details[open]")]
        .map((detail) => detail.dataset.liveDetail)
        .filter(Boolean);
      try {
        const response = await fetch(region.dataset.liveFragmentUrl, {
          headers: {"X-Requested-With": "XMLHttpRequest"},
        });
        if (response.ok) {
          const documentText = await response.text();
          const parsed = new DOMParser().parseFromString(documentText, "text/html");
          const replacement = parsed.querySelector(`#${region.id}`);
          if (replacement) {
            region.innerHTML = replacement.innerHTML;
            region.querySelectorAll("details").forEach((detail) => {
              if (openDetails.includes(detail.dataset.liveDetail)) {
                detail.open = true;
              }
            });
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
