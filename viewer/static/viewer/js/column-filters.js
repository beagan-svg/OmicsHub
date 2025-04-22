/**
 * Column-based filters for sample browser
 * This script implements the per-column filters in the table headers
 */

document.addEventListener('DOMContentLoaded', function () {
    initColumnFilters();
});

/**
 * Initialize column filters
 */
function initColumnFilters() {
    // Add filter buttons to table headers
    addFilterButtonsToHeaders();

    // Initialize filter dropdowns
    setupFilterDropdowns();

    // Set up click-outside handler to close dropdowns
    setupClickOutsideHandler();

    // Handle applied filters display
    updateAppliedFiltersDisplay();
}

/**
 * Add filter buttons to table headers
 */
function addFilterButtonsToHeaders() {
    const tableHeaders = document.querySelectorAll('table.table th:not(.selection-column)');

    tableHeaders.forEach(header => {
        // Skip if already has a filter button
        if (header.querySelector('.column-filter-btn')) {
            return;
        }

        // Get column name
        const columnName = header.textContent.trim();
        const columnId = header.getAttribute('id') ||
            'col-' + columnName.toLowerCase().replace(/\s+/g, '-');

        // Set header ID if not present
        if (!header.getAttribute('id')) {
            header.setAttribute('id', columnId);
        }

        // Clean up any placeholder-like text (such as {{ COLUMN.HEADER }})
        if (columnName.includes('{{') && columnName.includes('}}')) {
            // Extract a clean name from the placeholder
            const cleanName = columnName.replace(/[{}]/g, '').trim().split('.').pop();
            // Set the header text to the clean name
            header.textContent = cleanName.charAt(0).toUpperCase() + cleanName.slice(1).toLowerCase();
        }

        // Create filter button with tooltip
        const filterBtn = document.createElement('button');
        filterBtn.className = 'column-filter-btn';
        filterBtn.innerHTML = '<i class="bi bi-funnel"></i>';
        filterBtn.setAttribute('data-column', columnId);
        filterBtn.setAttribute('aria-label', `Filter ${header.textContent.trim()}`);
        filterBtn.setAttribute('title', `Filter ${header.textContent.trim()}`);

        // Create filter container
        const filterContainer = document.createElement('div');
        filterContainer.className = 'column-filter-container';

        // Create dropdown
        const dropdown = createFilterDropdown(header.textContent.trim(), columnId);

        // Add to header
        filterContainer.appendChild(filterBtn);
        filterContainer.appendChild(dropdown);
        header.appendChild(filterContainer);

        // Check if there are active filters for this column
        if (hasActiveFilters(columnId)) {
            header.classList.add('has-active-filter');
        }
    });
}

/**
 * Create filter dropdown for a column
 */
function createFilterDropdown(columnName, columnId) {
    // Create dropdown element
    const dropdown = document.createElement('div');
    dropdown.className = 'column-filter-dropdown';
    dropdown.id = `dropdown-${columnId}`;

    // Create dropdown header
    const header = document.createElement('div');
    header.className = 'filter-dropdown-header';
    header.innerHTML = `
        <span class="filter-title">Filter: ${columnName}</span>
        <button type="button" class="close-filter" aria-label="Close filter">
            <i class="bi bi-x"></i>
        </button>
    `;

    // Create dropdown content
    const content = document.createElement('div');
    content.className = 'filter-dropdown-content';

    // Create search input
    const search = document.createElement('div');
    search.className = 'filter-search';
    search.innerHTML = `
        <i class="bi bi-search"></i>
        <input type="text" class="filter-search-input" placeholder="Search values..." 
               aria-label="Search filter values">
    `;

    // Create select/deselect all buttons
    const selectButtons = document.createElement('div');
    selectButtons.className = 'select-all-container';
    selectButtons.innerHTML = `
        <button type="button" class="select-all-btn">Select All</button>
        <button type="button" class="deselect-all-btn">Deselect All</button>
    `;

    // Create filter options container
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'filter-options-container';
    optionsContainer.innerHTML = `
        <div class="filter-loading">
            <div class="filter-spinner"></div>
            <span>Loading filter values...</span>
        </div>
    `;

    // Create footer with action buttons
    const footer = document.createElement('div');
    footer.className = 'filter-dropdown-footer';
    footer.innerHTML = `
        <button type="button" class="btn btn-outline-secondary btn-sm cancel-filter">Cancel</button>
        <button type="button" class="btn btn-primary btn-sm apply-filter">Apply Filter</button>
    `;

    // Assemble dropdown
    content.appendChild(search);
    content.appendChild(selectButtons);
    content.appendChild(optionsContainer);

    dropdown.appendChild(header);
    dropdown.appendChild(content);
    dropdown.appendChild(footer);

    return dropdown;
}

/**
 * Set up filter dropdowns
 */
function setupFilterDropdowns() {
    // Handle filter button clicks
    document.querySelectorAll('.column-filter-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const columnId = this.getAttribute('data-column');
            const dropdown = document.getElementById(`dropdown-${columnId}`);

            // Close all other dropdowns
            document.querySelectorAll('.column-filter-dropdown.show').forEach(d => {
                if (d !== dropdown) {
                    d.classList.remove('show');
                }
            });

            // Toggle this dropdown
            dropdown.classList.toggle('show');

            // Toggle active state on button
            this.classList.toggle('active', dropdown.classList.contains('show'));

            // If showing dropdown, load filter values
            if (dropdown.classList.contains('show')) {
                loadFilterValues(columnId);
            }
        });
    });

    // Handle close button clicks
    document.querySelectorAll('.close-filter').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const dropdown = this.closest('.column-filter-dropdown');
            dropdown.classList.remove('show');

            // Remove active state from button
            const columnId = dropdown.id.replace('dropdown-', '');
            const btn = document.querySelector(`.column-filter-btn[data-column="${columnId}"]`);
            if (btn) btn.classList.remove('active');
        });
    });

    // Handle cancel button clicks
    document.querySelectorAll('.cancel-filter').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const dropdown = this.closest('.column-filter-dropdown');
            dropdown.classList.remove('show');

            // Remove active state from button
            const columnId = dropdown.id.replace('dropdown-', '');
            const btn = document.querySelector(`.column-filter-btn[data-column="${columnId}"]`);
            if (btn) btn.classList.remove('active');
        });
    });

    // Handle apply button clicks
    document.querySelectorAll('.apply-filter').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const dropdown = this.closest('.column-filter-dropdown');
            const columnId = dropdown.id.replace('dropdown-', '');

            applyFilter(columnId, dropdown);
        });
    });

    // Handle select all button clicks
    document.querySelectorAll('.select-all-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const dropdown = this.closest('.column-filter-dropdown');
            const checkboxes = dropdown.querySelectorAll('.filter-option input[type="checkbox"]');

            checkboxes.forEach(cb => {
                cb.checked = true;
            });
        });
    });

    // Handle deselect all button clicks
    document.querySelectorAll('.deselect-all-btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.stopPropagation();
            const dropdown = this.closest('.column-filter-dropdown');
            const checkboxes = dropdown.querySelectorAll('.filter-option input[type="checkbox"]');

            checkboxes.forEach(cb => {
                cb.checked = false;
            });
        });
    });

    // Handle filter search
    document.querySelectorAll('.filter-search-input').forEach(input => {
        input.addEventListener('input', function (e) {
            const searchValue = this.value.toLowerCase();
            const dropdown = this.closest('.column-filter-dropdown');
            const options = dropdown.querySelectorAll('.filter-option');

            options.forEach(option => {
                const text = option.querySelector('label').textContent.toLowerCase();
                option.style.display = text.includes(searchValue) ? '' : 'none';
            });
        });
    });
}

/**
 * Setup click outside handler to close dropdowns when clicking outside
 */
function setupClickOutsideHandler() {
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.column-filter-container')) {
            document.querySelectorAll('.column-filter-dropdown').forEach(dropdown => {
                dropdown.classList.remove('show');
            });

            // Remove active state from all buttons
            document.querySelectorAll('.column-filter-btn.active').forEach(btn => {
                btn.classList.remove('active');
            });
        }
    });
}

/**
 * Load filter values for a column
 */
function loadFilterValues(columnId) {
    const dropdown = document.getElementById(`dropdown-${columnId}`);
    const optionsContainer = dropdown.querySelector('.filter-options-container');

    // Show loading indicator
    optionsContainer.innerHTML = `
        <div class="filter-loading">
            <div class="filter-spinner"></div>
            <span>Loading filter values...</span>
        </div>
    `;

    // Get unique values from the table column
    setTimeout(() => {
        const values = getUniqueColumnValues(columnId);
        const activeFilters = getActiveFiltersForColumn(columnId);

        // Create filter options
        let optionsHTML = '';
        values.forEach(value => {
            const isChecked = !activeFilters.length || activeFilters.includes(value);
            const valueId = value.toString().replace(/[^a-zA-Z0-9]/g, '-');
            optionsHTML += `
                <div class="filter-option">
                    <input type="checkbox" id="${columnId}-${valueId}" 
                           ${isChecked ? 'checked' : ''} value="${value}">
                    <label for="${columnId}-${valueId}">${value}</label>
                </div>
            `;
        });

        // If no values found
        if (!values.length) {
            optionsHTML = '<div class="p-3 text-center text-muted">No values found</div>';
        }

        // Update options container
        optionsContainer.innerHTML = optionsHTML;
    }, 300);
}

/**
 * Get unique values from a table column
 */
function getUniqueColumnValues(columnId) {
    const header = document.getElementById(columnId);
    const columnIndex = Array.from(header.parentNode.children).indexOf(header);
    const tableRows = document.querySelectorAll('table.table tbody tr');
    const values = new Set();

    tableRows.forEach(row => {
        const cell = row.cells[columnIndex];
        if (cell) {
            const value = cell.textContent.trim();
            if (value) {
                values.add(value);
            }
        }
    });

    return Array.from(values).sort();
}

/**
 * Apply filter for column
 */
function applyFilter(columnId, dropdown) {
    const checkedOptions = dropdown.querySelectorAll('.filter-option input[type="checkbox"]:checked');
    const columnName = dropdown.querySelector('.filter-title').textContent.replace('Filter:', '').trim();

    // Get selected values
    const selectedValues = Array.from(checkedOptions).map(opt => opt.value);

    // If all options are selected, don't apply any filter
    const allOptions = dropdown.querySelectorAll('.filter-option input[type="checkbox"]');
    if (selectedValues.length === allOptions.length) {
        // Clear existing filter if any
        if (hasActiveFilters(columnId)) {
            updateFiltersInQueryString(columnId, []);
            window.location.href = window.location.pathname + '?' + getUpdatedQueryString();
        } else {
            // Just close the dropdown if no change
            dropdown.classList.remove('show');

            // Remove active state from button
            const btn = document.querySelector(`.column-filter-btn[data-column="${columnId}"]`);
            if (btn) btn.classList.remove('active');
        }
        return;
    }

    // Update query string and reload
    updateFiltersInQueryString(columnId, selectedValues);
    dropdown.classList.remove('show');

    // Submit form or reload page
    window.location.href = window.location.pathname + '?' + getUpdatedQueryString();
}

/**
 * Get active filters for a column from URL
 */
function getActiveFiltersForColumn(columnId) {
    const urlParams = new URLSearchParams(window.location.search);
    const paramName = columnToParamName(columnId);

    if (urlParams.has(paramName)) {
        return urlParams.get(paramName).split(',');
    }

    return [];
}

/**
 * Check if a column has active filters
 */
function hasActiveFilters(columnId) {
    return getActiveFiltersForColumn(columnId).length > 0;
}

/**
 * Update filters in query string
 */
function updateFiltersInQueryString(columnId, values) {
    const paramName = columnToParamName(columnId);
    let currentQueryString = window.location.search;
    const urlParams = new URLSearchParams(currentQueryString);

    if (values.length) {
        urlParams.set(paramName, values.join(','));
    } else {
        urlParams.delete(paramName);
    }

    // Update page to 1 when applying a new filter
    if (urlParams.has('page')) {
        urlParams.set('page', '1');
    }

    return urlParams.toString();
}

/**
 * Get updated query string
 */
function getUpdatedQueryString() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.toString();
}

/**
 * Convert column ID to parameter name
 */
function columnToParamName(columnId) {
    // Convert from col-fastq-name to fastq_name
    let paramName = columnId.replace(/^col-/, '').replace(/-/g, '_');
    return paramName + '_filter';
}

/**
 * Update applied filters display
 */
function updateAppliedFiltersDisplay() {
    const container = document.querySelector('.applied-filters-container');
    if (!container) return;

    const urlParams = new URLSearchParams(window.location.search);
    let hasActiveFilters = false;

    // Clear existing content
    container.innerHTML = '';

    // Process all filter parameters
    for (const [key, value] of urlParams.entries()) {
        if (key.endsWith('_filter') && value) {
            hasActiveFilters = true;

            // Convert parameter name to column name
            const baseKey = key.replace('_filter', '');
            const columnId = 'col-' + baseKey.replace(/_/g, '-');

            // Get column header text
            const header = document.getElementById(columnId);
            let columnName = baseKey.replace(/_/g, ' ');

            if (header) {
                const headerText = header.textContent.trim();
                columnName = headerText.replace(/[\n\t]/g, '').replace(/\s+/g, ' ');
            }

            // Create filter tag for each value
            value.split(',').forEach(val => {
                if (val.trim()) {
                    createFilterTag(container, columnId, columnName, val.trim());
                }
            });
        }
    }

    // Show or hide container based on active filters
    if (hasActiveFilters) {
        container.style.display = 'flex';
    } else {
        container.style.display = 'none';
    }
}

/**
 * Create a filter tag element
 */
function createFilterTag(container, columnId, columnName, value) {
    // Create tag element
    const tag = document.createElement('div');
    tag.className = 'applied-filter-tag';
    tag.dataset.column = columnId;
    tag.dataset.value = value;

    // Set tag content
    tag.innerHTML = `
        <span class="filter-column">${columnName}:</span>
        <span class="filter-value">${value}</span>
        <button type="button" class="remove-filter" aria-label="Remove filter">
            <i class="bi bi-x"></i>
        </button>
    `;

    // Add event listener to remove button
    const removeButton = tag.querySelector('.remove-filter');
    if (removeButton) {
        removeButton.addEventListener('click', function () {
            removeFilter(columnId, value);
        });
    }

    // Add to container
    container.appendChild(tag);
}

/**
 * Remove a specific filter
 */
function removeFilter(columnId, value) {
    const paramName = columnToParamName(columnId);
    const urlParams = new URLSearchParams(window.location.search);

    if (urlParams.has(paramName)) {
        const values = urlParams.get(paramName).split(',');
        const updatedValues = values.filter(val => val !== value);

        if (updatedValues.length) {
            urlParams.set(paramName, updatedValues.join(','));
        } else {
            urlParams.delete(paramName);
        }

        // Reset to page 1
        if (urlParams.has('page')) {
            urlParams.set('page', '1');
        }

        // Reload page with updated query string
        window.location.href = window.location.pathname + '?' + urlParams.toString();
    }
} 