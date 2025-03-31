/**
 * Debug script for column toggle functionality
 */
console.log('======== DEBUG COLUMN TOGGLE SCRIPT LOADED ========');

// Hijack localStorage to add debugging
const originalSetItem = localStorage.setItem;
localStorage.setItem = function(key, value) {
    console.log(`localStorage.setItem('${key}', '${value}')`);
    originalSetItem.call(this, key, value);
};

// Wait for DOM content to be loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('DEBUG: DOM content loaded, setting up debug listeners');
    
    // Add debug listener for Toggle All checkbox
    const toggleAllCheckbox = document.getElementById('toggleAllColumns');
    if (toggleAllCheckbox) {
        console.log('DEBUG: Found toggleAllColumns checkbox');
        
        // Log initial state
        console.log(`DEBUG: Initial checkbox state: ${toggleAllCheckbox.checked}`);
        
        // Add debug listener before the actual event
        toggleAllCheckbox.addEventListener('click', function(event) {
            console.log(`DEBUG: Toggle All CLICKED - current state before change: ${this.checked}, will become: ${!this.checked}`);
        }, true);
        
        toggleAllCheckbox.addEventListener('change', function(event) {
            console.log(`DEBUG: Toggle All CHANGED - new state: ${this.checked}`);
            console.log(`DEBUG: Event trusted: ${event.isTrusted}, Event type: ${event.type}`);
        });
    } else {
        console.error('DEBUG: toggleAllColumns checkbox NOT found in DOM');
    }
    
    // Debug all column toggle checkboxes
    const toggleSwitches = document.querySelectorAll('input[type="checkbox"][id^="toggle"]');
    console.log(`DEBUG: Found ${toggleSwitches.length} toggle switches`);
    
    // Add debug label for toggle all columns
    const toggleAllLabel = document.getElementById('toggleAllColumnsLabel');
    if (toggleAllLabel) {
        console.log(`DEBUG: Toggle All Label text: "${toggleAllLabel.textContent}"`);
    }
    
    // Debug value of allColumnsVisible
    setInterval(() => {
        if (typeof allColumnsVisible !== 'undefined') {
            console.log(`DEBUG: allColumnsVisible = ${allColumnsVisible}`);
        }
    }, 2000);
});

// Function to log all column visibility states
function debugColumnVisibility() {
    console.group('Column Visibility Debug');
    
    // Log all localStorage items related to column visibility
    const visibilityKeys = [];
    for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('show')) {
            visibilityKeys.push(key);
        }
    }
    
    console.log(`Found ${visibilityKeys.length} column visibility settings in localStorage`);
    visibilityKeys.forEach(key => {
        console.log(`${key} = ${localStorage.getItem(key)}`);
    });
    
    console.groupEnd();
}

// Add global function for manual debugging
window.debugColumnToggle = {
    logVisibility: debugColumnVisibility,
    toggleAll: function(state) {
        const toggleAllCheckbox = document.getElementById('toggleAllColumns');
        if (toggleAllCheckbox) {
            console.log(`Manually setting Toggle All to: ${state}`);
            toggleAllCheckbox.checked = state;
            
            // Dispatch a change event
            const event = new Event('change', { bubbles: true });
            toggleAllCheckbox.dispatchEvent(event);
        }
    }
};

console.log('======== DEBUG COLUMN TOGGLE SCRIPT READY ========'); 