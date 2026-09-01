// Native <select> filters (e.g. Data Locations' Stages filter) render their own selected
// <option>'s raw text inside the box -- there is no cross-browser CSS way to override
// that text. Where that raw text needs to read differently inside the mobile Filters
// sheet (see .filter-field__select-decoy in web_ui.css) than it needs to on desktop
// (Stages' own option text is "Stages: All" because desktop has no separate visible
// label for it -- see the comment in data_locations.html), this keeps a plain decorative
// element in sync with the real select's value via its `change` event and on load. The
// real select stays functionally present and on top (still the native picker, the real
// accessible name, real change/submit behavior) -- this only paints a cleaned-up value
// behind it.
(() => {
  document.querySelectorAll("[data-select-decoy-source]").forEach((select) => {
    const decoy = select.parentElement.querySelector("[data-select-decoy-value]");
    if (!decoy) return;
    // Strips a redundant "Label: " prefix some option text carries only for desktop's
    // benefit (no separate visible label there). Options with no such prefix (e.g. a
    // per-stage status value) pass through unchanged.
    const clean = (text) => text.replace(/^[^:]+:\s*/, "");
    const sync = () => {
      const option = select.options[select.selectedIndex];
      decoy.textContent = option ? clean(option.text) : "";
    };
    sync();
    select.addEventListener("change", sync);
  });
})();
