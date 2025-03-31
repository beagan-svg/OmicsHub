/**
 * Column Settings - Completely rebuilt implementation
 * Maintains visual consistency while improving functionality
 */

// Main configuration - will be filled at initialization
const columnConfig = {
    // Column mappings - populated from data attributes
    mappings: {},
    
    // Default visibility settings - populated from data attributes
    defaults: {},
    
    // Track if all columns are currently visible
    allVisible: false,
    
    // Flag to prevent feedback during initialization
    initializing: true,
    
    // Store previous column state before "Show All" was toggled
    previousState: {},
    
    // Flag to track if we're in "Show All" mode
    inShowAllMode: false,
    
    // Cache for DOM elements
    elements: {
        table: null,
        toggleAll: null,
        toggleAllLabel: null,
        resetButton: null,
        columnToggles: {},
        dropdown: null
    }
};

/**
 * Initialize the column settings functionality
 * This is the main entry point for the module
 */
function initializeColumnSettings() {
    // Get the main table
    columnConfig.elements.table = document.querySelector('table.table');
    if (!columnConfig.elements.table) {
        console.error('Table not found in the DOM');
        return;
    }
    
    // Get the toggle elements
    fetchToggleElements();
    
    // Get column configuration from data attributes
    extractColumnConfiguration();
    
    // Initialize column visibility from localStorage
    initializeVisibility();
    
    // Prevent dropdown from closing when toggles are clicked
    preventDropdownClosing();
    
    // Initialize is complete - enable feedback
    setTimeout(() => {
        columnConfig.initializing = false;
    }, 500);
}

/**
 * Fetch and cache all toggle DOM elements
 */
function fetchToggleElements() {
    // Get elements that don't depend on column mappings
    columnConfig.elements.toggleAll = document.getElementById('toggleAllColumns');
    columnConfig.elements.toggleAllLabel = document.getElementById('toggleAllColumnsLabel');
    columnConfig.elements.resetButton = document.getElementById('resetColumnDefaults');
    columnConfig.elements.dropdown = document.querySelector('.column-settings-dropdown .dropdown-menu');
    
    // Check if we found the main controls
    if (!columnConfig.elements.toggleAll) {
        console.error('Toggle All checkbox not found');
    }
    
    if (!columnConfig.elements.resetButton) {
        console.error('Reset button not found');
    }
    
    // Set up event listeners for main controls
    setupMainControlListeners();
}

/**
 * Extract column configuration from data attributes
 */
function extractColumnConfiguration() {
    // Define the list of default visible columns
    const defaultVisibleColumns = [
        'column_fastq_name',
        'column_study_set',
        'column_load_name',
        'column_library_prep_method',
        'column_organism',
        'column_organism_common_name',
        'column_ingest_status',
        'column_alignment_status',
        'column_postqc_status'
    ];
    
    // Get all toggle elements within the dropdown
    const toggles = document.querySelectorAll('.column-toggle-checkbox');
    
    toggles.forEach(toggle => {
        // Extract column class from toggle ID
        const toggleId = toggle.id;
        if (!toggleId.startsWith('toggle')) return;
        
        // Convert camelCase to snake_case (e.g. toggleFastqName -> column_fastq_name)
        const columnClassBase = camelToSnakeCase(toggleId.replace('toggle', ''));
        const columnClass = `column_${columnClassBase.toLowerCase()}`;
        
        // Skip if this doesn't look like a valid column toggle
        if (!columnClass) return;
        
        // Add to mappings
        columnConfig.mappings[columnClass] = {
            toggle: toggle,
            title: toggle.closest('.form-check')?.querySelector('.form-check-label')?.textContent.trim() || columnClass
        };
        
        // Set default to true only for columns in the defaultVisibleColumns list
        columnConfig.defaults[columnClass] = defaultVisibleColumns.includes(columnClass);
        
        // Update the data attribute for consistency
        toggle.dataset.defaultVisible = defaultVisibleColumns.includes(columnClass) ? "true" : "false";
        
        // Add event listener
        toggle.addEventListener('change', event => handleColumnToggleChange(event, columnClass));
    });
}

/**
 * Set up event listeners for the main controls (toggle all, reset)
 */
function setupMainControlListeners() {
    // Toggle All checkbox
    if (columnConfig.elements.toggleAll) {
        columnConfig.elements.toggleAll.addEventListener('change', handleToggleAllChange);
    }
    
    // Reset button
    if (columnConfig.elements.resetButton) {
        columnConfig.elements.resetButton.addEventListener('click', handleResetClick);
    }
}

/**
 * Initialize column visibility based on localStorage or defaults
 */
function initializeVisibility() {
    let visibleCount = 0;
    let totalColumns = 0;
    
    // First, check if this is the first visit (no column settings in localStorage)
    let isFirstVisit = true;
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('show')) {
            isFirstVisit = false;
            break;
        }
    }
    
    // If first visit, populate localStorage with default settings
    if (isFirstVisit) {
        Object.keys(columnConfig.mappings).forEach(columnClass => {
            const defaultState = columnConfig.defaults[columnClass];
            const storageKey = `show${snakeToCamelCase(columnClass)}`;
            localStorage.setItem(storageKey, defaultState);
        });
    }
    
    // Process each column
    Object.keys(columnConfig.mappings).forEach(columnClass => {
        totalColumns++;
        
        // Get stored visibility preference
        const storageKey = `show${snakeToCamelCase(columnClass)}`;
        const storedValue = localStorage.getItem(storageKey);
        
        // Determine if visible - use default if no stored value
        const isVisible = storedValue === null 
            ? columnConfig.defaults[columnClass] 
            : storedValue !== 'false';
        
        if (isVisible) visibleCount++;
        
        // Update toggle state
        const toggle = columnConfig.mappings[columnClass].toggle;
        if (toggle) {
            toggle.checked = isVisible;
        }
        
        // Apply visibility to column
        applyColumnVisibility(columnClass, isVisible, false);
        
        // Also save to previousState for use when toggling off "Show All"
        columnConfig.previousState[columnClass] = isVisible;
    });
    
    // Update all columns visibility state
    columnConfig.allVisible = (visibleCount === totalColumns);
    
    // If all columns are visible, mark as being in show all mode
    columnConfig.inShowAllMode = columnConfig.allVisible;
    
    // Update Toggle All state
    updateToggleAllState();
}

/**
 * Handle toggle state change for individual column
 */
function handleColumnToggleChange(event, columnClass) {
    const isVisible = event.target.checked;
    const storageKey = `show${snakeToCamelCase(columnClass)}`;
    
    // Apply column visibility
    applyColumnVisibility(columnClass, isVisible, true);
    
    // Save to localStorage
    localStorage.setItem(storageKey, isVisible);
    
    // Update previousState if we're not in Show All mode
    if (!columnConfig.inShowAllMode) {
        columnConfig.previousState[columnClass] = isVisible;
    }
    
    // Show feedback message
    if (!columnConfig.initializing && event.isTrusted) {
        const title = columnConfig.mappings[columnClass]?.title || columnClass;
        showFeedbackMessage(`${title} ${isVisible ? 'shown' : 'hidden'}`);
    }
    
    // Update all columns visibility state
    updateAllColumnsState();
}

/**
 * Handle Toggle All checkbox change
 */
function handleToggleAllChange(event) {
    const newState = event.target.checked;
    
    if (newState) {
        // Switching to "Show All" mode - save current state first
        saveCurrentState();
        columnConfig.inShowAllMode = true;
        
        // Show all columns
        Object.keys(columnConfig.mappings).forEach(columnClass => {
            // Update toggle state
            const toggle = columnConfig.mappings[columnClass].toggle;
            if (toggle) {
                toggle.checked = true;
            }
            
            // Apply visibility
            applyColumnVisibility(columnClass, true, true);
            
            // Save to localStorage
            const storageKey = `show${snakeToCamelCase(columnClass)}`;
            localStorage.setItem(storageKey, true);
        });
        
        // Show feedback
        if (!columnConfig.initializing && event.isTrusted) {
            showFeedbackMessage('Showing all columns');
        }
    } else {
        // Switching back to previous state
        columnConfig.inShowAllMode = false;
        
        // Restore previous state
        restorePreviousState();
        
        // Show feedback
        if (!columnConfig.initializing && event.isTrusted) {
            showFeedbackMessage('Restored previous column visibility');
        }
    }
    
    // Update tracking variable and UI
    updateAllColumnsState();
}

/**
 * Save current column visibility state before showing all
 */
function saveCurrentState() {
    columnConfig.previousState = {};
    
    Object.keys(columnConfig.mappings).forEach(columnClass => {
        const toggle = columnConfig.mappings[columnClass].toggle;
        if (toggle) {
            columnConfig.previousState[columnClass] = toggle.checked;
        }
    });
}

/**
 * Restore previous column visibility state
 */
function restorePreviousState() {
    // Check if we have a previous state to restore
    if (Object.keys(columnConfig.previousState).length === 0) {
        // If no previous state, just use defaults
        handleResetClick({ isTrusted: false });
        return;
    }
    
    Object.keys(columnConfig.mappings).forEach(columnClass => {
        // Get previous state (or default if not found)
        const previousState = columnConfig.previousState[columnClass] !== undefined 
            ? columnConfig.previousState[columnClass] 
            : columnConfig.defaults[columnClass];
        
        // Update toggle state
        const toggle = columnConfig.mappings[columnClass].toggle;
        if (toggle) {
            toggle.checked = previousState;
        }
        
        // Apply visibility
        applyColumnVisibility(columnClass, previousState, true);
        
        // Save to localStorage
        const storageKey = `show${snakeToCamelCase(columnClass)}`;
        localStorage.setItem(storageKey, previousState);
    });
}

/**
 * Handle Reset button click
 */
function handleResetClick(event) {
    // Clear all localStorage column visibility settings
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('show')) {
            localStorage.removeItem(key);
            // Adjust for removed item
            i--;
        }
    }
    
    // Track visibility status
    let visibleCount = 0;
    let totalColumns = 0;
    
    // Reset all columns to defaults
    Object.keys(columnConfig.mappings).forEach(columnClass => {
        totalColumns++;
        const defaultState = columnConfig.defaults[columnClass];
        
        if (defaultState) visibleCount++;
        
        // Update toggle state
        const toggle = columnConfig.mappings[columnClass].toggle;
        if (toggle) {
            toggle.checked = defaultState;
        }
        
        // Apply visibility
        applyColumnVisibility(columnClass, defaultState, true);
    });
    
    // Update all columns visibility state
    columnConfig.allVisible = (visibleCount === totalColumns);
    
    // Update Toggle All state
    updateToggleAllState();
    
    // Show feedback
    showFeedbackMessage('Reset to default columns');
}

/**
 * Apply visibility change to column
 */
function applyColumnVisibility(columnClass, isVisible, animate = false) {
    // Find all cells with this class
    const cells = document.querySelectorAll(`.${columnClass}`);
    const headers = document.querySelectorAll(`th.${columnClass}`);
    
    // Apply visibility to cells
    cells.forEach(cell => {
        if (animate) {
            cell.style.transition = 'width 0.3s ease, opacity 0.3s ease';
        }
        
        if (isVisible) {
            cell.style.display = '';
            setTimeout(() => {
                cell.style.opacity = '1';
                cell.style.width = '';
            }, 10);
        } else {
            cell.style.opacity = '0';
            cell.style.width = '0';
            setTimeout(() => {
                cell.style.display = 'none';
            }, animate ? 300 : 0);
        }
    });
    
    // Apply visibility to headers
    headers.forEach(header => {
        if (animate) {
            header.style.transition = 'width 0.3s ease, opacity 0.3s ease';
        }
        
        if (isVisible) {
            header.style.display = '';
            setTimeout(() => {
                header.style.opacity = '1';
                header.style.width = '';
            }, 10);
        } else {
            header.style.opacity = '0';
            header.style.width = '0';
            setTimeout(() => {
                header.style.display = 'none';
            }, animate ? 300 : 0);
        }
    });
}

/**
 * Update all columns visibility state
 */
function updateAllColumnsState() {
    let visibleCount = 0;
    let totalColumns = 0;
    
    // Count visible columns
    Object.keys(columnConfig.mappings).forEach(columnClass => {
        totalColumns++;
        const toggle = columnConfig.mappings[columnClass].toggle;
        
        if (toggle && toggle.checked) {
            visibleCount++;
        }
    });
    
    // Update state
    columnConfig.allVisible = (visibleCount === totalColumns && totalColumns > 0);
    
    // Update Toggle All state
    updateToggleAllState();
}

/**
 * Update Toggle All checkbox and label based on current state
 */
function updateToggleAllState() {
    const toggleAll = columnConfig.elements.toggleAll;
    const toggleLabel = columnConfig.elements.toggleAllLabel;
    
    if (toggleAll) {
        toggleAll.checked = columnConfig.allVisible;
    }
    
    if (toggleLabel) {
        toggleLabel.textContent = columnConfig.allVisible ? 'Hide All Columns' : 'Show All Columns';
    }
}

/**
 * Prevent dropdown from closing when clicking toggles
 */
function preventDropdownClosing() {
    // Prevent dropdown from closing when clicking inside
    const dropdown = columnConfig.elements.dropdown;
    
    if (dropdown) {
        // Ensure dropdown doesn't close when clicked inside
        dropdown.addEventListener('click', function(event) {
            // Stop propagation to prevent dropdown from closing
            event.stopPropagation();
        });
        
        // Also prevent event from bubbling up from toggle switches
        const toggles = dropdown.querySelectorAll('.toggle-switch, .form-check-label, .form-check');
        toggles.forEach(toggle => {
            toggle.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        });
        
        // Prevent propagation from toggle-all and reset button
        const toggleAll = document.querySelector('.toggle-all-columns');
        if (toggleAll) {
            toggleAll.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        }
        
        const resetButton = document.getElementById('resetColumnDefaults');
        if (resetButton) {
            resetButton.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        }
    }
}

/**
 * Show feedback message to user
 */
function showFeedbackMessage(message) {
    let feedbackElement = document.querySelector('.toggle-feedback');
    
    // Create feedback element if it doesn't exist
    if (!feedbackElement) {
        feedbackElement = document.createElement('div');
        feedbackElement.className = 'toggle-feedback';
        document.body.appendChild(feedbackElement);
    }
    
    // Set message
    feedbackElement.textContent = message;
    
    // Show feedback
    feedbackElement.classList.add('show');
    
    // Hide after delay
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
        .toLowerCase()
        .replace(/_([a-z])/g, (_, char) => char.toUpperCase());
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeColumnSettings();
});