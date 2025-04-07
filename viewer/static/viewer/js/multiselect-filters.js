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
    let icon = '';
    switch (type) {
        case 'success':
            icon = '<i class="bi bi-check2-circle"></i>';  // Changed to nicer checkmark
            break;
        case 'info':
            icon = '<i class="bi bi-stars"></i>';  // Changed to stars icon
            break;
        case 'warning':
            icon = '<i class="bi bi-exclamation-circle"></i>';
            break;
    }

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
            showFeedbackMessage('Filters cleared', 'success');

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