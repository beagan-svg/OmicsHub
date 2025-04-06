/**
 * Status Time Toggle Debugger
 * This script fixes issues with Status Time category toggles
 */

document.addEventListener('DOMContentLoaded', function () {
    console.log("Status Time Debug - Loading");

    // Find all time-related toggles
    const timeToggles = document.querySelectorAll('[id^="toggle"][id$="Time"]');
    console.log(`Found ${timeToggles.length} time-related toggles`);

    // Log initial state of each toggle
    timeToggles.forEach(toggle => {
        console.log(`Toggle ${toggle.id}: checked=${toggle.checked}, visible=${isColumnVisible(toggle)}`);

        // Ensure event listeners are properly set up
        toggle.addEventListener('change', function (event) {
            console.log(`Time toggle changed: ${toggle.id} -> ${toggle.checked}`);
            const columnClass = getColumnClassFromToggle(toggle);
            if (columnClass) {
                applyTimeColumnVisibility(columnClass, toggle.checked);

                // Save to localStorage
                const storageKey = `show${snakeToCamelCase(columnClass)}`;
                localStorage.setItem(storageKey, toggle.checked);

                // Show feedback
                const label = toggle.closest('.form-check')?.querySelector('.form-check-label');
                const title = label ? label.textContent.trim() : toggle.id;
                showFeedbackMessage(`${title} ${toggle.checked ? 'shown' : 'hidden'}`);
            } else {
                console.error(`Could not find column class for toggle: ${toggle.id}`);
            }
        });
    });

    // Add a click handler to the Status Time category header for testing
    const statusTimeHeader = document.querySelector('.column-category h6:contains("Status Time")');
    if (statusTimeHeader) {
        statusTimeHeader.style.cursor = 'pointer';
        statusTimeHeader.addEventListener('click', function () {
            console.log("Status Time header clicked - Toggling all time columns");
            const allTimeTogglesOn = Array.from(timeToggles).every(t => t.checked);

            // Toggle all time toggles to the opposite state
            timeToggles.forEach(toggle => {
                toggle.checked = !allTimeTogglesOn;
                toggle.dispatchEvent(new Event('change'));
            });
        });
    }

    /**
     * Get column class from toggle element
     */
    function getColumnClassFromToggle(toggle) {
        // First check for data-column attribute
        if (toggle.dataset.column) {
            return toggle.dataset.column;
        }

        // Fall back to converting from ID
        const toggleId = toggle.id;
        if (toggleId.startsWith('toggle')) {
            // Convert camelCase to snake_case (e.g. toggleIngestStartTime -> column-ingest_start_time)
            return `column-${camelToSnakeCase(toggleId.replace('toggle', '')).toLowerCase()}`;
        }

        return null;
    }

    /**
     * Check if a column is currently visible
     */
    function isColumnVisible(toggle) {
        const columnClass = getColumnClassFromToggle(toggle);
        if (!columnClass) return false;

        const cell = document.querySelector(`.${columnClass}`);
        return cell && window.getComputedStyle(cell).display !== 'none';
    }

    /**
     * Apply visibility change to time column
     */
    function applyTimeColumnVisibility(columnClass, isVisible) {
        console.log(`Applying visibility for ${columnClass}: ${isVisible}`);

        // Find all cells with this class (both th and td)
        const cells = document.querySelectorAll(`.${columnClass}`);

        cells.forEach(cell => {
            if (isVisible) {
                cell.style.display = '';
                cell.style.opacity = '1';
                cell.style.width = '';
            } else {
                cell.style.opacity = '0';
                cell.style.width = '0';
                setTimeout(() => {
                    cell.style.display = 'none';
                }, 300);
            }
        });
    }

    /**
     * Show feedback message to user
     */
    function showFeedbackMessage(message) {
        console.log(`Toggle feedback: ${message}`);

        let feedbackElement = document.querySelector('.toggle-feedback');

        if (!feedbackElement) {
            feedbackElement = document.createElement('div');
            feedbackElement.className = 'toggle-feedback';
            document.body.appendChild(feedbackElement);
        }

        feedbackElement.textContent = message;
        feedbackElement.classList.add('show');

        setTimeout(() => {
            feedbackElement.classList.remove('show');
        }, 2000);
    }

    /**
     * Utility: Convert camelCase to snake_case
     */
    function camelToSnakeCase(str) {
        return str
            .replace(/([a-z])([A-Z])/g, '$1_$2')
            .toLowerCase();
    }

    /**
     * Utility: Convert snake_case to camelCase
     */
    function snakeToCamelCase(str) {
        return str
            .replace('column-', '')
            .toLowerCase()
            .replace(/_([a-z])/g, (_, char) => char.toUpperCase());
    }

    // Define a custom "contains" selector for jQuery-like functionality
    if (!Element.prototype.matches) {
        Element.prototype.matches = Element.prototype.msMatchesSelector || Element.prototype.webkitMatchesSelector;
    }

    if (!document.querySelector(':contains')) {
        document.querySelectorAll = (function (querySelectorAll) {
            return function (selector) {
                if (selector.indexOf(':contains') > -1) {
                    const parts = selector.split(':contains');
                    const baseSelector = parts[0];
                    const textToMatch = parts[1].replace(/["'()]/g, '');

                    const elements = querySelectorAll.call(this, baseSelector);
                    return Array.from(elements).filter(el =>
                        el.textContent.indexOf(textToMatch) > -1
                    );
                }
                return querySelectorAll.call(this, selector);
            };
        })(document.querySelectorAll);
    }

    console.log("Status Time Debug - Initialized");
}); 