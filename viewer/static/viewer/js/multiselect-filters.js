// Sample browser utilities with selection panel
console.log('Loading sample browser utilities...');

/**
 * Utility function for logging with consistent format
 * @param {string} message - The message to log
 * @param {any} data - Optional data to log
 */
function logDebug(message, data) {
    if (window.DEBUG_MODE) {
        if (data !== undefined) {
            console.log(message, data);
        } else {
            console.log(message);
        }
    }
}

/**
 * Utility function to safely get elements and log errors if not found
 * @param {string} selector - The CSS selector
 * @param {string} elementName - A descriptive name for the element
 * @returns {Element|null} - The found element or null
 */
function getElement(selector, elementName) {
    const element = document.querySelector(selector);
    if (!element && elementName) {
        console.error(`${elementName} not found (${selector})`);
    }
    return element;
}

document.addEventListener('DOMContentLoaded', function () {
    logDebug('DOM loaded, initializing sample browser utilities');

    // Initialize selection panel if it exists
    initSelectionPanel();
});

// Show a feedback message to the user
function showFeedbackMessage(message, type = 'info', duration = 1500) {
    // Create or reuse the message container
    let messageContainer = document.getElementById('filter-feedback-message');
    if (!messageContainer) {
        messageContainer = document.createElement('div');
        messageContainer.id = 'filter-feedback-message';
        messageContainer.className = 'toast-message';
        document.body.appendChild(messageContainer);
    }

    // Configure the message
    const icon = '<i class="bi bi-stars"></i>';  // Always use stars icon
    messageContainer.innerHTML = `${icon} ${message}`;
    messageContainer.className = `toast-message ${type} show`;

    // Apply styles - use CSS classes where possible
    const styles = {
        position: 'fixed',
        bottom: '24px',
        left: '50%',
        transform: 'translate(-50%, 100%)',
        zIndex: '9999',
        backgroundColor: '#1976D2',
        color: '#fff',
        padding: '14px 24px',
        borderRadius: '8px',
        minWidth: '200px',
        maxWidth: '600px',
        boxShadow: '0 3px 5px -1px rgba(25, 118, 210, 0.2), 0 6px 10px 0 rgba(25, 118, 210, 0.14), 0 1px 18px 0 rgba(25, 118, 210, 0.12)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        fontSize: '15px',
        lineHeight: '1.4',
        fontWeight: '500',
        textAlign: 'center',
        transition: 'transform 0.15s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.15s cubic-bezier(0.4, 0, 0.2, 1)',
        opacity: '0'
    };

    // Apply all styles at once
    Object.assign(messageContainer.style, styles);

    // Show animation
    requestAnimationFrame(() => {
        messageContainer.style.opacity = '1';
        messageContainer.style.transform = 'translate(-50%, 0)';
    });

    // Hide and remove after duration
    setTimeout(() => {
        messageContainer.style.opacity = '0';
        messageContainer.style.transform = 'translate(-50%, 100%)';

        // Remove from DOM after animation
        setTimeout(() => {
            if (messageContainer.parentNode) {
                messageContainer.parentNode.removeChild(messageContainer);
            }
        }, 150);
    }, duration);
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

/**
 * Helper function to extract sample data from a row
 * @param {HTMLElement} row - The table row element to extract data from
 * @returns {Object|null} - The extracted sample data or null if error
 */
function getSampleDataFromRow(row) {
    if (!row) {
        console.error('No row provided to getSampleDataFromRow');
        return null;
    }

    // Initialize data object with empty fields
    let data = {
        fastqName: null,
        studySet: null,
        loadName: null,
        batchNameFromVendor: null,
        libraryPrepMethod: null,
        organismCommonName: null,
        ingestStatus: null,
        alignmentStatus: null,
        postqcStatus: null
    };

    // Define attribute mappings once - used for both data extraction and logging
    const attributeMappings = {
        fastqName: ['data-fastq-name'],
        studySet: ['data-study-set'],
        loadName: ['data-load-name'],
        batchNameFromVendor: ['data-batch-name-from-vendor'],
        organismCommonName: ['data-organism-common-name'],
        libraryPrepMethod: ['data-library-prep-method'],
        ingestStatus: ['data-ingest-status'],
        alignmentStatus: ['data-alignment-status'],
        postqcStatus: ['data-postqc-status']
    };

    // Define header text to field name mappings - same keys as data object
    const headerMappings = {
        'fastq name': 'fastqName',
        'study set': 'studySet',
        'load name': 'loadName',
        'batch name from vendor': 'batchNameFromVendor',
        'organism common name': 'organismCommonName',
        'library prep method': 'libraryPrepMethod',
        'ingest status': 'ingestStatus',
        'alignment status': 'alignmentStatus',
        'postqc status': 'postqcStatus'
    };

    // For debugging only
    const DEBUG_SAMPLE_EXTRACTION = window.DEBUG_MODE || false;

    if (DEBUG_SAMPLE_EXTRACTION) {
        console.log('Row element:', row);
        console.log('=== All Row Data Attributes ===');
    }

    // STEP 1: Extract data from HTML attributes
    for (const [field, attributes] of Object.entries(attributeMappings)) {
        for (const attr of attributes) {
            const value = row.getAttribute(attr);

            if (DEBUG_SAMPLE_EXTRACTION) {
                console.log(`${field} (${attr}): ${value}`);
            }

            // Set data if value exists
            if (value) {
                data[field] = value;
                break; // Stop checking other attributes for this field
            }
        }
    }

    // STEP 2: If attributes not complete, extract from table cells
    const cells = row.querySelectorAll('td');
    if (cells.length > 0) {
        // Create a mapping from header text to column index
        const columnMap = {};
        const table = row.closest('table');

        if (DEBUG_SAMPLE_EXTRACTION) {
            console.log('=== Table Cell Contents ===');
            cells.forEach((cell, index) => {
                console.log(`Cell ${index}: ${cell.textContent.trim()}`);
            });
        }

        if (table) {
            const headerRow = table.querySelector('thead tr');
            if (headerRow) {
                const headerCells = headerRow.querySelectorAll('th');

                if (DEBUG_SAMPLE_EXTRACTION) {
                    console.log('=== Header Cell Mapping ===');
                    headerCells.forEach((cell, index) => {
                        console.log(`Header ${index}: ${cell.textContent.trim()}`);
                    });
                }

                // Map each header to a field
                headerCells.forEach((cell, index) => {
                    const headerText = cell.textContent.trim().toLowerCase();

                    for (const [text, field] of Object.entries(headerMappings)) {
                        if (headerText.includes(text)) {
                            // Skip library prep method ID
                            if (field === 'libraryPrepMethod' && headerText === 'library prep method id') {
                                continue;
                            }
                            columnMap[field] = index;

                            if (DEBUG_SAMPLE_EXTRACTION) {
                                console.log(`Mapped ${headerText} to ${field} at index ${index}`);
                            }
                            break;
                        }
                    }
                });

                if (DEBUG_SAMPLE_EXTRACTION) {
                    console.log('=== Column Mapping ===', columnMap);
                }

                // Extract data from cells based on the mapping (only if not already set from attributes)
                for (const [field, index] of Object.entries(columnMap)) {
                    if (!data[field] && cells[index]) {
                        data[field] = cells[index].textContent.trim();

                        if (DEBUG_SAMPLE_EXTRACTION) {
                            console.log(`Extracted from cell - ${field}: ${data[field]}`);
                        }
                    }
                }
            }
        }
    }

    // STEP 3: Set ID and name if not already set
    if (!data.id) {
        data.id = data.fastqName || `row-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    }
    if (!data.name) {
        data.name = data.fastqName || data.id;
    }

    // STEP 4: Ensure all properties are strings (instead of null/undefined)
    for (const key in data) {
        data[key] = data[key] || '';
    }

    if (DEBUG_SAMPLE_EXTRACTION) {
        console.log('=== Final Extracted and Cleaned Data ===', data);
    }

    return data;
}

/**
 * Initializes the floating selection action panel
 */
function initSelectionPanel() {
    logDebug('initSelectionPanel called');

    // Get required elements
    const selectionPanel = getElement('#selection-actions', 'Selection panel');
    const selectionCount = getElement('#selected-count', 'Selection count');
    const clearSelectionBtn = getElement('#clear-selection-btn', 'Clear selection button');
    const sendToPipelineBtn = getElement('#send-to-pipeline-btn', 'Send to pipeline button');
    const selectAllCheckbox = getElement('#select-all-samples', 'Select all checkbox');

    if (!selectionPanel) return;

    // Check if we're on the main sample page by looking for sample checkboxes
    const checkboxes = document.querySelectorAll('.sample-select');
    logDebug('Found sample checkboxes:', checkboxes.length);

    if (!checkboxes.length) {
        logDebug('No sample checkboxes found, exiting');
        return;
    }

    // Initialize panel state
    selectionPanel.style.display = 'none';
    window.selectedSamples = window.selectedSamples || [];

    // Initialize from current checkbox state
    initializeFromCheckboxState();

    // Set up event handlers
    if (clearSelectionBtn) {
        clearSelectionBtn.addEventListener('click', handleClearSelection);
    }

    if (sendToPipelineBtn) {
        sendToPipelineBtn.addEventListener('click', handleSendToPipeline);
    }

    // Initialize sample checkboxes
    initializeSampleCheckboxes();

    // Initialize "Select All" checkbox
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', handleSelectAllChange);
    }

    // Initial update of panel
    updateSelectionPanel();

    // Helper functions

    /**
     * Initialize selected samples from current checkbox state
     */
    function initializeFromCheckboxState() {
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
    }

    /**
     * Handle clicking the clear selection button
     */
    function handleClearSelection() {
        // Uncheck all checkboxes
        document.querySelectorAll('.sample-select').forEach(checkbox => {
            if (checkbox.id !== 'select-all-samples') {
                checkbox.checked = false;
            }
        });

        // Clear "Select All" checkbox
        if (selectAllCheckbox) {
            selectAllCheckbox.checked = false;
        }

        // Update selection panel
        selectedSamples = [];
        updateSelectionPanel();
    }

    /**
     * Set up event handlers for individual sample checkboxes
     */
    function initializeSampleCheckboxes() {
        document.querySelectorAll('.sample-select').forEach(checkbox => {
            // Skip the select all checkbox
            if (checkbox.id === 'select-all-samples') return;

            checkbox.addEventListener('change', function () {
                const row = this.closest('tr');
                if (!row) {
                    console.error('No parent row found for checkbox');
                    return;
                }

                const data = getSampleDataFromRow(row);
                if (!data || !data.id) {
                    console.error('Invalid sample data extracted from row');
                    return;
                }

                if (this.checked) {
                    // Add to selected samples if not already there
                    if (!selectedSamples.some(s => s.id === data.id)) {
                        logDebug('Adding sample to selection:', data.id);
                        selectedSamples.push(data);
                    }
                } else {
                    // Remove from selected samples
                    logDebug('Removing sample from selection:', data.id);
                    selectedSamples = selectedSamples.filter(s => s.id !== data.id);
                }

                updateSelectionPanel();
            });
        });
    }

    /**
     * Handle changes to "Select All" checkbox
     */
    function handleSelectAllChange() {
        selectedSamples = []; // Reset the selected samples array

        document.querySelectorAll('.sample-select').forEach(checkbox => {
            // Skip the select all checkbox itself
            if (checkbox.id === 'select-all-samples') return;

            checkbox.checked = selectAllCheckbox.checked;

            if (selectAllCheckbox.checked) {
                const row = checkbox.closest('tr');
                if (row) {
                    const data = getSampleDataFromRow(row);
                    if (data && data.id) {
                        selectedSamples.push(data);
                    }
                }
            }
        });

        logDebug('Select all changed, selectedSamples count:', selectedSamples.length);
        updateSelectionPanel();
    }

    /**
     * Handle sending selected samples to pipeline
     */
    function handleSendToPipeline() {
        if (selectedSamples.length === 0) {
            showFeedbackMessage('No samples selected', 'warning');
            return;
        }

        // Show loading state
        sendToPipelineBtn.disabled = true;
        sendToPipelineBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';

        // Process samples in batches
        processSamplesInBatches();
    }

    /**
     * Process samples in batches to avoid UI blocking
     */
    function processSamplesInBatches() {
        const cleanedSamples = [];
        const batchSize = 200;
        let currentBatch = 0;

        processBatch();

        function processBatch() {
            const startIdx = currentBatch * batchSize;
            const endIdx = Math.min(startIdx + batchSize, selectedSamples.length);

            // Process this batch
            for (let i = startIdx; i < endIdx; i++) {
                const sample = selectedSamples[i];
                // Map to pipeline format with essential fields only
                cleanedSamples.push({
                    fastq_name: sample.fastqName || '',
                    study_set: sample.studySet || '',
                    load_name: sample.loadName || '',
                    batch_name_from_vendor: sample.batchNameFromVendor || '',
                    organism_common_name: sample.organismCommonName || '',
                    library_prep_method: sample.libraryPrepMethod || '',
                    ingest_status: sample.ingestStatus || 'Not Started',
                    alignment_status: sample.alignmentStatus || 'Not Started',
                    postqc_status: sample.postqcStatus || 'Not Started'
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
            // Store cleaned samples in localStorage
            const storageItem = {
                timestamp: new Date().getTime(),
                samples: cleanedSamples
            };

            try {
                // Store the data
                localStorage.setItem('selectedSamplesForPipeline', JSON.stringify(storageItem));
                showFeedbackMessage(`${selectedSamples.length} samples sent to Pipeline Dashboard`, 'success');

                // Redirect to pipeline dashboard
                setTimeout(() => {
                    window.location.href = '/pipeline/';
                }, 300);
            } catch (error) {
                console.error('Error storing samples:', error);

                // Handle storage errors
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
            // Try with a reduced sample set
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
                // If still failing, show error
                console.error('Still failed with reduced set:', error);
                showFeedbackMessage('Storage limit exceeded. Please select fewer samples.', 'danger');
                sendToPipelineBtn.disabled = false;
                sendToPipelineBtn.innerHTML = 'Send to Pipeline <i class="bi bi-arrow-right"></i>';
            }
        }
    }

    // Streamlined selection panel update function
    function updateSelectionPanel() {
        const selectionPanel = getElement('#selection-actions', 'Selection panel');
        const selectionCount = getElement('#selected-count', 'Selection count');

        if (!selectionPanel || !window.selectedSamples) return;

        logDebug('updateSelectionPanel called with', selectedSamples.length);

        // Filter out any invalid entries (missing id)
        selectedSamples = selectedSamples.filter(sample => sample && sample.id);

        if (selectedSamples.length > 0) {
            selectionPanel.style.display = 'flex';
            if (selectionCount) {
                selectionCount.textContent = selectedSamples.length;
            }
        } else {
            selectionPanel.style.display = 'none';
        }
    }
} 