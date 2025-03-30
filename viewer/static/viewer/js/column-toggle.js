/**
 * Map column class names to their display titles
 */
const columnMappings = {
    'batch_name': 'Batch Name',
    'batch_name_from_vendor': 'Batch Name From Vendor',
    'cell_capture': 'Cell Capture',
    'sample_id': 'Sample ID',
    'amplification_name': 'Amplification',
    'amplification_id': 'Amplification ID',
    'cell_prep_type': 'Cell Prep Type',
    'sequencing_vendor': 'Sequencing Vendor',
    'alignment_method': 'Alignment Method',
    'library_prep_method_id': 'Library Prep Method ID',
    'library_prep_name': 'Library Prep Name',
    'organism_common_name': 'Organism Common Name'
};

document.addEventListener('DOMContentLoaded', function() {
    // Initialize column visibility from localStorage
    initializeColumnVisibility();
    
    // Set up column visibility toggle event listeners
    setupColumnToggleListeners();
    
    // Prevent dropdown from closing when clicked inside
    document.getElementById('column-settings-dropdown')?.addEventListener('click', function(e) {
        e.stopPropagation();
    });

    // Wait a bit for the table to be fully rendered
    setTimeout(debugTableColumns, 1000);
});

/**
 * Initialize column visibility based on saved preferences
 */
function initializeColumnVisibility() {
    // Get saved preferences from localStorage
    const showBatchName = localStorage.getItem('showBatchName') !== 'false';
    const showBatchNameFromVendor = localStorage.getItem('showBatchNameFromVendor') !== 'false';
    const showCellCapture = localStorage.getItem('showCellCapture') !== 'false';
    const showSampleId = localStorage.getItem('showSampleId') !== 'false';
    const showAmplificationName = localStorage.getItem('showAmplificationName') !== 'false';
    const showAmplificationId = localStorage.getItem('showAmplificationId') !== 'false';
    const showCellPrepType = localStorage.getItem('showCellPrepType') !== 'false';
    const showSequencingVendor = localStorage.getItem('showSequencingVendor') !== 'false';
    const showAlignmentMethod = localStorage.getItem('showAlignmentMethod') !== 'false';
    const showLibraryPrepMethodId = localStorage.getItem('showLibraryPrepMethodId') !== 'false';
    const showLibraryPrepName = localStorage.getItem('showLibraryPrepName') !== 'false';
    const showOrganismCommonName = localStorage.getItem('showOrganismCommonName') !== 'false';
    
    // Update checkboxes in the settings dropdown
    if (document.getElementById('toggleBatchName')) {
        document.getElementById('toggleBatchName').checked = showBatchName;
    }
    
    if (document.getElementById('toggleBatchNameFromVendor')) {
        document.getElementById('toggleBatchNameFromVendor').checked = showBatchNameFromVendor;
    }
    
    if (document.getElementById('toggleCellCapture')) {
        document.getElementById('toggleCellCapture').checked = showCellCapture;
    }
    
    if (document.getElementById('toggleSampleId')) {
        document.getElementById('toggleSampleId').checked = showSampleId;
    }
    
    if (document.getElementById('toggleAmplificationName')) {
        document.getElementById('toggleAmplificationName').checked = showAmplificationName;
    }
    
    if (document.getElementById('toggleAmplificationId')) {
        document.getElementById('toggleAmplificationId').checked = showAmplificationId;
    }
    
    if (document.getElementById('toggleCellPrepType')) {
        document.getElementById('toggleCellPrepType').checked = showCellPrepType;
    }
    
    if (document.getElementById('toggleSequencingVendor')) {
        document.getElementById('toggleSequencingVendor').checked = showSequencingVendor;
    }
    
    if (document.getElementById('toggleAlignmentMethod')) {
        document.getElementById('toggleAlignmentMethod').checked = showAlignmentMethod;
    }
    
    if (document.getElementById('toggleLibraryPrepMethodId')) {
        document.getElementById('toggleLibraryPrepMethodId').checked = showLibraryPrepMethodId;
    }
    
    if (document.getElementById('toggleLibraryPrepName')) {
        document.getElementById('toggleLibraryPrepName').checked = showLibraryPrepName;
    }
    
    if (document.getElementById('toggleOrganismCommonName')) {
        document.getElementById('toggleOrganismCommonName').checked = showOrganismCommonName;
    }
    
    // Apply column visibility based on preferences
    applyColumnVisibility('batch_name', showBatchName);
    applyColumnVisibility('batch_name_from_vendor', showBatchNameFromVendor);
    applyColumnVisibility('cell_capture', showCellCapture);
    applyColumnVisibility('sample_id', showSampleId);
    applyColumnVisibility('amplification_name', showAmplificationName);
    applyColumnVisibility('amplification_id', showAmplificationId);
    applyColumnVisibility('cell_prep_type', showCellPrepType);
    applyColumnVisibility('sequencing_vendor', showSequencingVendor);
    applyColumnVisibility('alignment_method', showAlignmentMethod);
    applyColumnVisibility('library_prep_method_id', showLibraryPrepMethodId);
    applyColumnVisibility('library_prep_name', showLibraryPrepName);
    applyColumnVisibility('organism_common_name', showOrganismCommonName);
}

/**
 * Set up event listeners for column toggle controls
 */
function setupColumnToggleListeners() {
    // Batch Name toggle
    const batchNameToggle = document.getElementById('toggleBatchName');
    if (batchNameToggle) {
        batchNameToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('batch_name', isVisible);
            localStorage.setItem('showBatchName', isVisible);
            showToggleMessage(`${columnMappings['batch_name']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Batch Name From Vendor toggle
    const batchNameFromVendorToggle = document.getElementById('toggleBatchNameFromVendor');
    if (batchNameFromVendorToggle) {
        batchNameFromVendorToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('batch_name_from_vendor', isVisible);
            localStorage.setItem('showBatchNameFromVendor', isVisible);
            showToggleMessage(`${columnMappings['batch_name_from_vendor']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Cell Capture toggle
    const cellCaptureToggle = document.getElementById('toggleCellCapture');
    if (cellCaptureToggle) {
        cellCaptureToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('cell_capture', isVisible);
            localStorage.setItem('showCellCapture', isVisible);
            showToggleMessage(`${columnMappings['cell_capture']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Sample ID toggle
    const sampleIdToggle = document.getElementById('toggleSampleId');
    if (sampleIdToggle) {
        sampleIdToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('sample_id', isVisible);
            localStorage.setItem('showSampleId', isVisible);
            showToggleMessage(`${columnMappings['sample_id']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Amplification Name toggle
    const amplificationNameToggle = document.getElementById('toggleAmplificationName');
    if (amplificationNameToggle) {
        amplificationNameToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('amplification_name', isVisible);
            localStorage.setItem('showAmplificationName', isVisible);
            showToggleMessage(`${columnMappings['amplification_name']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Amplification ID toggle
    const amplificationIdToggle = document.getElementById('toggleAmplificationId');
    if (amplificationIdToggle) {
        amplificationIdToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('amplification_id', isVisible);
            localStorage.setItem('showAmplificationId', isVisible);
            showToggleMessage(`${columnMappings['amplification_id']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Cell Prep Type toggle
    const cellPrepTypeToggle = document.getElementById('toggleCellPrepType');
    if (cellPrepTypeToggle) {
        cellPrepTypeToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('cell_prep_type', isVisible);
            localStorage.setItem('showCellPrepType', isVisible);
            showToggleMessage(`${columnMappings['cell_prep_type']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Sequencing Vendor toggle
    const sequencingVendorToggle = document.getElementById('toggleSequencingVendor');
    if (sequencingVendorToggle) {
        sequencingVendorToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('sequencing_vendor', isVisible);
            localStorage.setItem('showSequencingVendor', isVisible);
            showToggleMessage(`${columnMappings['sequencing_vendor']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Alignment Method toggle
    const alignmentMethodToggle = document.getElementById('toggleAlignmentMethod');
    if (alignmentMethodToggle) {
        alignmentMethodToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('alignment_method', isVisible);
            localStorage.setItem('showAlignmentMethod', isVisible);
            showToggleMessage(`${columnMappings['alignment_method']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Library Prep Method ID toggle
    const libraryPrepMethodIdToggle = document.getElementById('toggleLibraryPrepMethodId');
    if (libraryPrepMethodIdToggle) {
        libraryPrepMethodIdToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('library_prep_method_id', isVisible);
            localStorage.setItem('showLibraryPrepMethodId', isVisible);
            showToggleMessage(`${columnMappings['library_prep_method_id']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Library Prep Name toggle
    const libraryPrepNameToggle = document.getElementById('toggleLibraryPrepName');
    if (libraryPrepNameToggle) {
        libraryPrepNameToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('library_prep_name', isVisible);
            localStorage.setItem('showLibraryPrepName', isVisible);
            showToggleMessage(`${columnMappings['library_prep_name']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
    
    // Organism Common Name toggle
    const organismCommonNameToggle = document.getElementById('toggleOrganismCommonName');
    if (organismCommonNameToggle) {
        organismCommonNameToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            applyColumnVisibility('organism_common_name', isVisible);
            localStorage.setItem('showOrganismCommonName', isVisible);
            showToggleMessage(`${columnMappings['organism_common_name']} column ${isVisible ? 'shown' : 'hidden'}`);
        });
    }
}

/**
 * Apply visibility to a table column
 * @param {string} columnClass - The class name of the column to toggle
 * @param {boolean} isVisible - Whether the column should be visible
 */
function applyColumnVisibility(columnClass, isVisible) {
    // Find the table in the DOM
    const table = document.querySelector('.table-container table');
    if (!table) return;

    // Find all column headers to identify the index of the column to toggle
    const headers = table.querySelectorAll('thead th');
    let columnIndex = -1;
    
    // Try to find the column by class first
    headers.forEach((header, index) => {
        if (header.classList.contains(`column-${columnClass}`)) {
            columnIndex = index;
        }
    });
    
    // If column not found by class, try to find it by text content
    if (columnIndex === -1) {
        // Get the display title from our mapping
        const columnTitle = columnMappings[columnClass] || columnClass
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
            
        headers.forEach((header, index) => {
            if (header.textContent.trim() === columnTitle || 
                header.textContent.trim().includes(columnTitle)) {
                columnIndex = index;
            }
        });
    }
    
    console.log(`Column ${columnClass} (${columnMappings[columnClass]}) found at index: ${columnIndex}`);
    
    // If we found the column index, toggle visibility of all cells in that column
    if (columnIndex !== -1) {
        // Toggle the header
        headers[columnIndex].style.display = isVisible ? '' : 'none';
        
        // Toggle all cells in this column
        const rows = table.querySelectorAll('tbody tr');
        rows.forEach(row => {
            const cells = row.querySelectorAll('td');
            if (cells.length > columnIndex) {
                cells[columnIndex].style.display = isVisible ? '' : 'none';
            }
        });
        
        // Log a confirmation message
        console.log(`Column ${columnClass} visibility set to ${isVisible}`);
    } else {
        console.warn(`Column ${columnClass} not found in the table`);
        
        // Fallback to the old method if column index not found
        // Get all table header cells with the class name
        const headerCells = document.querySelectorAll(`th.column-${columnClass}`);
        
        // Get all table data cells with the class name
        const dataCells = document.querySelectorAll(`td.field-${columnClass}`);
        
        // Apply visibility to all cells
        headerCells.forEach(cell => {
            cell.style.display = isVisible ? '' : 'none';
        });
        
        dataCells.forEach(cell => {
            cell.style.display = isVisible ? '' : 'none';
        });
    }
}

/**
 * Show a temporary message when a column is toggled
 * @param {string} message - The message to display
 */
function showToggleMessage(message) {
    // Create message element if it doesn't exist
    let messageElement = document.getElementById('toggle-feedback');
    if (!messageElement) {
        messageElement = document.createElement('div');
        messageElement.id = 'toggle-feedback';
        messageElement.className = 'toggle-feedback';
        document.body.appendChild(messageElement);
    }
    
    // Set message text
    messageElement.textContent = message;
    
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
        console.log(`${key} -> "${value}"`);
    });
} 