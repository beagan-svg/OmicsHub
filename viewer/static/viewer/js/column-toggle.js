document.addEventListener('DOMContentLoaded', function() {
    // Initialize column visibility from localStorage
    initializeColumnVisibility();
    
    // Set up column visibility toggle event listeners
    setupColumnToggleListeners();
});

/**
 * Initialize column visibility based on saved preferences
 */
function initializeColumnVisibility() {
    // Get saved preferences from localStorage
    const showBatchName = localStorage.getItem('showBatchName') !== 'false';
    const showCellCapture = localStorage.getItem('showCellCapture') !== 'false';
    
    // Update checkboxes in the settings panel
    if (document.getElementById('toggleBatchName')) {
        document.getElementById('toggleBatchName').checked = showBatchName;
    }
    
    if (document.getElementById('toggleCellCapture')) {
        document.getElementById('toggleCellCapture').checked = showCellCapture;
    }
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
            toggleColumnVisibility('batch_name', isVisible);
            localStorage.setItem('showBatchName', isVisible);
        });
    }
    
    // Cell Capture toggle
    const cellCaptureToggle = document.getElementById('toggleCellCapture');
    if (cellCaptureToggle) {
        cellCaptureToggle.addEventListener('change', function() {
            const isVisible = this.checked;
            toggleColumnVisibility('cell_capture', isVisible);
            localStorage.setItem('showCellCapture', isVisible);
        });
    }
    
    // Toggle settings panel
    const settingsToggle = document.getElementById('column-settings-toggle');
    const settingsPanel = document.getElementById('column-settings-panel');
    
    if (settingsToggle && settingsPanel) {
        settingsToggle.addEventListener('click', function() {
            if (settingsPanel.style.display === 'none' || !settingsPanel.style.display) {
                settingsPanel.style.display = 'block';
                settingsToggle.innerHTML = '<i class="bi bi-gear-fill"></i> Hide Column Settings';
            } else {
                settingsPanel.style.display = 'none';
                settingsToggle.innerHTML = '<i class="bi bi-gear"></i> Column Settings';
            }
        });
    }
}

/**
 * Toggle visibility of a table column
 * @param {string} columnClass - The class name of the column to toggle
 * @param {boolean} isVisible - Whether the column should be visible
 */
function toggleColumnVisibility(columnClass, isVisible) {
    // Get all table cells with the specified column class
    const cells = document.querySelectorAll(`.field-${columnClass}, .column-${columnClass}, th[class*="${columnClass}"]`);
    
    // Set display property based on visibility
    cells.forEach(cell => {
        cell.style.display = isVisible ? '' : 'none';
    });
} 