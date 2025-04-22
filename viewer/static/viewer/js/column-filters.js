/**
 * Column-based filtering system for the sample browser
 * This script handles filter dropdowns in table headers
 */

document.addEventListener('DOMContentLoaded', function () {
    console.log('Initializing column filters...');

    // Initialize column filters
    initColumnFilters();

    // Initialize active filters display
    updateActiveFiltersDisplay();

    // Initialize reset filters button
    initResetFiltersButton();
});

/**
 * Initialize column filters
 */
function initColumnFilters() {
    // Get all filter toggles
    const filterToggles = document.querySelectorAll('.filter-toggle');

    // Initialize each filter
    filterToggles.forEach(toggle => {
        // Get the column field from the parent
        const filterContainer = toggle.closest('.column-filter');
        const field = filterContainer.dataset.field;

        // Get the filter dropdown
        const dropdown = filterContainer.querySelector('.filter-dropdown');
        const select = dropdown.querySelector('select.filter-select');

        // For dropdowns, populate options from table data
        if (select) {
            populateFilterOptions(field, select);

            // Initialize Select2 for dropdowns
            if (jQuery && jQuery.fn.select2) {
                jQuery(select).select2({
                    theme: 'bootstrap4',
                    width: '100%',
                    placeholder: 'Select options',
                    allowClear: true,
                    closeOnSelect: false,
                    dropdownParent: dropdown
                });

                // Initialize current value from URL parameters
                initializeFilterValue(field, select);
            }
        }

        // For text filters, initialize from URL parameters
        const textInput = dropdown.querySelector('input.text-filter');
        if (textInput) {
            initializeFilterValue(field, textInput);
        }

        // Handle toggle click
        toggle.addEventListener('click', function (e) {
            e.stopPropagation();

            // Close any open dropdowns first
            document.querySelectorAll('.filter-dropdown.show').forEach(openDropdown => {
                if (openDropdown !== dropdown) {
                    openDropdown.classList.remove('show');
                    openDropdown.closest('.column-filter').querySelector('.filter-toggle').classList.remove('active');
                }
            });

            // Toggle this dropdown
            dropdown.classList.toggle('show');
            toggle.classList.toggle('active');
        });

        // Handle apply button click
        const applyBtn = dropdown.querySelector('.apply-filter-btn');
        if (applyBtn) {
            applyBtn.addEventListener('click', function () {
                applyFilter(field, dropdown);
                dropdown.classList.remove('show');
                toggle.classList.remove('active');
            });
        }

        // Handle clear button click
        const clearBtn = dropdown.querySelector('.clear-filter-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                clearFilter(field, dropdown);
            });
        }
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.column-filter')) {
            document.querySelectorAll('.filter-dropdown.show').forEach(dropdown => {
                dropdown.classList.remove('show');
                dropdown.closest('.column-filter').querySelector('.filter-toggle').classList.remove('active');
            });
        }
    });

    // Update toggle state for active filters
    updateFilterToggles();
}

/**
 * Populate filter options based on table data
 * @param {string} field - The field name to populate options for
 * @param {HTMLElement} select - The select element to populate
 */
function populateFilterOptions(field, select) {
    // Get all unique values from the table for this field
    const values = new Set();
    const columnIndex = getColumnIndexByField(field);

    if (columnIndex !== -1) {
        // Get all values from table rows
        document.querySelectorAll('table tbody tr').forEach(row => {
            const cell = row.cells[columnIndex];
            if (cell) {
                const value = cell.textContent.trim();
                if (value && value !== '—' && value !== '-') {
                    values.add(value);
                }
            }
        });

        // Sort values alphabetically
        const sortedValues = Array.from(values).sort();

        // Add options to select
        sortedValues.forEach(value => {
            const option = document.createElement('option');
            option.value = value;
            option.textContent = value;
            select.appendChild(option);
        });
    }
}

/**
 * Get column index by field name
 * @param {string} field - The field name to find
 * @returns {number} - The column index or -1 if not found
 */
function getColumnIndexByField(field) {
    // Add 1 to account for the selection column
    let index = 1;

    // Look through table headers
    const headers = document.querySelectorAll('table thead tr th');
    for (let i = 1; i < headers.length; i++) {
        const filterContainer = headers[i].querySelector('.column-filter');
        if (filterContainer && filterContainer.dataset.field === field) {
            return i;
        }
        index++;
    }

    return -1;
}

/**
 * Initialize filter value from URL parameters
 * @param {string} field - The field name
 * @param {HTMLElement} element - The filter element (select or input)
 */
function initializeFilterValue(field, element) {
    const urlParams = new URLSearchParams(window.location.search);

    if (element.tagName.toLowerCase() === 'select') {
        // Handle multi-select
        const paramName = `${field}_list`;
        if (urlParams.has(paramName)) {
            const values = urlParams.get(paramName).split(',');
            if (jQuery && jQuery.fn.select2) {
                jQuery(element).val(values).trigger('change');
            } else {
                values.forEach(value => {
                    const option = element.querySelector(`option[value="${value}"]`);
                    if (option) option.selected = true;
                });
            }

            // Mark the filter as active
            const toggle = element.closest('.column-filter').querySelector('.filter-toggle');
            toggle.classList.add('active');
        }
    } else {
        // Handle text input
        if (urlParams.has(field)) {
            element.value = urlParams.get(field);

            // Mark the filter as active
            const toggle = element.closest('.column-filter').querySelector('.filter-toggle');
            toggle.classList.add('active');
        }
    }
}

/**
 * Apply filter to the form
 * @param {string} field - The field name
 * @param {HTMLElement} dropdown - The dropdown element
 */
function applyFilter(field, dropdown) {
    const form = document.getElementById('filter-form');

    // Handle different filter types
    const select = dropdown.querySelector('select.filter-select');
    const textInput = dropdown.querySelector('input.text-filter');

    if (select) {
        // Handle multi-select
        const values = jQuery(select).val();
        if (values && values.length) {
            // Add or update hidden input for the field
            let input = form.querySelector(`input[name="${field}_list"]`);
            if (!input) {
                input = document.createElement('input');
                input.type = 'hidden';
                input.name = `${field}_list`;
                form.appendChild(input);
            }
            input.value = values.join(',');
        } else {
            // Remove hidden input if no values selected
            const input = form.querySelector(`input[name="${field}_list"]`);
            if (input) input.remove();
        }
    } else if (textInput) {
        // Handle text input
        const value = textInput.value.trim();
        if (value) {
            // Add or update hidden input for the field
            let input = form.querySelector(`input[name="${field}"]`);
            if (!input) {
                input = document.createElement('input');
                input.type = 'hidden';
                input.name = field;
                form.appendChild(input);
            }
            input.value = value;
        } else {
            // Remove hidden input if empty
            const input = form.querySelector(`input[name="${field}"]`);
            if (input) input.remove();
        }
    }

    // Reset to first page
    let pageInput = form.querySelector('input[name="page"]');
    if (!pageInput) {
        pageInput = document.createElement('input');
        pageInput.type = 'hidden';
        pageInput.name = 'page';
        form.appendChild(pageInput);
    }
    pageInput.value = '1';

    // Submit the form
    form.submit();
}

/**
 * Clear a specific filter
 * @param {string} field - The field name
 * @param {HTMLElement} dropdown - The dropdown element
 */
function clearFilter(field, dropdown) {
    const form = document.getElementById('filter-form');

    // Clear filter in the UI
    const select = dropdown.querySelector('select.filter-select');
    const textInput = dropdown.querySelector('input.text-filter');

    if (select && jQuery && jQuery.fn.select2) {
        jQuery(select).val(null).trigger('change');
    } else if (textInput) {
        textInput.value = '';
    }

    // Remove hidden inputs
    const hiddenInputs = form.querySelectorAll(`input[name="${field}"], input[name="${field}_list"]`);
    hiddenInputs.forEach(input => input.remove());

    // Reset to first page
    let pageInput = form.querySelector('input[name="page"]');
    if (!pageInput) {
        pageInput = document.createElement('input');
        pageInput.type = 'hidden';
        pageInput.name = 'page';
        form.appendChild(pageInput);
    }
    pageInput.value = '1';

    // Submit form to apply changes
    form.submit();
}

/**
 * Update the active filters display
 */
function updateActiveFiltersDisplay() {
    const container = document.querySelector('.active-filters-container');
    if (!container) return;

    // Clear existing content
    container.innerHTML = '';

    // Set to track unique filter combinations
    const uniqueFilters = new Set();
    let hasActiveFilters = false;

    // Process URL parameters
    const urlParams = new URLSearchParams(window.location.search);

    for (const [key, value] of urlParams.entries()) {
        if (key !== 'page' && key !== 'per_page' && value) {
            // Skip search parameter, handled separately
            if (key === 'search') {
                hasActiveFilters = true;
                const filterKey = `search:${value}`;
                if (!uniqueFilters.has(filterKey)) {
                    uniqueFilters.add(filterKey);
                    createFilterTag(container, 'search', null, value, 'Search');
                }
                continue;
            }

            hasActiveFilters = true;

            if (key.endsWith('_list')) {
                // Handle multi-select parameters
                const baseKey = key.replace('_list', '');
                const values = value.split(',');

                values.forEach(val => {
                    if (val) {
                        const filterKey = `${baseKey}:${val}`;
                        if (!uniqueFilters.has(filterKey)) {
                            uniqueFilters.add(filterKey);
                            // Get friendly field name from th content
                            const fieldName = getFieldDisplayName(baseKey);
                            createFilterTag(container, baseKey, val, val, fieldName);
                        }
                    }
                });
            } else {
                // Handle text filter parameters
                const filterKey = `${key}:${value}`;
                if (!uniqueFilters.has(filterKey)) {
                    uniqueFilters.add(filterKey);
                    // Get friendly field name from th content
                    const fieldName = getFieldDisplayName(key);
                    createFilterTag(container, key, null, value, fieldName);
                }
            }
        }
    }

    // Show or hide container based on filters
    if (hasActiveFilters) {
        container.style.display = 'flex';

        // Add a title if not present
        if (!container.querySelector('.filter-heading')) {
            const heading = document.createElement('div');
            heading.className = 'filter-heading';
            heading.innerHTML = '<i class="bi bi-funnel-fill me-1"></i> Active Filters:';
            container.prepend(heading);
        }
    } else {
        container.style.display = 'none';
    }
}

/**
 * Get field display name from table header
 * @param {string} field - The field name
 * @returns {string} - The display name
 */
function getFieldDisplayName(field) {
    // Find column with matching data-field
    const headers = document.querySelectorAll('table thead th');
    for (const header of headers) {
        const filterContainer = header.querySelector(`.column-filter[data-field="${field}"]`);
        if (filterContainer) {
            // Get text content of header excluding the filter toggle
            const headerContent = header.querySelector('.header-content');
            if (headerContent) {
                // Clone to avoid modifying the DOM
                const clone = headerContent.cloneNode(true);
                // Remove the filter container from the clone
                const filterInClone = clone.querySelector('.column-filter');
                if (filterInClone) filterInClone.remove();
                // Return the cleaned text
                return clone.textContent.trim();
            }
            return header.textContent.trim();
        }
    }

    // Fallback: format field name nicely
    return field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

/**
 * Creates a filter tag element
 * @param {HTMLElement} container - Container for the filter tags
 * @param {string} filter - Filter field name
 * @param {string|null} value - Filter value (null for text inputs)
 * @param {string} displayText - Text to display
 * @param {string} fieldName - Display name for the field
 */
function createFilterTag(container, filter, value, displayText, fieldName) {
    // Create tag element
    const tag = document.createElement('div');
    tag.className = 'filter-tag';

    // Create a data attribute to store the filter and value for removal
    tag.dataset.filter = filter;
    if (value) {
        tag.dataset.value = value;
    }

    // Set tag content with remove button
    tag.innerHTML = `
        <span class="tag-name">${fieldName}:</span>
        <span class="tag-value">${displayText}</span>
        <button type="button" class="tag-remove" aria-label="Remove filter">
            <i class="bi bi-x"></i>
        </button>
    `;

    // Add event listener to the remove button
    const removeButton = tag.querySelector('.tag-remove');
    if (removeButton) {
        removeButton.addEventListener('click', function () {
            removeFilter(filter, value);
        });
    }

    // Add to DOM
    container.appendChild(tag);

    // Add appearance animation
    tag.style.opacity = '0';
    tag.style.transform = 'translateY(10px)';

    // Trigger animation
    setTimeout(() => {
        tag.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        tag.style.opacity = '1';
        tag.style.transform = 'translateY(0)';
    }, 10);
}

/**
 * Remove a filter and submit the form
 * @param {string} filter - The filter field name
 * @param {string|null} value - The filter value (null for text inputs)
 */
function removeFilter(filter, value) {
    const form = document.getElementById('filter-form');

    if (value) {
        // For multi-select filters, remove specific value
        const inputName = `${filter}_list`;
        const input = form.querySelector(`input[name="${inputName}"]`);
        if (input) {
            const values = input.value.split(',');
            const newValues = values.filter(v => v !== value);

            if (newValues.length) {
                input.value = newValues.join(',');
            } else {
                input.remove();
            }
        }
    } else {
        // For text filters, remove the entire filter
        const input = form.querySelector(`input[name="${filter}"]`);
        if (input) {
            input.remove();
        }
    }

    // Reset to first page
    let pageInput = form.querySelector('input[name="page"]');
    if (!pageInput) {
        pageInput = document.createElement('input');
        pageInput.type = 'hidden';
        pageInput.name = 'page';
        form.appendChild(pageInput);
    }
    pageInput.value = '1';

    // Submit the form
    form.submit();
}

/**
 * Update filter toggle states based on active filters
 */
function updateFilterToggles() {
    const urlParams = new URLSearchParams(window.location.search);

    // For each filter toggle, check if its filter is active
    document.querySelectorAll('.column-filter').forEach(filterContainer => {
        const field = filterContainer.dataset.field;
        const toggle = filterContainer.querySelector('.filter-toggle');

        // Check if the filter has an active value
        if (urlParams.has(field) || urlParams.has(`${field}_list`)) {
            toggle.classList.add('active');
        }
    });
}

/**
 * Initialize reset filters button
 */
function initResetFiltersButton() {
    const resetButton = document.getElementById('resetFilters');

    if (resetButton) {
        resetButton.addEventListener('click', function () {
            // Get the current URL
            const url = new URL(window.location);

            // Keep only pagination parameters
            const params = new URLSearchParams();
            params.set('page', '1');
            if (url.searchParams.has('per_page')) {
                params.set('per_page', url.searchParams.get('per_page'));
            }

            // Redirect to the filtered URL
            window.location.href = `${url.pathname}?${params.toString()}`;
        });
    }
}

// Add CSS for filter toggles active state
document.addEventListener('DOMContentLoaded', function () {
    const style = document.createElement('style');
    style.textContent = `
        .filter-toggle.active {
            background-color: #e3f2fd;
            color: #1976D2;
            border-color: #1976D2;
        }
        
        .filter-dropdown {
            min-width: 250px;
        }
        
        @media (max-width: 768px) {
            .filter-dropdown {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 90%;
                max-width: 320px;
                z-index: 1050;
            }
        }
    `;
    document.head.appendChild(style);
}); 