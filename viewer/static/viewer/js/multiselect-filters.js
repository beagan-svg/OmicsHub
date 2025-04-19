// Modern filters script with enhanced UI/UX for card-based layout
console.log('Loading enhanced filter script with card animations...');

document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM loaded, initializing filters');

    // Toggle advanced filters
    initAdvancedFiltersToggle();

    // Initialize Select2 with enhanced settings
    initEnhancedSelect2();

    // Initialize filter tag removers
    initFilterTagRemovers();

    // Initialize reset filters button
    initResetFiltersButton();

    // Initialize apply filters button
    initApplyFiltersButton();

    // Initialize active filters display
    updateActiveFiltersDisplay();

    // Initialize card hover animations
    initCardAnimations();

    // Initialize selection panel if it exists
    initSelectionPanel();
});

// Initialize the advanced filters toggle with animation
function initAdvancedFiltersToggle() {
    const toggleButton = document.getElementById('toggleAdvancedFilters');
    const filtersPanel = document.getElementById('advancedFilters');

    if (!toggleButton || !filtersPanel) {
        console.error('Toggle button or filters panel not found');
        return;
    }

    // Click event for the toggle button
    toggleButton.addEventListener('click', function () {
        if (filtersPanel.style.display === 'none' || !filtersPanel.style.display) {
            // Show with smooth animation
            filtersPanel.style.display = 'block';
            filtersPanel.style.opacity = '0';
            filtersPanel.style.transform = 'translateY(-20px)';

            // Animate filter cards sequentially
            const filterCards = filtersPanel.querySelectorAll('.filter-card');

            setTimeout(() => {
                filtersPanel.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                filtersPanel.style.opacity = '1';
                filtersPanel.style.transform = 'translateY(0)';

                // Animate each card with a slight delay
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

            toggleButton.innerHTML = '<i class="bi bi-sliders"></i> <span>Hide Filters</span>';
            localStorage.setItem('showAdvancedFilters', 'true');
        } else {
            // Hide with smooth animation
            filtersPanel.style.opacity = '0';
            filtersPanel.style.transform = 'translateY(-20px)';

            setTimeout(() => {
                filtersPanel.style.display = 'none';
                filtersPanel.style.transition = '';
            }, 300);

            toggleButton.innerHTML = '<i class="bi bi-sliders"></i> <span>Advanced Filters</span>';
            localStorage.setItem('showAdvancedFilters', 'false');
        }
    });

    // Initialize from localStorage or data attribute
    const shouldShowFilters =
        localStorage.getItem('showAdvancedFilters') === 'true' ||
        (filtersPanel.dataset && filtersPanel.dataset.hasActiveFilters === 'true');

    if (shouldShowFilters) {
        filtersPanel.style.display = 'block';
        toggleButton.innerHTML = '<i class="bi bi-sliders"></i> <span>Hide Filters</span>';
    }
}

// Initialize Select2 dropdowns with enhanced styling and functionality
function initEnhancedSelect2() {
    if (typeof jQuery !== 'undefined' && typeof jQuery.fn.select2 !== 'undefined') {
        console.log('Initializing enhanced Select2');

        // Stylish configuration for Select2
        jQuery('.filter-select').select2({
            theme: 'bootstrap4',
            width: '100%',
            placeholder: 'Select options',
            allowClear: true,
            closeOnSelect: false,
            templateResult: formatSelectOption,
            templateSelection: formatSelectOption,
            dropdownCssClass: 'enhanced-dropdown',
            selectionCssClass: 'select2-selection-fixed-height',
            minimumResultsForSearch: 5,
            containerCssClass: 'select2-fixed-height'
        });

        // Fix placeholder appearance
        jQuery('.filter-select').on('select2:open', function () {
            document.querySelector('.select2-search__field').placeholder = 'Search...';
        });

        // Handle on-change events for dynamic interface updates
        jQuery('.filter-select').on('change', function () {
            // Update highlighting
            updateFilterHighlighting(this);

            // Update active filters display
            updateActiveFiltersDisplay();

            // Fix height if needed after selection
            fixSelectHeight(this);
        });

        // Initialize filter highlighting
        jQuery('.filter-select').each(function () {
            updateFilterHighlighting(this);
            fixSelectHeight(this);
        });
    } else {
        console.warn('Select2 or jQuery not available');
    }
}

// Fix select2 height to ensure consistent appearance
function fixSelectHeight(selectElement) {
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
}

// Initialize animations for filter cards
function initCardAnimations() {
    const filterCards = document.querySelectorAll('.filter-card');

    filterCards.forEach(card => {
        // Add subtle animation on hover
        card.addEventListener('mouseenter', function () {
            this.style.transition = 'transform 0.3s ease, box-shadow 0.3s ease';
        });

        // Add focus effect when clicking on any input inside the card
        const inputs = card.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('focus', function () {
                card.classList.add('filter-card-focus');
            });

            input.addEventListener('blur', function () {
                card.classList.remove('filter-card-focus');
            });
        });
    });
}

// Format select options with color-coding for status fields
function formatSelectOption(option) {
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
}

// Update the visual highlighting of filter fields based on selection state
function updateFilterHighlighting(selectElement) {
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

// Initialize filter tag removal functionality
function initFilterTagRemovers() {
    const filterTags = document.querySelectorAll('.tag-remove');

    filterTags.forEach(function (tag) {
        tag.addEventListener('click', function () {
            const filter = this.dataset.filter;
            const value = this.dataset.value;

            if (value) {
                // For multi-select filters, remove just this value
                const select = document.getElementById(filter);
                if (select && typeof jQuery !== 'undefined') {
                    // Get current values
                    let currentValues = jQuery(select).val() || [];
                    // Find and remove the value
                    currentValues = currentValues.filter(item => item !== value);
                    // Set the new values
                    jQuery(select).val(currentValues).trigger('change');
                }
            } else {
                // For text inputs, clear the field
                const input = document.querySelector(`[name="${filter}"]`);
                if (input) {
                    input.value = '';
                }
            }

            // Show the removal effect before submitting
            const tagElement = this.closest('.filter-tag');
            tagElement.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
            tagElement.style.transform = 'translateX(-10px)';
            tagElement.style.opacity = '0';

            setTimeout(() => {
                // Submit the form
                document.getElementById('filter-form').submit();
            }, 200);
        });
    });
}

// Create and update the active filters display
function updateActiveFiltersDisplay() {
    const container = document.querySelector('.active-filters-container');
    if (!container) return;

    // Clear existing content
    container.innerHTML = '';

    // Check URL parameters first
    const urlParams = new URLSearchParams(window.location.search);
    let hasActiveFilters = false;

    // Set to track unique filter combinations (filter:value)
    const uniqueFilters = new Set();

    // Process URL parameters
    for (const [key, value] of urlParams.entries()) {
        if (key !== 'page' && key !== 'per_page' && value) {
            hasActiveFilters = true;
            // For multi-select parameters that end with _list
            if (key.endsWith('_list')) {
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
                            createFilterTag(container, baseKey, val, displayText);
                        }
                    }
                });
            } else {
                const filterKey = `${key}:${value}`;
                if (!uniqueFilters.has(filterKey)) {
                    uniqueFilters.add(filterKey);
                    createFilterTag(container, key, null, value);
                }
            }
        }
    }

    // Process text filters
    document.querySelectorAll('input[type="text"][name]').forEach(input => {
        if (input.value) {
            const filterKey = `${input.name}:${input.value}`;
            if (!uniqueFilters.has(filterKey)) {
                uniqueFilters.add(filterKey);
                hasActiveFilters = true;
                createFilterTag(container, input.name, null, input.value);
            }
        }
    });

    // Process select filters
    document.querySelectorAll('select.filter-select').forEach(select => {
        const values = jQuery(select).val();
        if (values && values.length) {
            hasActiveFilters = true;
            values.forEach(value => {
                const filterKey = `${select.name}:${value}`;
                if (!uniqueFilters.has(filterKey)) {
                    uniqueFilters.add(filterKey);
                    // Find the option text for this value
                    const option = select.querySelector(`option[value="${value}"]`);
                    const displayText = option ? option.textContent : value;
                    createFilterTag(container, select.name, value, displayText);
                }
            });
        }
    });

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

    // Update the data attribute on the advanced filters container
    const advancedFilters = document.getElementById('advancedFilters');
    if (advancedFilters) {
        advancedFilters.dataset.hasActiveFilters = hasActiveFilters.toString();
    }
}

// Create a filter tag element
function createFilterTag(container, filter, value, displayText) {
    const tag = document.createElement('div');
    tag.className = 'filter-tag';

    // Get friendly name for the filter
    const filterLabel = document.querySelector(`label[for="${filter}"]`);
    const filterName = filterLabel ? filterLabel.textContent : formatLabelFromName(filter);

    tag.innerHTML = `
        <span class="tag-name">${filterName}:</span>
        <span class="tag-value">${displayText}</span>
    `;

    container.appendChild(tag);

    // Add appearance animation
    tag.style.opacity = '0';
    tag.style.transform = 'translateY(10px)';

    setTimeout(() => {
        tag.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
        tag.style.opacity = '1';
        tag.style.transform = 'translateY(0)';
    }, 10);
}

// Format a field name into a friendly label
function formatLabelFromName(name) {
    return name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

// Show a feedback message to the user
function showFeedbackMessage(message, type = 'info') {
    // Create or get the message container
    let messageContainer = document.getElementById('filter-feedback-message');

    if (!messageContainer) {
        messageContainer = document.createElement('div');
        messageContainer.id = 'filter-feedback-message';
        messageContainer.className = 'toast-message';
        document.body.appendChild(messageContainer);
    }

    // Set message content with enhanced icons
    let icon = '<i class="bi bi-stars"></i>';  // Always use stars icon for filter operations

    messageContainer.innerHTML = `${icon} ${message}`;
    messageContainer.className = `toast-message ${type} show`;

    // Google Material Design style positioning and appearance
    messageContainer.style.position = 'fixed';
    messageContainer.style.bottom = '24px';
    messageContainer.style.left = '50%';
    messageContainer.style.transform = 'translate(-50%, 100%)';
    messageContainer.style.zIndex = '9999';

    // Updated styling to match page theme
    messageContainer.style.backgroundColor = '#1976D2';
    messageContainer.style.color = '#fff';
    messageContainer.style.padding = '14px 24px';
    messageContainer.style.borderRadius = '8px';
    messageContainer.style.minWidth = '200px';
    messageContainer.style.maxWidth = '600px';
    messageContainer.style.boxShadow = '0 3px 5px -1px rgba(25, 118, 210, 0.2), 0 6px 10px 0 rgba(25, 118, 210, 0.14), 0 1px 18px 0 rgba(25, 118, 210, 0.12)';
    messageContainer.style.display = 'flex';
    messageContainer.style.alignItems = 'center';
    messageContainer.style.justifyContent = 'center';
    messageContainer.style.gap = '12px';
    messageContainer.style.fontSize = '15px';
    messageContainer.style.lineHeight = '1.4';
    messageContainer.style.fontWeight = '500';
    messageContainer.style.textAlign = 'center';
    messageContainer.style.transition = 'transform 0.15s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1)';
    messageContainer.style.opacity = '0';

    // Slide up animation
    requestAnimationFrame(() => {
        messageContainer.style.opacity = '1';
        messageContainer.style.transform = 'translate(-50%, 0)';
    });

    // Hide with slide down animation after 1.5 seconds
    setTimeout(() => {
        messageContainer.style.opacity = '0';
        messageContainer.style.transform = 'translate(-50%, 100%)';

        // Remove from DOM after animation
        setTimeout(() => {
            if (messageContainer.parentNode) {
                messageContainer.parentNode.removeChild(messageContainer);
            }
        }, 150);
    }, 1500);  // Changed from 3000 to 1500 for faster disappearance
}

// Add styles to the document
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

// Initialize the apply filters button with feedback
function initApplyFiltersButton() {
    const applyButton = document.querySelector('.filter-actions button[type="submit"]');

    if (applyButton) {
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

            setTimeout(() => {
                // Remove button effect
                this.classList.remove('btn-press-effect');

                // Submit the form
                document.getElementById('filter-form').submit();
            }, 300);
        });
    }
}

/**
 * Initializes the floating selection action panel
 */
function initSelectionPanel() {
    console.log('initSelectionPanel called');

    const selectionPanel = document.getElementById('selection-actions');
    console.log('Selection panel element:', selectionPanel);

    if (!selectionPanel) return;

    // Check if we're on the main sample page by looking for sample checkboxes
    const checkboxes = document.querySelectorAll('.sample-select');
    console.log('Found sample checkboxes:', checkboxes.length);

    const hasSampleCheckboxes = checkboxes.length > 0;
    if (!hasSampleCheckboxes) {
        console.log('No sample checkboxes found, exiting');
        return;
    }

    const selectionCount = document.getElementById('selected-count');
    console.log('Selection count element:', selectionCount);

    const clearSelectionBtn = document.getElementById('clear-selection-btn');
    console.log('Clear selection button:', clearSelectionBtn);

    const sendToPipelineBtn = document.getElementById('send-to-pipeline-btn');
    console.log('Send to pipeline button:', sendToPipelineBtn);

    // Initialize panel state
    selectionPanel.style.display = 'none';
    let selectedSamples = [];

    // Initialize from current checkbox state
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

    // Initial update of panel
    updateSelectionPanel();

    // Handle clear selection button
    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', function () {
            // Uncheck all checkboxes
            document.querySelectorAll('.sample-select').forEach(checkbox => {
                if (checkbox.id !== 'select-all-samples') { // Skip the select all checkbox
                    checkbox.checked = false;
                }
            });

            // Clear "Select All" checkbox
            const selectAllCheckbox = document.getElementById('select-all-samples');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }

            // Update selection panel
            selectedSamples = [];
            updateSelectionPanel();
        });
    }

    // Handle send to pipeline button
    if (sendToPipelineBtn) {
        sendToPipelineBtn.addEventListener('click', function () {
            if (selectedSamples.length === 0) {
                showFeedbackMessage('No samples selected', 'warning');
                return;
            }

            // Show loading state
            sendToPipelineBtn.disabled = true;
            sendToPipelineBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';

            // Convert selected samples to pipeline format more efficiently
            const cleanedSamples = [];

            // Process in batches to avoid blocking the UI
            const batchSize = 200;
            let currentBatch = 0;

            function processBatch() {
                const startIdx = currentBatch * batchSize;
                const endIdx = Math.min(startIdx + batchSize, selectedSamples.length);

                // Process this batch
                for (let i = startIdx; i < endIdx; i++) {
                    const sample = selectedSamples[i];
                    // Map to pipeline format with essential fields only
                    cleanedSamples.push({
                        id: sample.id || '',
                        name: sample.name || sample.id || '',
                        studySet: sample.studySet || '',
                        loadName: sample.loadName || '',
                        batchName: sample.batchName || '',
                        ingestStatus: sample.organism || 'Unknown', // Field-mapping correction
                        libraryPrep: sample.libraryPrep || 'Unknown'
                    });
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
                // Store cleaned samples in localStorage efficiently
                // Use a slimmer format to avoid size limitations
                const storageItem = {
                    timestamp: new Date().getTime(),
                    samples: cleanedSamples
                };

                try {
                    // Stringify and store the data
                    localStorage.setItem('selectedSamplesForPipeline', JSON.stringify(storageItem));

                    // Show feedback message
                    showFeedbackMessage(`${selectedSamples.length} samples sent to Pipeline Dashboard`, 'success');

                    // Redirect to pipeline dashboard with minimal delay
                    setTimeout(() => {
                        window.location.href = '/pipeline/';
                    }, 300);
                } catch (error) {
                    // Handle storage errors
                    console.error('Error storing samples:', error);

                    // If storage is full, try to store only most essential data
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
                // Try with a reduced sample set (first 1000 samples only)
                const reducedSamples = cleanedSamples.slice(0, 1000);
                try {
                    localStorage.setItem('selectedSamplesForPipeline', JSON.stringify({
                        timestamp: new Date().getTime(),
                        samples: reducedSamples
                    }));

                    showFeedbackMessage(`Storage limit reached. Only first 1000 samples will be processed.`, 'warning');

                    setTimeout(() => {
                        window.location.href = '/pipeline/';
                    }, 1000);
                } catch (error) {
                    // If still failing, give up and show error
                    console.error('Still failed with reduced set:', error);
                    showFeedbackMessage('Storage limit exceeded. Please select fewer samples.', 'danger');
                    sendToPipelineBtn.disabled = false;
                    sendToPipelineBtn.innerHTML = 'Send to Pipeline <i class="bi bi-arrow-right"></i>';
                }
            }

            // Start processing the first batch
            processBatch();
        });
    }

    // Initialize sample checkboxes
    document.querySelectorAll('.sample-select').forEach(checkbox => {
        // Skip the select all checkbox
        if (checkbox.id === 'select-all-samples') return;

        checkbox.addEventListener('change', function () {
            console.log('Checkbox change detected', this.checked);

            const row = this.closest('tr');
            console.log('Found row element:', row);

            if (!row) {
                console.error('No parent row found for checkbox');
                return;
            }

            const data = getSampleDataFromRow(row);
            console.log('Extracted sample data:', data);

            if (!data || !data.id) {
                console.error('Invalid sample data extracted from row');
                return;
            }

            if (this.checked) {
                // Add to selected samples if not already there
                if (!selectedSamples.some(s => s.id === data.id)) {
                    console.log('Adding sample to selection:', data);
                    selectedSamples.push(data);
                } else {
                    console.log('Sample already in selection, skipping');
                }
            } else {
                // Remove from selected samples
                console.log('Removing sample from selection:', data);
                selectedSamples = selectedSamples.filter(s => s.id !== data.id);
            }

            console.log('Updated selectedSamples:', selectedSamples);
            console.log('New count:', selectedSamples.length);
            updateSelectionPanel();
        });
    });

    // Initialize "Select All" checkbox
    const selectAllCheckbox = document.getElementById('select-all-samples');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function () {
            selectedSamples = []; // Reset the selected samples array

            document.querySelectorAll('.sample-select').forEach(checkbox => {
                // Skip the select all checkbox itself
                if (checkbox.id === 'select-all-samples') return;

                checkbox.checked = this.checked;

                if (this.checked) {
                    const row = checkbox.closest('tr');
                    if (row) {
                        const data = getSampleDataFromRow(row);
                        if (data && data.id) {
                            selectedSamples.push(data);
                        }
                    }
                }
            });

            console.log('Select all changed, selectedSamples count:', selectedSamples.length);
            updateSelectionPanel();
        });
    }

    // Helper function to extract sample data from a row
    function getSampleDataFromRow(row) {
        if (!row) {
            console.error('No row provided to getSampleDataFromRow');
            return null;
        }

        // Debug: Log the row
        console.log('Row element:', row);

        let data = {
            fastqName: null,
            studySet: null,
            loadName: null,
            batchNameFromVendor: null,
            libraryPrepMethod: null,
            organismCommon: null,
            ingestStatus: null,
            alignmentStatus: null,
            postqcStatus: null
        };

        // First try to get data from data attributes
        // Try multiple attribute formats
        const attributeMappings = {
            fastqName: ['data-fastq-name'],
            studySet: ['data-study-set'],
            loadName: ['data-load-name'],
            libraryPrepMethod: ['data-library-prep'],
            organismCommon: ['data-organism-common'],
            ingestStatus: ['data-ingest-status'],
            alignmentStatus: ['data-alignment-status'],
            postqcStatus: ['data-postqc-status']
        };

        // Try each possible attribute for each data field
        for (const [field, attributes] of Object.entries(attributeMappings)) {
            for (const attr of attributes) {
                const value = row.getAttribute(attr);
                if (value) {
                    data[field] = value;
                    break; // Stop checking other attributes for this field if found
                }
            }
        }

        // Special case: If we have data-fastq but not id or name, use it for both
        if (!data.id && !data.name && row.getAttribute('data-fastq')) {
            const fastqValue = row.getAttribute('data-fastq');
            data.id = fastqValue;
            data.name = fastqValue;
        }

        // If data attributes are not available or incomplete, extract from table cells
        if (!data.id || !data.fastqName || !data.studySet) {
            console.log('Data attributes not found or incomplete, extracting from cells');

            // Get all cells in the row
            const cells = row.querySelectorAll('td');
            if (cells.length < 2) {
                console.error('Not enough cells in row');
                return null;
            }

            // Find the table this row belongs to
            const table = row.closest('table');
            if (!table) {
                console.error('Could not find parent table');
                return null;
            }

            // Get header cells to dynamically determine column positions
            const headerRow = table.querySelector('thead tr');
            if (!headerRow) {
                console.error('Could not find table header row');
                return null;
            }

            const headerCells = headerRow.querySelectorAll('th');
            console.log('Found header cells:', headerCells.length);

            // Debug header texts
            const headerTexts = Array.from(headerCells).map(cell => cell.textContent.trim());
            console.log('Header texts:', headerTexts);

            const columnMap = {};

            // Map column indices to their names
            headerCells.forEach((cell, index) => {
                let headerText = cell.textContent.trim().toLowerCase();
                console.log(`Header ${index}: "${headerText}"`);

                // Map header texts to our field names
                if (headerText.includes('fastq name')) {
                    columnMap.fastqName = index;
                    console.log(`  ✓ Mapped fastqName to column ${index}`);
                }
                else if (headerText.includes('study set')) {
                    columnMap.studySet = index;
                    console.log(`  ✓ Mapped studySet to column ${index}`);
                }
                else if (headerText.includes('load name')) {
                    columnMap.loadName = index;
                    console.log(`  ✓ Mapped loadName to column ${index}`);
                }
                else if (headerText.includes('library prep method') && !headerText.includes('id')) {
                    columnMap.libraryPrepMethod = index;
                    console.log(`  ✓ Mapped libraryPrepMethod to column ${index}`);
                }
                else if (headerText.match(/\bingestion status\b|\bingest status\b|organism\b/) && !headerText.includes('common')) {
                    columnMap.ingestStatus = index;
                    console.log(`  ✓ Mapped ingestStatus to column ${index}`);
                }
                else if (headerText.includes('organism common name')) {
                    columnMap.organismCommon = index;
                    console.log(`  ✓ Mapped organismCommon to column ${index}`);
                }
                else if (headerText.match(/\balignment status\b/)) {
                    columnMap.alignmentStatus = index;
                    console.log(`  ✓ Mapped alignmentStatus to column ${index}`);
                }
                else if (headerText.match(/\bpostqc status\b/)) {
                    columnMap.postqcStatus = index;
                    console.log(`  ✓ Mapped postqcStatus to column ${index}`);
                }
                else if (headerText.includes('batch name from vendor')) {
                    columnMap.batchNameFromVendor = index;
                    console.log(`  ✓ Mapped batchNameFromVendor to column ${index}`);
                }
            });

            console.log('Dynamic column mapping from headers:', columnMap);

            // Generate a unique ID if none exists - use fastq name column if available
            if (!data.id) {
                const fastqNameIndex = columnMap.fastqName;
                data.id = row.getAttribute('data-fastq') ||
                    (fastqNameIndex !== undefined && cells[fastqNameIndex] ? cells[fastqNameIndex].textContent.trim() : null) ||
                    `row-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
            }

            // Extract data from cells based on the dynamic mapping
            for (const [field, index] of Object.entries(columnMap)) {
                if (!data[field] && cells[index]) {
                    // Get text content, removing any HTML tags
                    const cellText = cells[index].textContent.trim();
                    data[field] = cellText;
                }
            }

            // Make sure we have an ID - if FASTQ name is available, use it as ID
            if (!data.id && data.fastqName) {
                data.id = data.fastqName;
            }
        }

        // Ensure all properties are strings even if null
        for (const key in data) {
            data[key] = data[key] || '';
        }

        console.log('Extracted and cleaned data:', data);
        return data;
    }

    // Helper function to update the selection panel UI
    function updateSelectionPanel() {
        console.log('updateSelectionPanel called with', selectedSamples.length, 'samples');
        console.log('Selected samples data:', selectedSamples);

        // Filter out any invalid entries (missing id)
        selectedSamples = selectedSamples.filter(sample => sample && sample.id);

        if (selectedSamples.length > 0) {
            selectionPanel.style.display = 'flex';
            if (selectionCount) {
                console.log('Setting selection count to', selectedSamples.length);
                selectionCount.textContent = selectedSamples.length;
            } else {
                console.log('Selection count element not found');
            }
        } else {
            console.log('No samples selected, hiding panel');
            selectionPanel.style.display = 'none';
        }
    }
} 