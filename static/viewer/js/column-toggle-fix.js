/**
 * Fix for the Toggle All columns functionality
 */
console.log('========== COLUMN TOGGLE FIX LOADED ==========');

document.addEventListener('DOMContentLoaded', function() {
    console.log('Column toggle fix - DOM loaded');
    
    // Wait a moment for the original script to initialize
    setTimeout(() => {
        // Prevent dropdown from closing when clicked inside
        const dropdown = document.querySelector('.column-settings-dropdown-menu');
        if (dropdown) {
            dropdown.addEventListener('click', function(event) {
                // Stop propagation for all clicks inside the dropdown menu
                event.stopPropagation();
                console.log('Keeping dropdown open on internal click');
            });
            console.log('Added event listener to keep dropdown open');
        } else {
            console.warn('Column settings dropdown menu not found');
        }
        
        // Add functionality to prevent dropdown from closing when toggles are clicked
        const columnToggles = document.querySelectorAll('.column-toggle-checkbox');
        console.log(`Found ${columnToggles.length} column toggle checkboxes`);
        
        columnToggles.forEach(toggle => {
            toggle.addEventListener('click', function(event) {
                // Prevent event from bubbling up to dropdown which would close it
                event.stopPropagation();
                console.log('Prevented dropdown from closing on toggle click');
            });
        });
        
        // Also prevent dropdown from closing when toggle all or reset buttons are clicked
        const toggleAllCheckbox = document.getElementById('toggleAllColumns');
        if (toggleAllCheckbox) {
            toggleAllCheckbox.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        }
        
        const resetButton = document.getElementById('resetColumnDefaults');
        if (resetButton) {
            resetButton.addEventListener('click', function(event) {
                event.stopPropagation();
            });
        }
        
        // Override the setupToggleAllAndReset function with our fixed version
        window.originalSetupToggleAllAndReset = window.setupToggleAllAndReset;
        
        window.setupToggleAllAndReset = function() {
            console.log('FIXED: Setting up Toggle All and Reset functionality');
            // Toggle All checkbox
            const toggleAllCheckbox = document.getElementById('toggleAllColumns');
            
            if (toggleAllCheckbox) {
                // Force initial state to match current visibility
                toggleAllCheckbox.checked = window.allColumnsVisible;
                console.log(`FIXED: Initial toggle state set to: ${window.allColumnsVisible}`);
                
                // Remove any existing listeners by cloning and replacing
                const newToggle = toggleAllCheckbox.cloneNode(true);
                toggleAllCheckbox.parentNode.replaceChild(newToggle, toggleAllCheckbox);
                
                // Add our fixed event listener
                newToggle.addEventListener('change', function(event) {
                    // Get current checkbox state (true = checked = "Show All")
                    const newState = this.checked;
                    console.log(`FIXED: Toggle All changed to: ${newState ? "SHOW all columns" : "HIDE all columns"}`);
                    
                    // Important: Update the tracking variable
                    window.allColumnsVisible = newState;
                    
                    // Update all toggle checkboxes to match the new state
                    Object.keys(window.columnMappings).forEach(columnClass => {
                        // Get the checkbox for this column
                        const toggleId = `toggle${window.toCamelCase(columnClass)}`;
                        const toggleElement = document.getElementById(toggleId);
                        
                        if (toggleElement) {
                            // Update each checkbox to match the new state
                            toggleElement.checked = newState;
                            
                            // Apply visibility to the column
                            window.applyColumnVisibility(columnClass, newState, true);
                            
                            // Save the new state to localStorage
                            const storageKey = `show${window.toCamelCase(columnClass)}`;
                            localStorage.setItem(storageKey, newState);
                            
                            console.log(`FIXED: Updated ${columnClass} to ${newState}`);
                        }
                    });
                    
                    // Show feedback message
                    if (!window.isInitializing && event.isTrusted) {
                        window.showToggleMessage(newState ? 'Showing all columns' : 'Hiding all columns');
                    }
                    
                    // Update the toggle label text
                    window.updateToggleAllButtonText();
                });
                
                // Update text initially
                window.updateToggleAllButtonText();
            } else {
                console.error('FIXED: Toggle All checkbox not found in the DOM');
            }
            
            // Set up Reset button using original code
            const resetButton = document.getElementById('resetColumnDefaults');
            if (resetButton) {
                // Remove any existing listeners by cloning and replacing
                const newResetButton = resetButton.cloneNode(true);
                resetButton.parentNode.replaceChild(newResetButton, resetButton);
                
                newResetButton.addEventListener('click', function() {
                    console.log('FIXED: Reset button clicked');
                    
                    // Clear all localStorage column visibility settings
                    Object.keys(window.columnMappings).forEach(columnClass => {
                        const storageKey = `show${window.toCamelCase(columnClass)}`;
                        localStorage.removeItem(storageKey);
                    });
                    
                    // Get defaults
                    let visibleCount = 0;
                    let totalCount = 0;
                    
                    // Reset all columns to their default visibility
                    Object.keys(window.columnMappings).forEach(columnClass => {
                        totalCount++;
                        const defaultState = window.defaultColumnVisibility[columnClass];
                        if (defaultState) visibleCount++;
                        
                        console.log(`Resetting ${columnClass} to default: ${defaultState}`);
                        
                        // Update checkbox state
                        const toggleId = `toggle${window.toCamelCase(columnClass)}`;
                        const toggleElement = document.getElementById(toggleId);
                        
                        if (toggleElement) {
                            toggleElement.checked = defaultState;
                        }
                        
                        // Apply visibility to column
                        window.applyColumnVisibility(columnClass, defaultState, true);
                    });
                    
                    console.log(`After reset: ${visibleCount}/${totalCount} columns visible`);
                    
                    // Update the all columns visible state
                    window.allColumnsVisible = (visibleCount === totalCount);
                    
                    // Update the toggle all checkbox
                    const toggleAllCheckbox = document.getElementById('toggleAllColumns');
                    if (toggleAllCheckbox) {
                        toggleAllCheckbox.checked = window.allColumnsVisible;
                    }
                    
                    // Update the toggle all label
                    window.updateToggleAllButtonText();
                    
                    // Show feedback message
                    window.showToggleMessage('Reset to default columns');
                });
                
                console.log('FIXED: Reset button event listener added');
            }
        };
        
        // Override the updateToggleAllButtonText function
        window.originalUpdateToggleAllButtonText = window.updateToggleAllButtonText;
        
        window.updateToggleAllButtonText = function() {
            const toggleAllCheckbox = document.getElementById('toggleAllColumns');
            const toggleAllLabel = document.getElementById('toggleAllColumnsLabel');
            
            console.log('FIXED: Updating toggle all button text');
            
            if (toggleAllCheckbox && toggleAllLabel) {
                // Make sure the checkbox state matches allColumnsVisible
                toggleAllCheckbox.checked = window.allColumnsVisible;
                
                // Update label text based on toggle state
                // When checked (true) = showing all columns → label should say "Hide All Columns"
                // When unchecked (false) = hiding columns → label should say "Show All Columns" 
                if (window.allColumnsVisible) {
                    console.log('FIXED: Setting toggle to "Hide All Columns" state');
                    toggleAllLabel.textContent = 'Hide All Columns';
                } else {
                    console.log('FIXED: Setting toggle to "Show All Columns" state');
                    toggleAllLabel.textContent = 'Show All Columns';
                }
            } else {
                console.warn('FIXED: Toggle All checkbox or label not found in the DOM');
            }
        };
        
        // Run the fixed setup function
        window.setupToggleAllAndReset();
        
        console.log('Column toggle fix applied successfully');
    }, 500);
});

console.log('========== COLUMN TOGGLE FIX READY =========='); 