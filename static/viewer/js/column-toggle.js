/**
 * Set up Toggle All and Reset to Default buttons
 */
function setupToggleAllAndReset() {
    // Toggle All checkbox
    const toggleAllCheckbox = document.getElementById('toggleAllColumns');
    
    if (toggleAllCheckbox) {
        console.log('Setting up Toggle All checkbox event listeners');
        
        // Force initial state to match allColumnsVisible
        toggleAllCheckbox.checked = allColumnsVisible;
        console.log(`Initial toggle state set to: ${allColumnsVisible}`);
        
        toggleAllCheckbox.addEventListener('change', function(event) {
            // Get current checkbox state (true = checked = "Show All")
            const newState = this.checked;
            console.log(`Toggle All changed to: ${newState ? "SHOW all columns" : "HIDE all columns"}`);
            
            // Important: Update our tracking variable
            allColumnsVisible = newState;
            
            // Update all toggle checkboxes to match the new state
            Object.keys(columnMappings).forEach(columnClass => {
                // Get the checkbox for this column
                const toggleId = `toggle${toCamelCase(columnClass)}`;
                const toggleElement = document.getElementById(toggleId);
                
                if (toggleElement) {
                    // Update each checkbox to match the new state
                    toggleElement.checked = newState;
                    
                    // Apply visibility to the column
                    applyColumnVisibility(columnClass, newState, true);
                    
                    // Save the new state to localStorage
                    const storageKey = `show${toCamelCase(columnClass)}`;
                    localStorage.setItem(storageKey, newState);
                    
                    console.log(`Updated ${columnClass} to ${newState}`);
                }
            });
            
            // Show feedback message
            if (!isInitializing && event.isTrusted) {
                showToggleMessage(newState ? 'Showing all columns' : 'Hiding all columns');
            }
            
            // Update the toggle label text
            updateToggleAllButtonText();
        });
        
        // Update text initially
        updateToggleAllButtonText();
    } else {
        console.error('Toggle All checkbox not found in the DOM');
    }
    
    // Reset to Default button
    const resetButton = document.getElementById('resetColumnDefaults');
    
    if (resetButton) {
        resetButton.addEventListener('click', function() {
            console.log('Reset button clicked');
            // Clear all localStorage column visibility settings
            Object.keys(columnMappings).forEach(columnClass => {
                const storageKey = `show${toCamelCase(columnClass)}`;
                localStorage.removeItem(storageKey);
            });
            
            // Reset all columns to their default visibility
            Object.keys(columnMappings).forEach(columnClass => {
                const defaultState = defaultColumnVisibility[columnClass];
                
                // Update checkbox state
                const toggleId = `toggle${toCamelCase(columnClass)}`;
                const toggleElement = document.getElementById(toggleId);
                
                if (toggleElement) {
                    toggleElement.checked = defaultState;
                }
                
                // Apply visibility to column
                applyColumnVisibility(columnClass, defaultState, true);
                
                // Save preference to localStorage (explicitly set to the default)
                const storageKey = `show${toCamelCase(columnClass)}`;
                localStorage.setItem(storageKey, defaultState);
            });
            
            // Show feedback message
            showToggleMessage('Reset to default columns');
            
            // Update the "all columns visible" state
            updateAllColumnsState();
        });
    }
}

/**
 * Update the Toggle All button text based on current state
 */
function updateToggleAllButtonText() {
    const toggleAllCheckbox = document.getElementById('toggleAllColumns');
    const toggleAllLabel = document.getElementById('toggleAllColumnsLabel');
    
    if (toggleAllCheckbox && toggleAllLabel) {
        // Make sure the checkbox state matches allColumnsVisible
        toggleAllCheckbox.checked = allColumnsVisible;
        
        // Update label text based on toggle state
        // When checked (true) = showing all columns → label should say "Hide All Columns"
        // When unchecked (false) = hiding columns → label should say "Show All Columns"
        if (allColumnsVisible) {
            console.log('Setting toggle label to "Hide All Columns"');
            toggleAllLabel.textContent = 'Hide All Columns';
        } else {
            console.log('Setting toggle label to "Show All Columns"');
            toggleAllLabel.textContent = 'Show All Columns';
        }
    } else {
        console.warn('Toggle All checkbox or label not found in the DOM');
    }
}

/**
 * Update the state tracking if all columns are visible
 */
function updateAllColumnsState() {
    // Count visible columns for debugging
    let visibleCount = 0;
    let totalCount = 0;
    
    console.group('Column Visibility Check');
    
    // Check each column's visibility state
    Object.keys(columnMappings).forEach(columnClass => {
        totalCount++;
        const storageKey = `show${toCamelCase(columnClass)}`;
        const storedValue = localStorage.getItem(storageKey);
        
        // If not in localStorage, use default; otherwise check if it's not 'false'
        const isVisible = storedValue === null ? 
            defaultColumnVisibility[columnClass] : 
            storedValue !== 'false';
            
        if (isVisible) visibleCount++;
        
        console.log(`Column "${columnClass}": localStorage=${storedValue}, isVisible=${isVisible}`);
    });
    
    // All columns are visible if every column is visible
    const allVisible = visibleCount === totalCount;
    console.log(`Column visibility summary: ${visibleCount}/${totalCount} columns visible`);
    
    // Update the global state variable
    if (allColumnsVisible !== allVisible) {
        console.log(`Updating allColumnsVisible from ${allColumnsVisible} to ${allVisible}`);
        allColumnsVisible = allVisible;
    }
    
    console.groupEnd();
    
    // Update the Toggle All checkbox
    const toggleAllCheckbox = document.getElementById('toggleAllColumns');
    if (toggleAllCheckbox) {
        console.log(`Setting Toggle All checkbox to ${allColumnsVisible}`);
        toggleAllCheckbox.checked = allColumnsVisible;
    }
    
    // Update the Toggle All label text
    updateToggleAllButtonText();
}

// Track if all columns are currently visible
let allColumnsVisible = false; 