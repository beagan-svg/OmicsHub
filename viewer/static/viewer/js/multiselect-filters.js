// Modern filters script with enhanced UI/UX for card-based layout
console.log('Loading enhanced filter script with card animations...');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM loaded, initializing filters');
    
    // Toggle advanced filters
    initAdvancedFiltersToggle();
    
    // Initialize Select2 with enhanced settings
    initEnhancedSelect2();
    
    // Initialize filter tag removers
    initFilterTagRemovers();
    
    // Initialize reset filters button
    initResetFiltersButton();
    
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
    toggleButton.addEventListener('click', function() {
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
            containerCssClass: 'select2-fixed-height',
            tags: false
        });
        
        // Fix placeholder appearance
        jQuery('.filter-select').on('select2:open', function() {
            document.querySelector('.select2-search__field').placeholder = 'Search...';
        });
        
        // Handle keyboard events to improve backspace behavior
        jQuery(document).on('keydown', '.select2-selection--multiple .select2-search__field', function(e) {
            // Get the select element
            const $select = jQuery(this).closest('.select2-container').siblings('select.filter-select');
            
            // If backspace key pressed and input is empty
            if (e.keyCode === 8 && this.value.length === 0) {
                // Get current values
                const values = $select.val() || [];
                
                // If there are selected values
                if (values.length > 0) {
                    // Create a new array without the last value
                    const newValues = values.slice(0, -1);
                    
                    // Set the new values without opening dropdown
                    $select.val(newValues).trigger('change.select2');
                    
                    // Prevent default backspace action which might cause cursor behavior issues
                    e.preventDefault();
                }
            }
        });
        
        // Close dropdown when pressing ESC or Tab
        jQuery(document).on('keydown', '.select2-selection--multiple', function(e) {
            if (e.keyCode === 27 || e.keyCode === 9) { // ESC or Tab
                const $select = jQuery(this).closest('.select2-container').siblings('select.filter-select');
                $select.select2('close');
            }
        });
        
        // Fix input field focus when clicking on selection area
        jQuery(document).on('click', '.select2-selection--multiple', function(e) {
            if (jQuery(e.target).hasClass('select2-selection--multiple')) {
                const searchField = jQuery(this).find('.select2-search__field')[0];
                if (searchField) {
                    setTimeout(() => {
                        searchField.focus();
                    }, 0);
                }
            }
        });
        
        // Handle on-change events for dynamic interface updates
        jQuery('.filter-select').on('change', function() {
            // Update highlighting
            updateFilterHighlighting(this);
            
            // Update active filters display
            updateActiveFiltersDisplay();
            
            // Fix height if needed after selection
            fixSelectHeight(this);
        });
        
        // Initialize filter highlighting
        jQuery('.filter-select').each(function() {
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
        card.addEventListener('mouseenter', function() {
            this.style.transition = 'transform 0.3s ease, box-shadow 0.3s ease';
        });
        
        // Add focus effect when clicking on any input inside the card
        const inputs = card.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('focus', function() {
                card.classList.add('filter-card-focus');
            });
            
            input.addEventListener('blur', function() {
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
    
    filterTags.forEach(function(tag) {
        tag.addEventListener('click', function() {
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
    
    // Create title if filters are active
    let hasActiveFilters = false;
    
    // Process text filters
    document.querySelectorAll('input[type="text"][name]').forEach(input => {
        if (input.value) {
            hasActiveFilters = true;
            createFilterTag(container, input.name, null, input.value);
        }
    });
    
    // Process select filters
    document.querySelectorAll('select.filter-select').forEach(select => {
        const values = jQuery(select).val();
        if (values && values.length) {
            hasActiveFilters = true;
            values.forEach(value => {
                // Find the option text for this value
                const option = select.querySelector(`option[value="${value}"]`);
                const displayText = option ? option.textContent : value;
                createFilterTag(container, select.name, value, displayText);
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
        <span class="tag-remove" data-filter="${filter}" data-value="${value || ''}">
            <i class="bi bi-x-circle"></i>
        </span>
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
    
    // Add click handler
    tag.querySelector('.tag-remove').addEventListener('click', function() {
        const filterField = this.dataset.filter;
        const filterValue = this.dataset.value;
        
        if (filterValue) {
            // For multi-select filters, remove just this value
            const select = document.getElementById(filterField);
            if (select && typeof jQuery !== 'undefined') {
                let currentValues = jQuery(select).val() || [];
                currentValues = currentValues.filter(item => item !== filterValue);
                jQuery(select).val(currentValues).trigger('change');
            }
        } else {
            // For text inputs, clear the field
            const input = document.querySelector(`[name="${filterField}"]`);
            if (input) {
                input.value = '';
            }
        }
        
        // Add removal animation
        const tagElement = this.closest('.filter-tag');
        tagElement.style.transition = 'transform 0.2s ease, opacity 0.2s ease';
        tagElement.style.transform = 'translateX(-10px)';
        tagElement.style.opacity = '0';
        
        setTimeout(() => {
            // Submit the form
            document.getElementById('filter-form').submit();
        }, 200);
    });
}

// Format a field name into a friendly label
function formatLabelFromName(name) {
    return name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, l => l.toUpperCase());
}

// Initialize the reset filters button with enhanced feedback
function initResetFiltersButton() {
    const resetButton = document.getElementById('resetFilters');
    
    if (resetButton) {
        resetButton.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Add button press effect
            this.classList.add('btn-press-effect');
            
            // Clear all selects
            if (typeof jQuery !== 'undefined' && typeof jQuery.fn.select2 !== 'undefined') {
                jQuery('.filter-select').val(null).trigger('change');
            } else {
                document.querySelectorAll('.filter-select').forEach(function(select) {
                    select.selectedIndex = -1;
                });
            }
            
            // Reset text inputs
            document.querySelectorAll('input[type="text"]').forEach(function(input) {
                input.value = '';
            });
            
            // Show feedback message
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

// Show a feedback message to the user
function showFeedbackMessage(message, type = 'info') {
    // Create or get the message container
    let messageContainer = document.getElementById('filter-feedback-message');
    
    if (!messageContainer) {
        messageContainer = document.createElement('div');
        messageContainer.id = 'filter-feedback-message';
        messageContainer.className = 'filter-message';
        document.body.appendChild(messageContainer);
    }
    
    // Set message content and style
    messageContainer.textContent = message;
    messageContainer.className = `filter-message ${type}`;
    
    // Show and then hide after delay
    messageContainer.classList.add('show');
    
    setTimeout(() => {
        messageContainer.classList.remove('show');
    }, 3000);
} 