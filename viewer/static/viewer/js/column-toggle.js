/**
 * Map column class names to their display titles and categories
 */
const columnMappings = {
    'batch_name': {
        title: 'Batch Name',
        category: 'sample'
    },
    'batch_name_from_vendor': {
        title: 'Batch Name From Vendor',
        category: 'sample'
    },
    'cell_capture': {
        title: 'Cell Capture',
        category: 'sample'
    },
    'sample_id': {
        title: 'Sample ID',
        category: 'sample'
    },
    'amplification_name': {
        title: 'Amplification',
        category: 'amplification'
    },
    'amplification_id': {
        title: 'Amplification ID',
        category: 'amplification'
    },
    'cell_prep_type': {
        title: 'Cell Prep Type',
        category: 'preparation'
    },
    'sequencing_vendor': {
        title: 'Sequencing Vendor',
        category: 'preparation'
    },
    'alignment_method': {
        title: 'Alignment Method',
        category: 'preparation'
    },
    'library_prep_method_id': {
        title: 'Library Prep Method ID',
        category: 'library'
    },
    'library_prep_name': {
        title: 'Library Prep Name',
        category: 'library'
    },
    'organism_common_name': {
        title: 'Organism Common Name',
        category: 'organism'
    }
};

// Default visibility state for columns
const defaultColumnVisibility = {
    'batch_name': true,
    'batch_name_from_vendor': true,
    'cell_capture': true,
    'sample_id': true,
    'amplification_name': true,
    'amplification_id': true,
    'cell_prep_type': true,
    'sequencing_vendor': true,
    'alignment_method': true,
    'library_prep_method_id': true,
    'library_prep_name': true,
    'organism_common_name': true
};

// Track if all columns are currently visible
let allColumnsVisible = true;

// Track if columns are being initialized to avoid showing messages during load
let isInitializing = true;

// Track the last message to prevent duplicates
let lastMessage = '';
let lastMessageTime = 0;

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM content loaded - initializing column toggle functionality');
    
    // Set initializing flag to prevent unnecessary notifications during page load
    isInitializing = true;
    
    // Initialize column visibility from localStorage
    initializeColumnVisibility();
    
    // Set up column visibility toggle event listeners
    setupColumnToggleListeners();
    
    // Add search functionality
    setupColumnSearch();
    
    // Add toggle all and reset buttons functionality
    setupToggleAllAndReset();
    
    // Prevent dropdown from closing when clicked inside
    const dropdown = document.getElementById('column-settings-dropdown');
    if (dropdown) {
        dropdown.addEventListener('click', function(e) {
            if (!e.target.matches('button') || e.target.id === 'column-settings-toggle') {
                e.stopPropagation();
            }
        });
    }
    
    // Wait a bit for the table to be fully rendered
    setTimeout(() => {
        debugTableColumns();
        // No longer initializing, now user interactions should show messages
        isInitializing = false;
    }, 1000);
    
    // Check if form submission is happening (filtering)
    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        filterForm.addEventListener('submit', function() {
            // Set a flag to prevent toggle messages during page transitions for filtering
            sessionStorage.setItem('isFiltering', 'true');
        });
    }
    
    // Check if we're coming from a filter submission
    if (sessionStorage.getItem('isFiltering') === 'true') {
        // We're just loaded after filtering, don't show toggle messages
        isInitializing = true;
        // Clear the flag
        sessionStorage.removeItem('isFiltering');
        // After a delay, allow toggle messages again
        setTimeout(() => {
            isInitializing = false;
        }, 1000);
    }
});

/**
 * Initialize column visibility based on saved preferences
 */
function initializeColumnVisibility() {
    console.log('Initializing column visibility');

    // Initialize all toggle controls from localStorage
    Object.keys(columnMappings).forEach(columnClass => {
        const storageKey = `show${toCamelCase(columnClass)}`;
        const isVisible = localStorage.getItem(storageKey) !== 'false';
        
        // Update checkbox state
        const toggleId = `toggle${toCamelCase(columnClass)}`;
        const toggleElement = document.getElementById(toggleId);
        
        if (toggleElement) {
            toggleElement.checked = isVisible;
            console.log(`Setting ${toggleId} to ${isVisible}`);
        } else {
            console.warn(`Toggle element ${toggleId} not found`);
        }
        
        // Apply visibility to column
        applyColumnVisibility(columnClass, isVisible, false); // Don't animate on initial load
    });
    
    // Update the "all columns visible" state
    updateAllColumnsState();
}

/**
 * Set up event listeners for column toggle controls
 */
function setupColumnToggleListeners() {
    // Find all column toggle switches
    const toggleSwitches = document.querySelectorAll('input[type="checkbox"][id^="toggle"]');
    
    console.log(`Found ${toggleSwitches.length} toggle switches`);
    
    // Iterate through all toggle switches
    toggleSwitches.forEach(toggle => {
        const toggleId = toggle.id;
        // Extract column name from toggle ID (e.g., "toggleBatchName" -> "batch_name")
        let columnClass = toggleId.replace('toggle', '');
        
        // Convert from camelCase back to snake_case if needed
        // First character to lowercase
        columnClass = columnClass.charAt(0).toLowerCase() + columnClass.slice(1);
        
        // Convert camelCase to snake_case
        columnClass = columnClass.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
        
        console.log(`Setting up listener for ${toggleId} -> ${columnClass}`);
        
        if (toggle) {
            toggle.addEventListener('change', function(event) {
                // Get current state
                const isVisible = this.checked;
                const storageKey = `show${toCamelCase(columnClass)}`;
                
                console.log(`Toggle changed for ${columnClass}: ${isVisible}`);
                
                // Apply visibility to column with animation
                applyColumnVisibility(columnClass, isVisible, true);
                
                // Save preference to localStorage
                localStorage.setItem(storageKey, isVisible);
                
                // Show feedback message only if not initializing and not triggered programmatically
                if (!isInitializing && event.isTrusted) {
                    const title = columnMappings[columnClass]?.title || 
                        columnClass.split('_').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
                    showToggleMessage(`${title} ${isVisible ? 'shown' : 'hidden'}`);
                }
                
                // Update the "all columns visible" state
                updateAllColumnsState();
            });
        } else {
            console.warn(`Toggle element not found: ${toggleId}`);
        }
    });
}

/**
 * Set up search functionality for column toggles
 */
function setupColumnSearch() {
    const searchInput = document.getElementById('column-toggle-search-input');
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            console.log(`Filtering toggle elements for: "${searchTerm}"`);
            
            // Find the categories container
            const categoriesContainer = document.querySelector('.column-categories-container');
            if (!categoriesContainer) {
                console.error('Categories container not found');
                return;
            }
            
            // Filter toggle elements based on search term
            Object.keys(columnMappings).forEach(columnClass => {
                const toggleId = `toggle${toCamelCase(columnClass)}`;
                const toggleElement = document.getElementById(toggleId);
                
                if (toggleElement) {
                    const formCheck = toggleElement.closest('.form-check');
                    
                    if (formCheck) {
                        const columnTitle = columnMappings[columnClass].title.toLowerCase();
                        const isMatch = columnTitle.includes(searchTerm);
                        
                        // Show/hide the form-check element
                        formCheck.style.display = isMatch || searchTerm === '' ? '' : 'none';
                        console.log(`Toggle ${toggleId} ${isMatch ? 'matches' : 'does not match'} search term`);
                    }
                }
            });
            
            // Show/hide category headers based on whether they have visible items
            categoriesContainer.querySelectorAll('.column-category').forEach(category => {
                const hasVisibleItems = Array.from(category.querySelectorAll('.form-check')).some(
                    check => check.style.display !== 'none'
                );
                
                category.style.display = hasVisibleItems ? '' : 'none';
                console.log(`Category ${category.querySelector('h6')?.textContent.trim()} ${hasVisibleItems ? 'has' : 'has no'} visible items`);
            });
        });
    }
}

/**
 * Set up Toggle All and Reset to Default buttons
 */
function setupToggleAllAndReset() {
    // Toggle All button
    const toggleAllButton = document.getElementById('toggleAllColumns');
    
    if (toggleAllButton) {
        toggleAllButton.addEventListener('click', function() {
            // If all columns are visible, hide all; otherwise, show all
            const newState = !allColumnsVisible;
            
            Object.keys(columnMappings).forEach(columnClass => {
                // Update checkbox state
                const toggleId = `toggle${toCamelCase(columnClass)}`;
                const toggleElement = document.getElementById(toggleId);
                
                if (toggleElement) {
                    toggleElement.checked = newState;
                }
                
                // Apply visibility to column
                applyColumnVisibility(columnClass, newState, true);
                
                // Save preference to localStorage
                const storageKey = `show${toCamelCase(columnClass)}`;
                localStorage.setItem(storageKey, newState);
            });
            
            // Show feedback message
            showToggleMessage(`${newState ? 'Showing' : 'Hiding'} all columns`);
            
            // Update button text
            this.textContent = newState ? 'Hide All' : 'Show All';
            
            // Update the "all columns visible" state
            allColumnsVisible = newState;
        });
    }
    
    // Reset to Default button
    const resetButton = document.getElementById('resetColumnDefaults');
    
    if (resetButton) {
        resetButton.addEventListener('click', function() {
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
                
                // Save preference to localStorage
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
 * Update the state tracking if all columns are visible
 */
function updateAllColumnsState() {
    allColumnsVisible = Object.keys(columnMappings).every(columnClass => {
        const storageKey = `show${toCamelCase(columnClass)}`;
        return localStorage.getItem(storageKey) !== 'false';
    });
    
    // Update Toggle All button text
    const toggleAllButton = document.getElementById('toggleAllColumns');
    if (toggleAllButton) {
        toggleAllButton.textContent = allColumnsVisible ? 'Hide All' : 'Show All';
    }
}

/**
 * Convert a snake_case string to camelCase
 * @param {string} str - The snake_case string to convert
 * @return {string} The camelCase string
 */
function toCamelCase(str) {
    return str.split('_').map((word, index) => {
        return index === 0 ? word : word.charAt(0).toUpperCase() + word.slice(1);
    }).join('');
}

/**
 * Apply visibility to a table column
 * @param {string} columnClass - The class name of the column to toggle
 * @param {boolean} isVisible - Whether the column should be visible
 * @param {boolean} animate - Whether to animate the visibility change
 */
function applyColumnVisibility(columnClass, isVisible, animate = false) {
    // Find the table in the DOM
    const table = document.querySelector('.table-container table');
    if (!table) {
        console.error('Table not found - looking for .table-container table');
        // Try alternate selectors
        const altTable = document.querySelector('table.table') || document.querySelector('table');
        if (altTable) {
            console.log('Found table with alternate selector');
            applyColumnVisibilityToTable(altTable, columnClass, isVisible, animate);
        } else {
            console.error('No table found in the document');
        }
        return;
    }
    
    applyColumnVisibilityToTable(table, columnClass, isVisible, animate);
}

/**
 * Apply visibility to a specific table
 * @param {HTMLElement} table - The table element
 * @param {string} columnClass - The class name of the column to toggle
 * @param {boolean} isVisible - Whether the column should be visible
 * @param {boolean} animate - Whether to animate the visibility change
 */
function applyColumnVisibilityToTable(table, columnClass, isVisible, animate = false) {
    console.group(`Toggling column ${columnClass} to ${isVisible ? 'visible' : 'hidden'}`);
    console.log(`Table element:`, table);
    
    // Direct approach: try all possible class combinations
    const possibleColumnHeaderClasses = [
        `column-${columnClass}`,
        `${columnClass}-column`,
        columnClass
    ];
    
    const possibleDataCellClasses = [
        `field-${columnClass}`,
        `${columnClass}-field`,
        columnClass
    ];
    
    let foundCells = false;
    
    // Check for title-based matching (more reliable sometimes)
    const columnTitle = columnMappings[columnClass]?.title || 
        columnClass.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
    
    // 1. Find header by column title
    const headers = table.querySelectorAll('thead th');
    let targetHeaders = [];
    
    headers.forEach((header, index) => {
        const headerText = header.textContent.trim();
        // Look for exact match or very close match
        if (headerText === columnTitle || 
            headerText.includes(columnTitle) || 
            columnTitle.includes(headerText)) {
            targetHeaders.push(header);
            console.log(`Found header by title match: "${headerText}" for "${columnTitle}"`);
            
            // If we haven't added class attribute yet, add it for future toggles
            if (!header.classList.contains(`column-${columnClass}`)) {
                header.classList.add(`column-${columnClass}`);
                console.log(`Added column-${columnClass} class to header`);
            }
        }
    });
    
    // 2. Find headers by class
    if (targetHeaders.length === 0) {
        for (const className of possibleColumnHeaderClasses) {
            const found = table.querySelectorAll(`thead th.${className}`);
            if (found.length > 0) {
                targetHeaders = [...found];
                console.log(`Found ${found.length} headers with class ${className}`);
                break;
            }
        }
    }
    
    // 3. Find all matching data cells
    let targetCells = [];
    
    if (targetHeaders.length > 0) {
        // If we found headers, find all cells in those columns
        targetHeaders.forEach(header => {
            const headerIndex = Array.from(headers).indexOf(header);
            if (headerIndex >= 0) {
                // Get all cells in this column
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length > headerIndex) {
                        targetCells.push(cells[headerIndex]);
                        // Add class for future toggles
                        if (!cells[headerIndex].classList.contains(`field-${columnClass}`)) {
                            cells[headerIndex].classList.add(`field-${columnClass}`);
                        }
                    }
                });
            }
        });
    } else {
        // Otherwise try to find cells by class
        for (const className of possibleDataCellClasses) {
            const found = table.querySelectorAll(`tbody td.${className}`);
            if (found.length > 0) {
                targetCells = [...found];
                console.log(`Found ${found.length} data cells with class ${className}`);
                break;
            }
        }
    }
    
    // Apply visibility to all found elements
    const allTargetElements = [...targetHeaders, ...targetCells];
    
    if (allTargetElements.length > 0) {
        foundCells = true;
        console.log(`Found ${allTargetElements.length} elements to toggle for ${columnClass}`);
        
        if (animate) {
            // Apply animated visibility changes
            allTargetElements.forEach(element => {
                element.classList.add('animate-column-toggle');
                
                if (isVisible) {
                    element.style.opacity = '0';
                    element.style.transform = 'translateY(-10px)';
                    element.style.display = '';
                    
                    // Trigger reflow
                    void element.offsetWidth;
                    
                    element.style.opacity = '1';
                    element.style.transform = 'translateY(0)';
                    
                    // Remove animation class after animation completes
                    setTimeout(() => {
                        element.classList.remove('animate-column-toggle');
                    }, 300);
                } else {
                    element.style.opacity = '0';
                    element.style.transform = 'translateY(-10px)';
                    
                    // Hide after animation
                    setTimeout(() => {
                        element.style.display = 'none';
                        element.classList.remove('animate-column-toggle');
                    }, 300);
                }
            });
        } else {
            // Apply immediate visibility changes
            allTargetElements.forEach(element => {
                element.style.display = isVisible ? '' : 'none';
            });
        }
    }
    
    // 4. Handle special case: cells without proper classes
    if (!foundCells) {
        console.warn(`Could not find cells for column ${columnClass} by class or title, trying nth-child`);
        
        // Last resort: try to find the column by its title text in header and use nth-child
        const headerWithTitle = Array.from(headers).find(header => 
            header.textContent.trim() === columnTitle ||
            header.textContent.trim().includes(columnTitle)
        );
        
        if (headerWithTitle) {
            const headerIndex = Array.from(headers).indexOf(headerWithTitle);
            console.log(`Found header "${headerWithTitle.textContent.trim()}" at index ${headerIndex}`);
            
            // Add nth-child selector to all rows
            if (headerIndex >= 0) {
                // Apply to header
                headerWithTitle.style.display = isVisible ? '' : 'none';
                
                // Apply to all cells in this column position
                const rows = table.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const targetCell = row.querySelector(`td:nth-child(${headerIndex + 1})`);
                    if (targetCell) {
                        if (animate) {
                            targetCell.classList.add('animate-column-toggle');
                            
                            if (isVisible) {
                                targetCell.style.opacity = '0';
                                targetCell.style.transform = 'translateY(-10px)';
                                targetCell.style.display = '';
                                
                                // Trigger reflow
                                void targetCell.offsetWidth;
                                
                                targetCell.style.opacity = '1';
                                targetCell.style.transform = 'translateY(0)';
                                
                                // Remove animation class after animation completes
                                setTimeout(() => {
                                    targetCell.classList.remove('animate-column-toggle');
                                }, 300);
                            } else {
                                targetCell.style.opacity = '0';
                                targetCell.style.transform = 'translateY(-10px)';
                                
                                // Hide after animation
                                setTimeout(() => {
                                    targetCell.style.display = 'none';
                                    targetCell.classList.remove('animate-column-toggle');
                                }, 300);
                            }
                        } else {
                            targetCell.style.display = isVisible ? '' : 'none';
                        }
                    }
                });
                
                foundCells = true;
            }
        }
    }
    
    // Log final status
    if (foundCells) {
        console.log(`✅ Successfully toggled column ${columnClass}`);
    } else {
        console.error(`❌ Failed to toggle column ${columnClass}`);
        showToggleMessage(`Could not toggle column: ${columnTitle}`, true);
    }
    
    console.groupEnd();
    return foundCells;
}

/**
 * Show a temporary message when a column is toggled
 * @param {string} message - The message to display
 * @param {boolean} isError - Whether this is an error message
 */
function showToggleMessage(message, isError = false) {
    console.log(`Toggle message: ${message}`);
    
    // Prevent duplicate messages within a short timeframe
    const now = Date.now();
    if (message === lastMessage && now - lastMessageTime < 1000) {
        console.log('Suppressing duplicate message');
        return;
    }
    
    // Update last message tracking
    lastMessage = message;
    lastMessageTime = now;
    
    // Create message element if it doesn't exist
    let messageElement = document.getElementById('toggle-feedback');
    if (!messageElement) {
        messageElement = document.createElement('div');
        messageElement.id = 'toggle-feedback';
        messageElement.className = 'toggle-feedback';
        document.body.appendChild(messageElement);
        console.log('Created new toggle feedback element');
    }
    
    // Set message text
    messageElement.textContent = message;
    
    // Add error class for error messages
    if (isError) {
        messageElement.classList.add('error');
    } else {
        messageElement.classList.remove('error');
    }
    
    // Show the message
    messageElement.classList.add('show');
    
    // Hide the message after a delay
    setTimeout(function() {
        messageElement.classList.remove('show');
    }, 2000);
}

/**
 * Debug utility to log all column headers
 */
function debugTableColumns() {
    const table = document.querySelector('.table-container table');
    if (!table) {
        console.warn('No table found in the DOM');
        return;
    }
    
    console.log('===== TABLE COLUMN DEBUG =====');
    const headers = table.querySelectorAll('thead th');
    headers.forEach((header, index) => {
        console.log(`Column ${index}: "${header.textContent.trim()}" - Classes: ${header.className}`);
    });
    
    // Check first row data cells
    const firstRow = table.querySelector('tbody tr');
    if (firstRow) {
        const cells = firstRow.querySelectorAll('td');
        console.log('===== FIRST ROW CELLS =====');
        cells.forEach((cell, index) => {
            console.log(`Cell ${index}: Classes: ${cell.className}`);
        });
    }
    
    console.log('===== COLUMN MAPPINGS =====');
    Object.entries(columnMappings).forEach(([key, value]) => {
        console.log(`${key} -> "${value.title}" (${value.category})`);
    });
} 