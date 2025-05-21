/**
 * OCS Browser - JavaScript for the OCS Browser interface
 * Handles filters, selection, and UI interactions
 */

// Configuration
const OCSBrowser = {
    config: {
        debug: false,
        animationsEnabled: true,
        storageKey: 'selectedSamplesForPipeline'
    }
};

/**
 * Pagination Module
 * Handles consistent pagination logic across the application
 */
const PaginationManager = {
    // Constants for pagination parameters
    PAGINATION_PARAMS: {
        PAGE: 'page',
        PER_PAGE: 'per_page',
        DEFAULT_PAGE: 1,
        DEFAULT_PER_PAGE: 25
    },

    /**
     * Initialize pagination functionality
     */
    init() {
        Utils.logDebug('Initializing PaginationManager');

        // Get pagination state from the DOM
        this.loadPaginationState();

        // Set up event handlers
        this.setupEventHandlers();
    },

    /**
     * Load pagination state from data attributes in the DOM
     */
    loadPaginationState() {
        const paginationContainer = document.querySelector('[data-pagination-current-page]');
        if (paginationContainer) {
            try {
                // Read individual data attributes
                const currentPage = parseInt(paginationContainer.dataset.paginationCurrentPage) || 1;
                const totalPages = parseInt(paginationContainer.dataset.paginationTotalPages) || 1;
                const perPage = parseInt(paginationContainer.dataset.paginationPerPage) || 25;
                const totalItems = parseInt(paginationContainer.dataset.paginationTotalItems) || 0;

                this.state = {
                    current_page: currentPage,
                    total_pages: totalPages,
                    per_page: perPage,
                    total_items: totalItems
                };

                Utils.logDebug('Loaded pagination state:', this.state);
            } catch (error) {
                console.error('Error loading pagination state:', error);
                this.state = {
                    current_page: 1,
                    total_pages: 1,
                    per_page: 25,
                    total_items: 0
                };
            }
        } else {
            // Default state if not found
            this.state = {
                current_page: 1,
                total_pages: 1,
                per_page: 25,
                total_items: 0
            };
            Utils.logDebug('Using default pagination state');
        }

        return this.state;
    },

    /**
     * Set up event handlers for pagination controls
     */
    setupEventHandlers() {
        // Page navigation buttons
        document.querySelectorAll('[data-pagination-action]').forEach(element => {
            if (element.tagName === 'FORM') {
                // Handle form submissions (go to page)
                element.addEventListener('submit', (e) => this.handleGotoPageSubmit(e));
            } else {
                // Handle button/link clicks
                element.addEventListener('click', (e) => this.handlePaginationClick(e));
            }
        });

        // Per-page dropdown
        document.querySelectorAll('[data-pagination-action="per-page"]').forEach(element => {
            element.addEventListener('click', (e) => this.handlePerPageChange(e));
        });
    },

    /**
     * Handle click on pagination controls
     * @param {Event} event - The click event
     */
    handlePaginationClick(event) {
        const element = event.currentTarget;
        const action = element.dataset.paginationAction;

        // Don't handle form submissions here
        if (element.tagName === 'FORM') return;

        // Skip if disabled
        if (element.classList.contains('disabled') || element.hasAttribute('disabled')) {
            event.preventDefault();
            return;
        }

        // If the element is already a link with href, let the browser handle it
        if (element.tagName === 'A' && element.hasAttribute('href')) {
            // The link's href already contains the correct URL
            // Just let the default browser behavior happen
            return;
        }

        // Otherwise, construct the URL and navigate
        event.preventDefault();

        let targetPage = 1;
        switch (action) {
            case 'first': targetPage = 1; break;
            case 'prev': targetPage = Math.max(1, this.state.current_page - 1); break;
            case 'next': targetPage = Math.min(this.state.total_pages, this.state.current_page + 1); break;
            case 'last': targetPage = this.state.total_pages; break;
            default:
                if (element.dataset.paginationPage) {
                    targetPage = parseInt(element.dataset.paginationPage) || 1;
                }
                break;
        }

        window.location.href = this.generatePaginationUrl(targetPage);
    },

    /**
     * Handle form submission for go-to-page
     * @param {Event} event - The submit event
     */
    handleGotoPageSubmit(event) {
        event.preventDefault();
        const form = event.currentTarget;
        const input = form.querySelector('input[name="page"]');

        if (!input) return;

        // Validate page number
        const requestedPage = parseInt(input.value) || 1;
        const maxPage = parseInt(input.dataset.totalPages) || this.state.total_pages;
        const page = Math.max(1, Math.min(requestedPage, maxPage));

        // Navigate to the page
        window.location.href = this.generatePaginationUrl(page);
    },

    /**
     * Handle change of items per page
     * @param {Event} event - The click event
     */
    handlePerPageChange(event) {
        event.preventDefault();
        const element = event.currentTarget;
        const perPage = parseInt(element.dataset.perPage) || this.PAGINATION_PARAMS.DEFAULT_PER_PAGE;

        // Navigate to first page with new per_page setting
        window.location.href = this.generatePaginationUrl(1, perPage);
    },

    /**
     * Generate a URL for pagination
     * @param {number} page - The target page number
     * @param {number} [perPage] - Items per page (optional)
     * @returns {string} - The generated URL
     */
    generatePaginationUrl(page, perPage = null) {
        const url = new URL(window.location.href);
        const params = new URLSearchParams(url.search);

        // Set page parameter
        params.set(this.PAGINATION_PARAMS.PAGE, page);

        // Set per_page parameter if provided
        if (perPage !== null) {
            params.set(this.PAGINATION_PARAMS.PER_PAGE, perPage);
        }

        // Update URL
        url.search = params.toString();
        return url.toString();
    },

    /**
     * Preserve pagination state when performing other operations
     * @param {URLSearchParams} params - URL parameters to update
     * @returns {URLSearchParams} - Updated parameters with pagination preserved
     */
    preservePaginationParams(params) {
        const currentParams = new URLSearchParams(window.location.search);

        // Copy pagination params if they exist
        if (currentParams.has(this.PAGINATION_PARAMS.PER_PAGE)) {
            params.set(this.PAGINATION_PARAMS.PER_PAGE, currentParams.get(this.PAGINATION_PARAMS.PER_PAGE));
        }

        // Always set page to 1 when filter changes
        params.set(this.PAGINATION_PARAMS.PAGE, 1);

        return params;
    }
};

/**
 * Utility functions
 */
const Utils = {
    /**
     * Log debug messages when debug mode is enabled
     * @param {string} message - The message to log
     * @param {any} data - Optional data to log
     */
    logDebug(message, data) {
        if (window.DEBUG_MODE || OCSBrowser.config.debug) {
            if (data !== undefined) {
                console.log(`[OCS Browser] ${message}`, data);
            } else {
                console.log(`[OCS Browser] ${message}`);
            }
        }
    },

    /**
     * Safely get DOM elements and log errors if not found
     * @param {string} selector - The CSS selector
     * @param {string} elementName - A descriptive name for the element
     * @returns {Element|null} - The found element or null
     */
    getElement(selector, elementName) {
        const element = document.querySelector(selector);
        if (!element && elementName) {
            console.error(`[OCS Browser] ${elementName} not found (${selector})`);
        }
        return element;
    },

    /**
     * Format a field name into a friendly label
     * @param {string} name - The field name to format
     * @returns {string} - The formatted label
     */
    formatLabelFromName(name) {
        return name
            .replace(/_/g, ' ')
            .replace(/\b\w/g, l => l.toUpperCase());
    }
};

// Initialize the application when the DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    Utils.logDebug('DOM loaded, initializing OCS Browser components');

    // Initialize all components
    initAdvancedFiltersToggle();
    initEnhancedSelect2();
    initFilterTagRemovers();
    initResetFiltersButton();
    initApplyFiltersButton();
    updateActiveFiltersDisplay();
    initCardAnimations();
    initSelectionPanel();

    // Initialize pagination manager
    PaginationManager.init();
});

/**
 * Advanced Filters Module
 * Handles the toggling and animation of the advanced filters panel
 */
const AdvancedFilters = {
    /**
     * Initialize the advanced filters toggle with animation
     */
    init() {
        const toggleButton = Utils.getElement('#toggleAdvancedFilters', 'Toggle button');
        const filtersPanel = Utils.getElement('#advancedFilters', 'Filters panel');

        if (!toggleButton || !filtersPanel) return;

        // Set up the toggle click handler
        toggleButton.addEventListener('click', () => {
            const isHidden = filtersPanel.style.display === 'none' || !filtersPanel.style.display;
            isHidden ? this.showPanel(filtersPanel, toggleButton) : this.hidePanel(filtersPanel, toggleButton);
        });

        // Initialize from localStorage or data attribute
        const shouldShowFilters =
            localStorage.getItem('showAdvancedFilters') === 'true' ||
            (filtersPanel.dataset && filtersPanel.dataset.hasActiveFilters === 'true');

        if (shouldShowFilters) {
            filtersPanel.style.display = 'block';
            toggleButton.innerHTML = '<i class="bi bi-sliders"></i> <span>Hide Filters</span>';
        }
    },

    /**
     * Show filters panel with animation
     * @param {HTMLElement} panel - The filters panel element
     * @param {HTMLElement} button - The toggle button element
     */
    showPanel(panel, button) {
        if (!OCSBrowser.config.animationsEnabled) {
            panel.style.display = 'block';
            button.innerHTML = '<i class="bi bi-sliders"></i> <span>Hide Filters</span>';
            localStorage.setItem('showAdvancedFilters', 'true');
            return;
        }

        // Initial display
        panel.style.display = 'block';
        panel.style.opacity = '0';
        panel.style.transform = 'translateY(-20px)';

        // Get filter cards for animation
        const filterCards = panel.querySelectorAll('.filter-card');

        // Animate panel
        setTimeout(() => {
            panel.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            panel.style.opacity = '1';
            panel.style.transform = 'translateY(0)';

            // Animate each card with a delay
            filterCards.forEach((card, index) => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';

                setTimeout(() => {
                    card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, 100 + (index * 70));
            });
        }, 10);

        // Update button text
        button.innerHTML = '<i class="bi bi-sliders"></i> <span>Hide Filters</span>';
        localStorage.setItem('showAdvancedFilters', 'true');
    },

    /**
     * Hide filters panel with animation
     * @param {HTMLElement} panel - The filters panel element
     * @param {HTMLElement} button - The toggle button element
     */
    hidePanel(panel, button) {
        if (!OCSBrowser.config.animationsEnabled) {
            panel.style.display = 'none';
            button.innerHTML = '<i class="bi bi-sliders"></i> <span>Advanced Filters</span>';
            localStorage.setItem('showAdvancedFilters', 'false');
            return;
        }

        // Animate out
        panel.style.opacity = '0';
        panel.style.transform = 'translateY(-20px)';

        // Hide after animation
        setTimeout(() => {
            panel.style.display = 'none';
            panel.style.transition = '';
        }, 300);

        // Update button text
        button.innerHTML = '<i class="bi bi-sliders"></i> <span>Advanced Filters</span>';
        localStorage.setItem('showAdvancedFilters', 'false');
    }
};

/**
 * Initialize the advanced filters toggle
 */
function initAdvancedFiltersToggle() {
    AdvancedFilters.init();
}

/**
 * Select2 Module
 * Handles initialization and customization of Select2 dropdowns
 */
const Select2Manager = {
    /**
     * Initialize Select2 dropdowns with enhanced styling and functionality
     */
    init() {
        if (typeof jQuery === 'undefined' || typeof jQuery.fn.select2 === 'undefined') {
            console.warn('[OCS Browser] Select2 or jQuery not available');
            return;
        }

        Utils.logDebug('Initializing enhanced Select2');

        this.addCustomStyles();
        this.initializeDropdowns();
        this.setupEventHandlers();
        this.initializeCurrentStates();
    },

    /**
     * Add custom CSS styles for Select2 dropdowns
     */
    addCustomStyles() {
        const selectStyles = document.createElement('style');
        selectStyles.textContent = `
            /* Selected option in dropdown */
            .select2-results__option--selected {
                background-color: #e6f3ff !important;
                position: relative;
                padding-right: 25px !important;
            }
            
            /* Checkmark icon for selected options */
            .select2-results__option--selected:after {
                content: "✓";
                position: absolute;
                right: 10px;
                top: 50%;
                transform: translateY(-50%);
                color: #1976D2;
                font-weight: bold;
            }
            
            /* Highlight selected option on hover */
            .select2-results__option--selected:hover {
                background-color: #d4e9ff !important;
            }
        `;
        document.head.appendChild(selectStyles);
    },

    /**
     * Initialize Select2 dropdowns with configuration
     */
    initializeDropdowns() {
        const select2Config = {
            theme: 'bootstrap4',
            width: '100%',
            placeholder: 'Select options',
            allowClear: true,
            closeOnSelect: false,  // Keep dropdown open after selection
            templateResult: this.formatSelectOption,
            templateSelection: this.formatSelectOption,
            dropdownCssClass: 'enhanced-dropdown',
            selectionCssClass: 'select2-selection-fixed-height',
            minimumResultsForSearch: 5,
            containerCssClass: 'select2-fixed-height'
        };

        jQuery('.filter-select').select2(select2Config);
    },

    /**
     * Set up event handlers for Select2 elements
     */
    setupEventHandlers() {
        // Fix placeholder appearance
        jQuery('.filter-select').on('select2:open', function () {
            document.querySelector('.select2-search__field').placeholder = 'Search...';
        });

        // Handle on-change events
        jQuery('.filter-select').on('change', function () {
            Select2Manager.updateFilterHighlighting(this);
            updateActiveFiltersDisplay();
            Select2Manager.fixSelectHeight(this);

            // Keep focus on the dropdown after selection
            if (jQuery(this).data('select2').isOpen()) {
                jQuery(this).siblings('.select2-container').find('.select2-search__field').focus();
            }
        });

        // Prevent dropdown from closing when clicking inside
        jQuery(document).on('click', '.select2-results__option', function (e) {
            e.stopPropagation();
        });
    },

    /**
     * Initialize current states for all select elements
     */
    initializeCurrentStates() {
        jQuery('.filter-select').each(function () {
            Select2Manager.updateFilterHighlighting(this);
            Select2Manager.fixSelectHeight(this);
        });
    },

    /**
     * Format select options with color-coding for status fields
     * @param {Object} option - The option object from Select2
     * @returns {string|jQuery} - The formatted option
     */
    formatSelectOption(option) {
        if (!option.id) {
            return option.text;
        }

        let $option = jQuery(option.element);
        let optionText = option.text;
        let fieldName = $option.closest('select').attr('id');

        // If this is a status field, add color indicators
        if (fieldName && (fieldName.includes('status'))) {
            let statusClass = '';

            if (optionText.toUpperCase() === 'COMPLETED') {
                statusClass = 'status-option-completed';
            } else if (optionText.toUpperCase() === 'NOT COMPLETED') {
                statusClass = 'status-option-not-completed';
            } else if (optionText.toUpperCase() === 'FAILED') {
                statusClass = 'status-option-failed';
            }

            if (statusClass) {
                return jQuery('<span class="status-filter-option ' + statusClass + '">' + optionText + '</span>');
            }
        }

        return optionText;
    },

    /**
     * Fix select2 height to ensure consistent appearance
     * @param {HTMLElement} selectElement - The select element to fix
     */
    fixSelectHeight(selectElement) {
        const $select = jQuery(selectElement);
        const $container = $select.next('.select2-container');
        const $selection = $container.find('.select2-selection');

        // Force correct height
        $selection.css('height', '38px');

        // For multiple select, check if we need to scroll
        if ($selection.hasClass('select2-selection--multiple')) {
            const $choices = $selection.find('.select2-selection__rendered');
            if ($choices.children().length > 2) {
                // Don't set multiple scrollable containers
                $selection.css('overflow-y', 'hidden');
                $choices.css('overflow-y', 'auto');
                $choices.css('max-height', '68px'); // Allow showing 2-3 rows of tags
            }
        }
    },

    /**
     * Update the visual highlighting of filter fields based on selection state
     * @param {HTMLElement} selectElement - The select element to update
     */
    updateFilterHighlighting(selectElement) {
        const $select = jQuery(selectElement);
        const $container = $select.closest('.col-md-4, .col-md-6');
        const $label = $container.find('label');

        if ($select.val() && $select.val().length > 0) {
            $label.addClass('text-primary font-weight-bold');
            $container.addClass('has-active-filter');

            // Also highlight the parent card
            const $card = $container.closest('.filter-card');
            if ($card.length) {
                $card.addClass('has-active-filters');
            }
        } else {
            $label.removeClass('text-primary font-weight-bold');
            $container.removeClass('has-active-filter');

            // Check if any other filters in the card are active
            const $card = $container.closest('.filter-card');
            if ($card.length) {
                const activeFiltersInCard = $card.find('.has-active-filter').length;
                if (activeFiltersInCard === 0) {
                    $card.removeClass('has-active-filters');
                }
            }
        }
    }
};

/**
 * Initialize Select2 dropdowns
 */
function initEnhancedSelect2() {
    Select2Manager.init();
}

/**
 * Card Animations Module
 * Handles animations and effects for filter cards
 */
const CardAnimations = {
    /**
     * Initialize animations for filter cards
     */
    init() {
        const filterCards = document.querySelectorAll('.filter-card');

        filterCards.forEach(card => {
            // Add hover animation
            this.addHoverEffect(card);

            // Add focus effects for inputs
            this.addInputFocusEffects(card);
        });
    },

    /**
     * Add hover animation to card
     * @param {HTMLElement} card - The card element
     */
    addHoverEffect(card) {
        card.addEventListener('mouseenter', function () {
            this.style.transition = 'transform 0.3s ease, box-shadow 0.3s ease';
        });
    },

    /**
     * Add focus effects for inputs inside a card
     * @param {HTMLElement} card - The card element
     */
    addInputFocusEffects(card) {
        const inputs = card.querySelectorAll('input, select');

        inputs.forEach(input => {
            input.addEventListener('focus', function () {
                card.classList.add('filter-card-focus');
            });

            input.addEventListener('blur', function () {
                card.classList.remove('filter-card-focus');
            });
        });
    }
};

/**
 * Initialize card animations
 */
function initCardAnimations() {
    CardAnimations.init();
}

/**
 * Filter Tags Module
 * Handles the creation and management of filter tags
 */
const FilterTags = {
    /**
     * Creates a filter tag element
     * @param {HTMLElement} container - Container for the filter tags
     * @param {string} filter - Filter field name
     * @param {string|null} value - Filter value (null for text inputs)
     * @param {string} displayText - Text to display
     */
    createTag(container, filter, value, displayText) {
        // Create tag element
        const tag = document.createElement('div');
        tag.className = 'filter-tag';

        // Get friendly display name for the filter
        const filterLabel = document.querySelector(`label[for="${filter}"]`);
        const filterName = filterLabel ? filterLabel.textContent : Utils.formatLabelFromName(filter);

        // Create a data attribute to store the filter and value for removal
        tag.dataset.filter = filter;
        if (value) {
            tag.dataset.value = value;
        }

        // Set tag content with remove button
        tag.innerHTML = `
            <span class="tag-name">${filterName}:</span>
            <span class="tag-value">${displayText}</span>
            <button type="button" class="tag-remove" aria-label="Remove filter">
                <i class="bi bi-x"></i>
            </button>
        `;

        // Add event listener to the remove button
        const removeButton = tag.querySelector('.tag-remove');
        if (removeButton) {
            removeButton.addEventListener('click', () => {
                // Handle the filter removal
                if (value) {
                    this.removeFilterValue(filter, value);
                } else {
                    this.clearFilterInput(filter);
                }

                // Show animation before submitting
                this.animateTagRemoval(tag);
            });
        }

        // Add to DOM
        container.appendChild(tag);

        // Add appearance animation
        if (OCSBrowser.config.animationsEnabled) {
            tag.style.opacity = '0';
            tag.style.transform = 'translateY(10px)';

            // Trigger animation
            setTimeout(() => {
                tag.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                tag.style.opacity = '1';
                tag.style.transform = 'translateY(0)';
            }, 10);
        }
    },

    /**
     * Initialize filter tag removal functionality
     */
    initTagRemovers() {
        const filterTags = document.querySelectorAll('.tag-remove');

        filterTags.forEach(tag => {
            tag.addEventListener('click', () => {
                const filter = tag.closest('.filter-tag').dataset.filter;
                const value = tag.closest('.filter-tag').dataset.value;
                const tagElement = tag.closest('.filter-tag');

                // Handle different filter types
                if (value) {
                    this.removeFilterValue(filter, value);
                } else {
                    this.clearFilterInput(filter);
                }

                // Show animation before submitting
                this.animateTagRemoval(tagElement);
            });
        });
    },

    /**
     * Remove a filter value from a select element
     * @param {string} filter - The filter field name
     * @param {string} value - The value to remove
     */
    removeFilterValue(filter, value) {
        const select = document.getElementById(filter);
        if (select && typeof jQuery !== 'undefined') {
            let currentValues = jQuery(select).val() || [];
            currentValues = currentValues.filter(item => item !== value);
            jQuery(select).val(currentValues).trigger('change');
        }
    },

    /**
     * Clear a filter input field
     * @param {string} filter - The filter field name
     */
    clearFilterInput(filter) {
        const input = document.querySelector(`[name="${filter}"]`);
        if (input) {
            input.value = '';
        }
    },

    /**
     * Animate the removal of a filter tag
     * @param {HTMLElement} tagElement - The tag element to animate
     */
    animateTagRemoval(tagElement) {
        if (OCSBrowser.config.animationsEnabled) {
            tagElement.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
            tagElement.style.transform = 'translateX(-10px)';
            tagElement.style.opacity = '0';

            setTimeout(() => {
                document.getElementById('filter-form').submit();
            }, 200);
        } else {
            document.getElementById('filter-form').submit();
        }
    }
};

/**
 * Initialize filter tag removal functionality
 */
function initFilterTagRemovers() {
    FilterTags.initTagRemovers();
}

/**
 * Active Filters Module
 * Handles the display and management of active filters
 */
const ActiveFilters = {
    /**
     * Update the active filters display
     */
    update() {
        const container = document.querySelector('.active-filters-container');
        if (!container) return;

        // Clear existing content
        container.innerHTML = '';

        // Set to track unique filter combinations (filter:value)
        const uniqueFilters = new Set();
        let hasActiveFilters = false;

        // Process all filter sources
        this.processUrlParameters(container, uniqueFilters, hasActiveFilters);
        this.processFormFields(container, uniqueFilters, hasActiveFilters);

        // Update UI state
        this.updateContainerVisibility(container, hasActiveFilters);
    },

    /**
     * Process URL parameters to find active filters
     * @param {HTMLElement} container - The container for filter tags
     * @param {Set} uniqueFilters - Set to track unique filter combinations
     * @param {boolean} hasActiveFilters - Flag indicating if active filters exist
     * @returns {boolean} - Updated hasActiveFilters flag
     */
    processUrlParameters(container, uniqueFilters, hasActiveFilters) {
        const urlParams = new URLSearchParams(window.location.search);
        let updatedHasActiveFilters = hasActiveFilters;

        for (const [key, value] of urlParams.entries()) {
            if (key !== 'page' && key !== 'per_page' && value) {
                updatedHasActiveFilters = true;

                if (key.endsWith('_list')) {
                    this.processListParameter(container, uniqueFilters, key, value);
                } else {
                    this.processSimpleParameter(container, uniqueFilters, key, value);
                }
            }
        }

        return updatedHasActiveFilters;
    },

    /**
     * Process current form field values
     * @param {HTMLElement} container - The container for filter tags
     * @param {Set} uniqueFilters - Set to track unique filter combinations
     * @param {boolean} hasActiveFilters - Flag indicating if active filters exist
     * @returns {boolean} - Updated hasActiveFilters flag
     */
    processFormFields(container, uniqueFilters, hasActiveFilters) {
        let updatedHasActiveFilters = hasActiveFilters;

        // Process text inputs
        document.querySelectorAll('input[type="text"][name]').forEach(input => {
            if (input.value) {
                const filterKey = `${input.name}:${input.value}`;
                if (!uniqueFilters.has(filterKey)) {
                    uniqueFilters.add(filterKey);
                    updatedHasActiveFilters = true;
                    FilterTags.createTag(container, input.name, null, input.value);
                }
            }
        });

        // Process select filters
        document.querySelectorAll('select.filter-select').forEach(select => {
            const values = jQuery(select).val();
            if (values && values.length) {
                updatedHasActiveFilters = true;
                values.forEach(value => {
                    const filterKey = `${select.name}:${value}`;
                    if (!uniqueFilters.has(filterKey)) {
                        uniqueFilters.add(filterKey);
                        const option = select.querySelector(`option[value="${value}"]`);
                        const displayText = option ? option.textContent : value;
                        FilterTags.createTag(container, select.name, value, displayText);
                    }
                });
            }
        });

        return updatedHasActiveFilters;
    },

    /**
     * Process list parameters (comma-separated values)
     * @param {HTMLElement} container - The container for filter tags
     * @param {Set} uniqueFilters - Set to track unique filter combinations
     * @param {string} key - The parameter key
     * @param {string} value - The parameter value
     */
    processListParameter(container, uniqueFilters, key, value) {
        const baseKey = key.replace('_list', '');
        const values = value.split(',');

        values.forEach(val => {
            if (val) {
                const filterKey = `${baseKey}:${val}`;
                if (!uniqueFilters.has(filterKey)) {
                    uniqueFilters.add(filterKey);
                    const select = document.getElementById(baseKey);
                    const option = select ? select.querySelector(`option[value="${val}"]`) : null;
                    const displayText = option ? option.textContent : val;
                    FilterTags.createTag(container, baseKey, val, displayText);
                }
            }
        });
    },

    /**
     * Process simple parameters (non-list)
     * @param {HTMLElement} container - The container for filter tags
     * @param {Set} uniqueFilters - Set to track unique filter combinations
     * @param {string} key - The parameter key
     * @param {string} value - The parameter value
     */
    processSimpleParameter(container, uniqueFilters, key, value) {
        const filterKey = `${key}:${value}`;
        if (!uniqueFilters.has(filterKey)) {
            uniqueFilters.add(filterKey);
            FilterTags.createTag(container, key, null, value);
        }
    },

    /**
     * Update UI state based on active filters
     * @param {HTMLElement} container - The container for filter tags
     * @param {boolean} hasActiveFilters - Flag indicating if active filters exist
     */
    updateContainerVisibility(container, hasActiveFilters) {
        // Show or hide the container
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

        // Update data attribute on advanced filters container
        const advancedFilters = document.getElementById('advancedFilters');
        if (advancedFilters) {
            advancedFilters.dataset.hasActiveFilters = hasActiveFilters.toString();
        }
    }
};

/**
 * Update the active filters display
 */
function updateActiveFiltersDisplay() {
    ActiveFilters.update();
}

/**
 * Feedback Module
 * Handles displaying feedback messages to the user
 */
const FeedbackManager = {
    /**
     * Show a feedback message to the user
     * @param {string} message - The message to display
     * @param {string} type - The type of message (info, success, warning, error)
     * @param {number} duration - How long to display the message in milliseconds
     */
    showMessage(message, type = 'info', duration = 1500) {
        // Create or reuse the message container
        let messageContainer = document.getElementById('filter-feedback-message');
        if (!messageContainer) {
            messageContainer = document.createElement('div');
            messageContainer.id = 'filter-feedback-message';
            messageContainer.className = 'toast-message';
            document.body.appendChild(messageContainer);
        }

        // Configure the message
        const icon = '<i class="bi bi-stars"></i>';  // Always use stars icon
        messageContainer.innerHTML = `${icon} ${message}`;
        messageContainer.className = `toast-message ${type} show`;

        // Apply styles - use CSS classes where possible
        const styles = {
            position: 'fixed',
            bottom: '24px',
            left: '50%',
            transform: 'translate(-50%, 100%)',
            zIndex: '9999',
            backgroundColor: '#1976D2',
            color: '#fff',
            padding: '14px 24px',
            borderRadius: '8px',
            minWidth: '200px',
            maxWidth: '600px',
            boxShadow: '0 3px 5px -1px rgba(25, 118, 210, 0.2), 0 6px 10px 0 rgba(25, 118, 210, 0.14), 0 1px 18px 0 rgba(25, 118, 210, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            fontSize: '15px',
            lineHeight: '1.4',
            fontWeight: '500',
            textAlign: 'center',
            transition: 'transform 0.15s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
            opacity: '0'
        };

        // Apply all styles at once
        Object.assign(messageContainer.style, styles);

        // Show animation
        requestAnimationFrame(() => {
            messageContainer.style.opacity = '1';
            messageContainer.style.transform = 'translate(-50%, 0)';
        });

        // Hide and remove after duration
        setTimeout(() => {
            messageContainer.style.opacity = '0';
            messageContainer.style.transform = 'translate(-50%, 100%)';

            // Remove from DOM after animation
            setTimeout(() => {
                if (messageContainer.parentNode) {
                    messageContainer.parentNode.removeChild(messageContainer);
                }
            }, 150);
        }, duration);
    },

    /**
     * Initialize the feedback styles
     */
    initStyles() {
        const style = document.createElement('style');
        style.textContent = `
            @keyframes sparkle {
                0%, 100% { transform: scale(1) rotate(0deg); }
                25% { transform: scale(1.2) rotate(-5deg); }
                50% { transform: scale(1.1) rotate(5deg); }
                75% { transform: scale(1.2) rotate(-3deg); }
            }

            .toast-message i {
                font-size: 1.2em;
                margin-right: 4px;
                animation: sparkle 2s infinite;
                display: inline-block;
                color: #fff;
            }

            .toast-message.success {
                background-color: #1976D2 !important;
            }

            .toast-message.info {
                background-color: #1976D2 !important;
            }

            .toast-message.warning {
                background-color: #1976D2 !important;
            }

            .toast-message {
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.1);
            }
        `;
        document.head.appendChild(style);
    }
};

// Initialize feedback styles
FeedbackManager.initStyles();

/**
 * Show a feedback message to the user (legacy function for backward compatibility)
 * @param {string} message - The message to display
 * @param {string} type - The type of message (info, success, warning, error)
 * @param {number} duration - How long to display the message in milliseconds
 */
function showFeedbackMessage(message, type = 'info', duration = 1500) {
    FeedbackManager.showMessage(message, type, duration);
}

// Initialize the reset filters button with enhanced feedback
function initResetFiltersButton() {
    const resetButton = document.getElementById('resetFilters');

    if (resetButton) {
        resetButton.addEventListener('click', function (e) {
            e.preventDefault();

            // Add button press effect
            this.classList.add('btn-press-effect');

            // Clear all selects
            if (typeof jQuery !== 'undefined' && typeof jQuery.fn.select2 !== 'undefined') {
                jQuery('.filter-select').val(null).trigger('change');
            } else {
                document.querySelectorAll('.filter-select').forEach(function (select) {
                    select.selectedIndex = -1;
                });
            }

            // Reset text inputs
            document.querySelectorAll('input[type="text"]').forEach(function (input) {
                input.value = '';
            });

            // Show feedback message with success style
            showFeedbackMessage('Clearing filters...', 'success');

            // Animate filter cards reset
            const filterCards = document.querySelectorAll('.filter-card');
            filterCards.forEach((card, index) => {
                setTimeout(() => {
                    card.classList.add('filter-card-reset');
                    setTimeout(() => {
                        card.classList.remove('filter-card-reset');
                    }, 300);
                }, index * 50);
            });

            setTimeout(() => {
                // Remove button effect
                resetButton.classList.remove('btn-press-effect');

                // Submit the form
                document.getElementById('filter-form').submit();
            }, 300);
        });
    }
}

/**
 * Initialize apply filters button with enhanced feedback
 */
function initApplyFiltersButton() {
    const applyButton = document.querySelector('.filter-actions button[type="submit"]');
    const filterForm = document.getElementById('filter-form');

    if (applyButton && filterForm) {
        applyButton.addEventListener('click', function (e) {
            e.preventDefault();

            // Add button press effect
            this.classList.add('btn-press-effect');

            // Show feedback message
            showFeedbackMessage('Applying filters...', 'info');

            // Animate filter cards
            const filterCards = document.querySelectorAll('.filter-card');
            filterCards.forEach((card, index) => {
                setTimeout(() => {
                    card.style.transition = 'transform 0.2s ease';
                    card.style.transform = 'scale(0.98)';
                    setTimeout(() => {
                        card.style.transform = 'scale(1)';
                    }, 200);
                }, index * 50);
            });

            // Collect and merge filters
            const currentFilters = collectCurrentFilters();
            const mergedFilters = mergeFilters(currentFilters);

            // Update form with merged filters
            updateFormWithFilters(mergedFilters);

            setTimeout(() => {
                // Remove button effect
                this.classList.remove('btn-press-effect');

                // Submit the form
                filterForm.submit();
            }, 300);
        });
    }
}

/**
 * Collect current filter values from the form
 */
function collectCurrentFilters() {
    const filters = {
        textFilters: {},
        multiSelectFilters: {}
    };

    // Collect text input filters
    document.querySelectorAll('input[type="text"][name]').forEach(input => {
        if (input.value) {
            filters.textFilters[input.name] = input.value;
        }
    });

    // Collect multi-select filters
    document.querySelectorAll('select.filter-select').forEach(select => {
        const values = jQuery(select).val();
        if (values && values.length) {
            filters.multiSelectFilters[select.name] = values;
        }
    });

    return filters;
}

/**
 * Merge current filters with existing URL parameters
 */
function mergeFilters(currentFilters) {
    const urlParams = new URLSearchParams(window.location.search);
    const mergedFilters = {
        textFilters: { ...currentFilters.textFilters },
        multiSelectFilters: { ...currentFilters.multiSelectFilters }
    };

    // Process URL parameters
    for (const [key, value] of urlParams.entries()) {
        // Skip pagination params
        if ([PaginationManager.PAGINATION_PARAMS.PAGE, PaginationManager.PAGINATION_PARAMS.PER_PAGE].includes(key)) continue;

        // Handle text filters
        if (key in currentFilters.textFilters) {
            if (!mergedFilters.textFilters[key]) {
                mergedFilters.textFilters[key] = value;
            }
        }
        // Handle multi-select filters
        else {
            if (!mergedFilters.multiSelectFilters[key]) {
                mergedFilters.multiSelectFilters[key] = [];
            }
            if (!mergedFilters.multiSelectFilters[key].includes(value)) {
                mergedFilters.multiSelectFilters[key].push(value);
            }
        }
    }

    return mergedFilters;
}

/**
 * Update form with merged filter values
 */
function updateFormWithFilters(filters) {
    const form = document.getElementById('filter-form');
    if (!form) return;

    // Clear existing hidden inputs
    form.querySelectorAll('input[type="hidden"]').forEach(input => {
        if (input.name !== 'csrfmiddlewaretoken') {
            input.remove();
        }
    });

    // Always reset to page 1 when changing filters
    const pageInput = document.createElement('input');
    pageInput.type = 'hidden';
    pageInput.name = PaginationManager.PAGINATION_PARAMS.PAGE;
    pageInput.value = "1";
    form.appendChild(pageInput);

    // Get current per_page setting
    const perPageDropdown = document.getElementById('rowsPerPageDropdown');
    if (perPageDropdown && perPageDropdown.dataset.currentPerPage) {
        const perPageInput = document.createElement('input');
        perPageInput.type = 'hidden';
        perPageInput.name = PaginationManager.PAGINATION_PARAMS.PER_PAGE;
        perPageInput.value = perPageDropdown.dataset.currentPerPage;
        form.appendChild(perPageInput);
    }

    // Add text filters
    for (const [key, value] of Object.entries(filters.textFilters)) {
        const input = document.querySelector(`input[name="${key}"]`);
        if (input) {
            input.value = value;
        } else {
            const hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = key;
            hiddenInput.value = value;
            form.appendChild(hiddenInput);
        }
    }

    // Add multi-select filters
    for (const [key, values] of Object.entries(filters.multiSelectFilters)) {
        const select = document.getElementById(key);
        if (select) {
            jQuery(select).val(values).trigger('change');
        } else {
            values.forEach(value => {
                const hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = key;
                hiddenInput.value = value;
                form.appendChild(hiddenInput);
            });
        }
    }
}

/**
 * Data Extraction Module
 * Handles extracting sample data from table rows
 */
const DataExtractor = {
    /**
     * Extract sample data from a table row
     * @param {HTMLElement} row - The table row element to extract data from
     * @returns {Object|null} - The extracted sample data or null if error
     */
    getSampleDataFromRow(row) {
        if (!row) {
            console.error('No row provided to getSampleDataFromRow');
            return null;
        }

        // Initialize data object with empty fields
        let data = {
            fastqName: null,
            studySet: null,
            loadName: null,
            batchNameFromVendor: null,
            libraryPrepMethod: null,
            organismCommonName: null,
            ingestStatus: null,
            alignmentStatus: null,
            postqcStatus: null
        };

        // Define attribute mappings once - used for both data extraction and logging
        const attributeMappings = {
            fastqName: ['data-fastq-name'],
            studySet: ['data-study-set'],
            loadName: ['data-load-name'],
            batchNameFromVendor: ['data-batch-name-from-vendor'],
            organismCommonName: ['data-organism-common-name'],
            libraryPrepMethod: ['data-library-prep-method'],
            ingestStatus: ['data-ingest-status'],
            alignmentStatus: ['data-alignment-status'],
            postqcStatus: ['data-postqc-status']
        };

        // Define header text to field name mappings - same keys as data object
        const headerMappings = {
            'fastq name': 'fastqName',
            'study set': 'studySet',
            'load name': 'loadName',
            'batch name from vendor': 'batchNameFromVendor',
            'organism common name': 'organismCommonName',
            'library prep method': 'libraryPrepMethod',
            'ingest status': 'ingestStatus',
            'alignment status': 'alignmentStatus',
            'postqc status': 'postqcStatus'
        };

        // For debugging only
        const DEBUG_SAMPLE_EXTRACTION = window.DEBUG_MODE || OCSBrowser.config.debug;

        if (DEBUG_SAMPLE_EXTRACTION) {
            Utils.logDebug('Row element:', row);
            Utils.logDebug('=== All Row Data Attributes ===');
        }

        // STEP 1: Extract data from HTML attributes
        for (const [field, attributes] of Object.entries(attributeMappings)) {
            for (const attr of attributes) {
                const value = row.getAttribute(attr);

                if (DEBUG_SAMPLE_EXTRACTION) {
                    Utils.logDebug(`${field} (${attr}): ${value}`);
                }

                // Set data if value exists
                if (value) {
                    data[field] = value;
                    break; // Stop checking other attributes for this field
                }
            }
        }

        // STEP 2: If attributes not complete, extract from table cells
        const cells = row.querySelectorAll('td');
        if (cells.length > 0) {
            // Create a mapping from header text to column index
            const columnMap = {};
            const table = row.closest('table');

            if (DEBUG_SAMPLE_EXTRACTION) {
                Utils.logDebug('=== Table Cell Contents ===');
                cells.forEach((cell, index) => {
                    Utils.logDebug(`Cell ${index}: ${cell.textContent.trim()}`);
                });
            }

            if (table) {
                const headerRow = table.querySelector('thead tr');
                if (headerRow) {
                    const headerCells = headerRow.querySelectorAll('th');

                    if (DEBUG_SAMPLE_EXTRACTION) {
                        Utils.logDebug('=== Header Cell Mapping ===');
                        headerCells.forEach((cell, index) => {
                            Utils.logDebug(`Header ${index}: ${cell.textContent.trim()}`);
                        });
                    }

                    // Map each header to a field
                    headerCells.forEach((cell, index) => {
                        const headerText = cell.textContent.trim().toLowerCase();

                        for (const [text, field] of Object.entries(headerMappings)) {
                            if (headerText.includes(text)) {
                                // Skip library prep method ID
                                if (field === 'libraryPrepMethod' && headerText === 'library prep method id') {
                                    continue;
                                }
                                columnMap[field] = index;

                                if (DEBUG_SAMPLE_EXTRACTION) {
                                    Utils.logDebug(`Mapped ${headerText} to ${field} at index ${index}`);
                                }
                                break;
                            }
                        }
                    });

                    if (DEBUG_SAMPLE_EXTRACTION) {
                        Utils.logDebug('=== Column Mapping ===', columnMap);
                    }

                    // Extract data from cells based on the mapping (only if not already set from attributes)
                    for (const [field, index] of Object.entries(columnMap)) {
                        if (!data[field] && cells[index]) {
                            data[field] = cells[index].textContent.trim();

                            if (DEBUG_SAMPLE_EXTRACTION) {
                                Utils.logDebug(`Extracted from cell - ${field}: ${data[field]}`);
                            }
                        }
                    }
                }
            }
        }

        // STEP 3: Set ID and name if not already set
        if (!data.id) {
            data.id = data.fastqName || `row-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }
        if (!data.name) {
            data.name = data.fastqName || data.id;
        }

        // STEP 4: Ensure all properties are strings (instead of null/undefined)
        for (const key in data) {
            data[key] = data[key] || '';
        }

        if (DEBUG_SAMPLE_EXTRACTION) {
            Utils.logDebug('=== Final Extracted and Cleaned Data ===', data);
        }

        return data;
    }
};

/**
 * Helper function to extract sample data from a row (legacy function for backward compatibility)
 * @param {HTMLElement} row - The table row element to extract data from
 * @returns {Object|null} - The extracted sample data or null if error
 */
function getSampleDataFromRow(row) {
    return DataExtractor.getSampleDataFromRow(row);
}

/**
 * Initializes the floating selection action panel
 */
function initSelectionPanel() {
    Utils.logDebug('initSelectionPanel called');

    // Get required elements
    const selectionPanel = Utils.getElement('#selection-actions', 'Selection panel');
    const selectionCount = Utils.getElement('#selected-count', 'Selection count');
    const clearSelectionBtn = Utils.getElement('#clear-selection-btn', 'Clear selection button');
    const sendToPipelineBtn = Utils.getElement('#send-to-pipeline-btn', 'Send to pipeline button');
    const selectAllCheckbox = Utils.getElement('#select-all-samples', 'Select all checkbox');

    if (!selectionPanel) return;

    // Check if we're on the main sample page by looking for sample checkboxes
    const checkboxes = document.querySelectorAll('.sample-select');
    Utils.logDebug('Found sample checkboxes:', checkboxes.length);

    if (!checkboxes.length) {
        Utils.logDebug('No sample checkboxes found, exiting');
        return;
    }

    // Initialize panel state
    selectionPanel.style.display = 'none';
    window.selectedSamples = window.selectedSamples || [];
    selectedSamples = window.selectedSamples; // Ensure we're using the same reference

    // Initialize from current checkbox state
    initializeFromCheckboxState();

    // Set up event handlers
    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', handleClearSelection);
    }

    if (sendToPipelineBtn) {
        sendToPipelineBtn.addEventListener('click', handleSendToPipeline);
    }

    // Initialize sample checkboxes
    initializeSampleCheckboxes();

    // Initialize "Select All" checkbox
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', handleSelectAllChange);
    }

    // Initial update of panel
    updateSelectionPanel();

    // Helper functions

    /**
     * Initialize selected samples from current checkbox state
     */
    function initializeFromCheckboxState() {
        document.querySelectorAll('.sample-select').forEach(checkbox => {
            if (checkbox.id === 'select-all-samples') return;

            if (checkbox.checked) {
                const row = checkbox.closest('tr');
                if (row) {
                    const data = getSampleDataFromRow(row);
                    if (data && data.id && !selectedSamples.some(s => s.id === data.id)) {
                        selectedSamples.push(data);
                    }
                }
            }
        });
    }

    /**
     * Handle clicking the clear selection button
     */
    function handleClearSelection() {
        // Uncheck all checkboxes
        document.querySelectorAll('.sample-select').forEach(checkbox => {
            if (checkbox.id !== 'select-all-samples') {
                checkbox.checked = false;
            }
        });

        // Clear "Select All" checkbox
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }

        // Update selection panel
        selectedSamples.length = 0; // Clear array without reassigning
        updateSelectionPanel();
    }

    /**
     * Set up event handlers for individual sample checkboxes
     */
    function initializeSampleCheckboxes() {
        document.querySelectorAll('.sample-select').forEach(checkbox => {
            // Skip the select all checkbox
            if (checkbox.id === 'select-all-samples') return;

            checkbox.addEventListener('change', function () {
                const row = this.closest('tr');
                if (!row) {
                    console.error('No parent row found for checkbox');
                    return;
                }

                const data = getSampleDataFromRow(row);
                if (!data || !data.id) {
                    console.error('Invalid sample data extracted from row');
                    return;
                }

                if (this.checked) {
                    // Add to selected samples if not already there
                    if (!selectedSamples.some(s => s.id === data.id)) {
                        Utils.logDebug('Adding sample to selection:', data.id);
                        selectedSamples.push(data);
                    }
                } else {
                    // Remove from selected samples
                    Utils.logDebug('Removing sample from selection:', data.id);
                    selectedSamples = selectedSamples.filter(s => s.id !== data.id);
                }

                updateSelectionPanel();
            });
        });
    }

    /**
     * Handle changes to "Select All" checkbox
     */
    function handleSelectAllChange() {
        // Don't reset the array, just clear its contents
        selectedSamples.length = 0;

        document.querySelectorAll('.sample-select').forEach(checkbox => {
            // Skip the select all checkbox itself
            if (checkbox.id === 'select-all-samples') return;

            checkbox.checked = selectAllCheckbox.checked;

            if (selectAllCheckbox.checked) {
                const row = checkbox.closest('tr');
                if (row) {
                    const data = getSampleDataFromRow(row);
                    if (data && data.id) {
                        selectedSamples.push(data);
                    }
                }
            }
        });

        Utils.logDebug('Select all changed, selectedSamples count:', selectedSamples.length);
        updateSelectionPanel();
    }

    /**
     * Handle sending selected samples to pipeline
     */
    function handleSendToPipeline() {
        if (selectedSamples.length === 0) {
            showFeedbackMessage('No samples selected', 'warning');
            return;
        }

        // Show loading state
        sendToPipelineBtn.disabled = true;
        sendToPipelineBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';

        // Process samples in batches
        processSamplesInBatches();
    }

    /**
     * Process samples in batches to avoid UI blocking
     */
    function processSamplesInBatches() {
        const cleanedSamples = [];
        const batchSize = 200;
        let currentBatch = 0;

        processBatch();

        function processBatch() {
            const startIdx = currentBatch * batchSize;
            const endIdx = Math.min(startIdx + batchSize, selectedSamples.length);

            // Process this batch
            for (let i = startIdx; i < endIdx; i++) {
                const sample = selectedSamples[i];
                // Check if sample exists and has expected properties
                if (!sample) {
                    continue;
                }

                // Map to pipeline format with essential fields only
                const cleanedSample = {
                    fastq_name: sample.fastqName || '',
                    study_set: sample.studySet || '',
                    load_name: sample.loadName || '',
                    batch_name_from_vendor: sample.batchNameFromVendor || '',
                    organism_common_name: sample.organismCommonName || '',
                    library_prep_method: sample.libraryPrepMethod || '',
                    ingest_status: sample.ingestStatus || 'Not Started',
                    alignment_status: sample.alignmentStatus || 'Not Started',
                    postqc_status: sample.postqcStatus || 'Not Started'
                };

                cleanedSamples.push(cleanedSample);
            }

            // Check if we're done
            if (endIdx >= selectedSamples.length) {
                finalizeSending();
            } else {
                // Move to next batch
                currentBatch++;
                setTimeout(processBatch, 0);
            }
        }

        function finalizeSending() {
            // Store cleaned samples in localStorage
            const storageItem = {
                timestamp: new Date().getTime(),
                samples: cleanedSamples
            };

            try {
                // Verify we have data before saving
                if (cleanedSamples.length === 0) {
                    showFeedbackMessage('No samples to send to pipeline', 'warning');
                    sendToPipelineBtn.disabled = false;
                    sendToPipelineBtn.innerHTML = 'Send to Pipeline <i class="bi bi-arrow-right"></i>';
                    return;
                }

                // Store the data using the standardized key
                localStorage.setItem('pipelineSelectedSamples', JSON.stringify(cleanedSamples));

                // Verify data was saved correctly
                const verifyData = localStorage.getItem('pipelineSelectedSamples');
                if (!verifyData) {
                    throw new Error('Failed to verify saved data');
                }

                const verifiedSamples = JSON.parse(verifyData);

                showFeedbackMessage(`${selectedSamples.length} samples sent to Pipeline Dashboard`, 'success');

                // Redirect to pipeline dashboard
                setTimeout(() => {
                    window.location.href = '/pipeline/';
                }, 300);
            } catch (error) {
                console.error('Error storing samples:', error);

                // Handle storage errors
                if (error.name === 'QuotaExceededError' || error.code === 22) {
                    handleStorageFullError();
                } else {
                    showFeedbackMessage('Error sending samples to pipeline', 'danger');
                    sendToPipelineBtn.disabled = false;
                    sendToPipelineBtn.innerHTML = 'Send to Pipeline <i class="bi bi-arrow-right"></i>';
                }
            }
        }

        function handleStorageFullError() {
            // Try with a reduced sample set
            const reducedSamples = cleanedSamples.slice(0, 1000);
            try {
                localStorage.setItem('pipelineSelectedSamples', JSON.stringify(reducedSamples));

                showFeedbackMessage(`Storage limit reached. Only first 1000 samples will be processed.`, 'warning');
                setTimeout(() => {
                    window.location.href = '/pipeline/';
                }, 1000);
            } catch (error) {
                // If still failing, show error
                console.error('Still failed with reduced set:', error);
                showFeedbackMessage('Storage limit exceeded. Please select fewer samples.', 'danger');
                sendToPipelineBtn.disabled = false;
                sendToPipelineBtn.innerHTML = 'Send to Pipeline <i class="bi bi-arrow-right"></i>';
            }
        }
    }

    // Streamlined selection panel update function
    function updateSelectionPanel() {
        const selectionPanel = Utils.getElement('#selection-actions', 'Selection panel');
        const selectionCount = Utils.getElement('#selected-count', 'Selection count');

        if (!selectionPanel || !selectedSamples) return;

        Utils.logDebug('updateSelectionPanel called with', selectedSamples.length);

        // Filter out any invalid entries (missing id) - use filter without reassignment
        const validSamples = selectedSamples.filter(sample => sample && sample.id);

        // If some samples were invalid, replace the array contents
        if (validSamples.length !== selectedSamples.length) {
            selectedSamples.length = 0;
            selectedSamples.push(...validSamples);
        }

        if (selectedSamples.length > 0) {
            selectionPanel.style.display = 'flex';
            if (selectionCount) {
                selectionCount.textContent = selectedSamples.length;
            }
        } else {
            selectionPanel.style.display = 'none';
        }
    }
}
