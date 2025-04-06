/**
 * Status Time Toggle Debugger
 * This script fixes issues with Status Time category toggles
 */

document.addEventListener('DOMContentLoaded', function () {
    console.log("Status Time Debug - Loading");

    // Find all time-related toggles
    const timeToggles = document.querySelectorAll('[id^="toggle"][id$="Time"]');
    console.log(`Found ${timeToggles.length} time-related toggles`);

    // Add a debugging button to inspect the table state
    addDebugControls();

    // Log initial state of each toggle
    timeToggles.forEach(toggle => {
        console.log(`Toggle ${toggle.id}: checked=${toggle.checked}, visible=${isColumnVisible(toggle)}`);
        validateColumnClasses(toggle);

        // Ensure event listeners are properly set up - override any existing listeners
        toggle.addEventListener('click', function (event) {
            // Stop event propagation to prevent multiple handlers
            event.stopPropagation();

            console.log(`Time toggle clicked: ${toggle.id} -> ${toggle.checked}`);
            const columnClass = getColumnClassFromToggle(toggle);

            if (columnClass) {
                // Force toggle the column visibility directly
                forceColumnVisibility(columnClass, toggle.checked);

                // Save to localStorage
                const storageKey = `show${snakeToCamelCase(columnClass)}`;
                localStorage.setItem(storageKey, toggle.checked);
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
                const columnClass = getColumnClassFromToggle(toggle);
                if (columnClass) {
                    forceColumnVisibility(columnClass, toggle.checked);

                    // Save to localStorage
                    const storageKey = `show${snakeToCamelCase(columnClass)}`;
                    localStorage.setItem(storageKey, toggle.checked);
                }
            });
        });
    }

    /**
     * Add debug controls to the page
     */
    function addDebugControls() {
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'debug-controls';
        controlsDiv.style.position = 'fixed';
        controlsDiv.style.bottom = '10px';
        controlsDiv.style.left = '10px';
        controlsDiv.style.zIndex = '9999';
        controlsDiv.style.display = 'flex';
        controlsDiv.style.flexDirection = 'column';
        controlsDiv.style.gap = '5px';

        // Inspect Table Button
        const inspectButton = document.createElement('button');
        inspectButton.innerText = 'Inspect Table';
        inspectButton.style.padding = '5px 10px';
        inspectButton.style.backgroundColor = '#007bff';
        inspectButton.style.color = 'white';
        inspectButton.style.border = 'none';
        inspectButton.style.borderRadius = '4px';
        inspectButton.style.cursor = 'pointer';
        inspectButton.addEventListener('click', inspectTableState);
        controlsDiv.appendChild(inspectButton);

        // Fix All Button
        const fixButton = document.createElement('button');
        fixButton.innerText = 'Fix All Columns';
        fixButton.style.padding = '5px 10px';
        fixButton.style.backgroundColor = '#28a745';
        fixButton.style.color = 'white';
        fixButton.style.border = 'none';
        fixButton.style.borderRadius = '4px';
        fixButton.style.cursor = 'pointer';
        fixButton.addEventListener('click', fixAllColumns);
        controlsDiv.appendChild(fixButton);

        // Show/Hide Debug Controls Button
        const toggleControlsButton = document.createElement('button');
        toggleControlsButton.innerText = '👁️';
        toggleControlsButton.style.position = 'fixed';
        toggleControlsButton.style.bottom = '10px';
        toggleControlsButton.style.left = '10px';
        toggleControlsButton.style.zIndex = '10000';
        toggleControlsButton.style.width = '30px';
        toggleControlsButton.style.height = '30px';
        toggleControlsButton.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        toggleControlsButton.style.color = 'white';
        toggleControlsButton.style.border = 'none';
        toggleControlsButton.style.borderRadius = '50%';
        toggleControlsButton.style.display = 'flex';
        toggleControlsButton.style.alignItems = 'center';
        toggleControlsButton.style.justifyContent = 'center';
        toggleControlsButton.style.cursor = 'pointer';

        // Initially hide the controls div
        controlsDiv.style.display = 'none';

        toggleControlsButton.addEventListener('click', function () {
            if (controlsDiv.style.display === 'none') {
                controlsDiv.style.display = 'flex';
                toggleControlsButton.style.display = 'none';
            } else {
                controlsDiv.style.display = 'none';
            }
        });

        // Hide button when controls are shown
        const hideButton = document.createElement('button');
        hideButton.innerText = '✖️';
        hideButton.style.alignSelf = 'flex-end';
        hideButton.style.backgroundColor = 'transparent';
        hideButton.style.border = 'none';
        hideButton.style.color = '#555';
        hideButton.style.cursor = 'pointer';
        hideButton.addEventListener('click', function () {
            controlsDiv.style.display = 'none';
            toggleControlsButton.style.display = 'flex';
        });
        controlsDiv.appendChild(hideButton);

        document.body.appendChild(toggleControlsButton);
        document.body.appendChild(controlsDiv);
    }

    /**
     * Inspect the current state of the table
     */
    function inspectTableState() {
        console.group('Table Inspection');

        // Get all table headers
        const table = document.querySelector('table.table');
        if (!table) {
            console.error('Table not found');
            console.groupEnd();
            return;
        }

        const headers = table.querySelectorAll('th');
        console.log(`Found ${headers.length} table headers`);

        // Get all time-related headers
        const timeHeaders = Array.from(headers).filter(th => th.className.includes('time'));
        console.log(`Found ${timeHeaders.length} time-related headers`);

        timeHeaders.forEach(header => {
            const columnClass = header.className.split(' ').find(cls => cls.includes('column-'));
            const isVisible = window.getComputedStyle(header).display !== 'none';
            console.log(`Header: ${header.textContent.trim()}, Class: ${columnClass}, Visible: ${isVisible}`);

            // Check if the corresponding cells are visible
            const fieldClass = `field-${columnClass.replace('column-', '')}`;
            const cells = table.querySelectorAll(`td.${fieldClass}`);

            console.log(`  Found ${cells.length} cells with class ${fieldClass}`);

            // Check the first cell visibility
            if (cells.length > 0) {
                const firstCell = cells[0];
                const isCellVisible = window.getComputedStyle(firstCell).display !== 'none';
                console.log(`  First cell content: "${firstCell.textContent.trim()}", Visible: ${isCellVisible}`);

                // Check for mismatch
                if (isVisible !== isCellVisible) {
                    console.error(`  MISMATCH: Header visible: ${isVisible}, Cell visible: ${isCellVisible}`);
                }
            }
        });

        // Get toggle state
        const timeToggles = document.querySelectorAll('[id^="toggle"][id$="Time"]');
        timeToggles.forEach(toggle => {
            const columnClass = getColumnClassFromToggle(toggle);

            // Find the corresponding header and cell
            const header = table.querySelector(`th.${columnClass}`);
            const cells = table.querySelectorAll(`td.field-${columnClass.replace('column-', '')}`);

            const headerVisible = header ? window.getComputedStyle(header).display !== 'none' : false;
            const cellsVisible = cells.length > 0 ?
                window.getComputedStyle(cells[0]).display !== 'none' : false;

            console.log(`Toggle ${toggle.id}: checked=${toggle.checked}, header visible=${headerVisible}, cells visible=${cellsVisible}`);

            // Check for mismatch
            if (toggle.checked !== headerVisible || toggle.checked !== cellsVisible) {
                console.error(`  MISMATCH: Toggle checked: ${toggle.checked}, Header visible: ${headerVisible}, Cells visible: ${cellsVisible}`);
            }
        });

        console.groupEnd();
    }

    /**
     * Fix all column visibility issues
     */
    function fixAllColumns() {
        console.group('Fixing All Columns');

        // Get all time toggles
        const timeToggles = document.querySelectorAll('[id^="toggle"][id$="Time"]');

        timeToggles.forEach(toggle => {
            const columnClass = getColumnClassFromToggle(toggle);
            if (columnClass) {
                // Force the visibility to match the toggle state
                forceColumnVisibility(columnClass, toggle.checked);
                console.log(`Fixed visibility for ${columnClass}: ${toggle.checked}`);
            }
        });

        console.groupEnd();
    }

    /**
     * Force visibility of column cells
     */
    function forceColumnVisibility(columnClass, isVisible) {
        console.log(`Forcing visibility for ${columnClass}: ${isVisible ? 'SHOW' : 'HIDE'}`);

        // Get the field class
        const fieldClass = `field-${columnClass.replace('column-', '')}`;

        // Find all cells and headers
        const table = document.querySelector('table.table');
        if (!table) {
            console.error('Table not found');
            return;
        }

        const headers = table.querySelectorAll(`th.${columnClass}`);
        const cells = table.querySelectorAll(`td.${fieldClass}`);

        console.log(`Found ${headers.length} headers and ${cells.length} cells for ${columnClass}`);

        // Apply to headers
        headers.forEach(header => {
            header.style.display = isVisible ? '' : 'none';
        });

        // Apply to cells
        cells.forEach(cell => {
            cell.style.display = isVisible ? '' : 'none';
        });
    }

    /**
     * Validate column classes for a toggle
     */
    function validateColumnClasses(toggle) {
        const columnClass = getColumnClassFromToggle(toggle);
        if (!columnClass) {
            console.error(`No column class found for toggle: ${toggle.id}`);
            return;
        }

        const fieldClass = `field-${columnClass.replace('column-', '')}`;

        // Find table
        const table = document.querySelector('table.table');
        if (!table) {
            console.error('Table not found');
            return;
        }

        // Count headers and cells
        const headers = table.querySelectorAll(`th.${columnClass}`);
        const cells = table.querySelectorAll(`td.${fieldClass}`);

        if (headers.length === 0) {
            console.error(`No headers found with class: ${columnClass}`);
        }

        if (cells.length === 0) {
            console.error(`No cells found with class: ${fieldClass}`);
        }

        console.log(`Validation for ${toggle.id}: ${headers.length} headers and ${cells.length} cells found`);
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

        const table = document.querySelector('table.table');
        if (!table) return false;

        const header = table.querySelector(`th.${columnClass}`);
        return header && window.getComputedStyle(header).display !== 'none';
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

// Update status badges to Google Material Design style
function createStatusBadge(status) {
    // Default values
    let badgeClass = 'status-not-completed';
    let label = status || 'Not Started';

    // Map status strings to badge classes and labels
    if (status) {
        status = status.toLowerCase();

        if (status === 'completed' || status === 'complete') {
            badgeClass = 'status-completed';
            label = 'Completed';
        } else if (status === 'not completed') {
            badgeClass = 'status-not-completed';
            label = 'Not Completed';
        } else if (status.includes('in progress') || status === 'running') {
            badgeClass = 'status-in-progress';
            label = 'In Progress';
        } else if (status.includes('pending') || status === 'submitted' || status === 'queued') {
            badgeClass = 'status-pending';
            label = 'Pending';
        } else if (status.includes('error') || status.includes('fail') || status.includes('killed')) {
            badgeClass = 'status-error';
            label = status.charAt(0).toUpperCase() + status.slice(1);
        } else {
            badgeClass = 'status-not-completed';
            label = status.charAt(0).toUpperCase() + status.slice(1);
        }
    }

    // Create the badge element
    return `<span class="status-badge ${badgeClass}">${label}</span>`;
} 