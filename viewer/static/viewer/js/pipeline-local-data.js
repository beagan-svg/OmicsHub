/**
 * pipeline-local-data.js
 * Handles local storage of selected samples and rebuilding the pipeline table
 */

// Add immediate debugging to see if script is loaded
console.log('pipeline-local-data.js is being loaded');

class PipelineLocalData {
    constructor() {
        this.storageKey = 'pipelineSelectedSamples';
        this.legacyStorageKey = 'selectedSamplesForPipeline'; // Add legacy key from main_list.html
        this.init();

        // Log constructor completion
        console.log('PipelineLocalData constructor complete');
    }

    init() {
        // Initialize the selected samples from local storage
        this.selectedSamples = this.getStoredSamples();

        // Initialize event listeners once DOM is loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                console.log('DOM loaded - setting up event listeners');
                this.setupEventListeners();

                // Add a small delay to reinitialize after page is fully loaded
                setTimeout(() => this.reinitialize(), 300);
            });
        } else {
            // DOM already loaded, set up listeners now
            console.log('DOM already loaded - setting up event listeners immediately');
            this.setupEventListeners();

            // Add a small delay to reinitialize after page is fully loaded
            setTimeout(() => this.reinitialize(), 300);
        }

        console.log('PipelineLocalData initialized');
    }

    setupEventListeners() {
        // Listen for sample selection changes
        this.setupSelectionListeners();

        // Listen for submit button click
        const submitBtn = document.getElementById('confirm-submit');
        if (submitBtn) {
            submitBtn.addEventListener('click', (e) => this.handleSampleSubmission(e));
        }

        // Listen for clear selection button click
        const clearBtn = document.getElementById('clear-selection');
        if (clearBtn) {
            console.log('Adding event listener to clear-selection button');
            clearBtn.addEventListener('click', () => {
                console.log('Clear button clicked directly on PipelineLocalData');
                this.clearStoredData();

                // Show success notification
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-success alert-dismissible fade show';
                alertDiv.setAttribute('role', 'alert');
                alertDiv.innerHTML = `
                    <i class="bi bi-check-circle-fill me-2"></i>
                    Selection cleared successfully.
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                `;

                // Insert alert
                const container = document.querySelector('.container-fluid');
                if (container) {
                    container.insertBefore(alertDiv, container.firstChild);

                    // Auto-dismiss after 3 seconds
                    setTimeout(() => {
                        try {
                            const bsAlert = new bootstrap.Alert(alertDiv);
                            bsAlert.close();
                        } catch (err) {
                            if (alertDiv.parentNode) {
                                alertDiv.parentNode.removeChild(alertDiv);
                            }
                        }
                    }, 3000);
                }
            });
        } else {
            console.log('Clear button not found!');
        }

        // Rebuild the table on page load
        this.rebuildSamplesTable();

        console.log('PipelineLocalData event listeners set up');
    }

    setupSelectionListeners() {
        // Handle individual sample selection
        const sampleCheckboxes = document.querySelectorAll('.sample-select');
        sampleCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => this.updateSelectedSamples());
        });

        // Handle select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-samples');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', () => {
                const isChecked = selectAllCheckbox.checked;
                sampleCheckboxes.forEach(cb => {
                    cb.checked = isChecked;
                });
                this.updateSelectedSamples();
            });
        }
    }

    updateSelectedSamples() {
        const samples = [];
        const selectedRows = document.querySelectorAll('.sample-select:checked');

        selectedRows.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                samples.push({
                    fastq_name: row.querySelector('td:nth-child(2)').textContent.trim(),
                    batch_name: row.querySelector('td:nth-child(3)').textContent.trim(),
                    organism: row.querySelector('td:nth-child(4)').textContent.trim(),
                    library_prep: row.querySelector('td:nth-child(5)').textContent.trim(),
                    ingest_status: row.querySelector('td:nth-child(6)').textContent.trim(),
                    alignment_status: row.querySelector('td:nth-child(7)').textContent.trim(),
                    postqc_status: row.querySelector('td:nth-child(8)').textContent.trim()
                });
            }
        });

        this.selectedSamples = samples;
        this.storeSamples();
    }

    getStoredSamples() {
        try {
            console.log('getStoredSamples called');

            // First try with our primary key
            const storedData = localStorage.getItem(this.storageKey);
            if (storedData) {
                console.log(`Found data using primary key: ${this.storageKey}`);
                const parsedData = JSON.parse(storedData);
                return this.normalizeStoredSamples(parsedData);
            }

            // If not found, try with the legacy key from main_list.html
            const legacyStoredData = localStorage.getItem(this.legacyStorageKey);
            if (legacyStoredData) {
                console.log(`Found data using legacy key: ${this.legacyStorageKey}`);

                // Parse the JSON data
                try {
                    const parsedData = JSON.parse(legacyStoredData);
                    console.log('Parsed legacy data:', parsedData);

                    // Check various possible formats
                    let samplesToNormalize;

                    // Format 1: {timestamp, samples} from multiselect-filters.js
                    if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData) &&
                        parsedData.samples && Array.isArray(parsedData.samples)) {
                        console.log('Found data in {timestamp, samples} format, extracting samples array');
                        samplesToNormalize = parsedData.samples;
                    }
                    // Format 2: Direct array of samples from main_list.html
                    else if (Array.isArray(parsedData)) {
                        console.log('Found data as direct array of samples');
                        samplesToNormalize = parsedData;
                    }
                    // Format 3: Single sample object (unlikely but handle it)
                    else if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
                        console.log('Found data as single sample object, wrapping in array');
                        samplesToNormalize = [parsedData];
                    }
                    else {
                        console.error('Unrecognized data format in localStorage:', parsedData);
                        samplesToNormalize = [];
                    }

                    // Normalize the samples
                    if (samplesToNormalize && samplesToNormalize.length > 0) {
                        console.log(`Normalizing ${samplesToNormalize.length} samples`);
                        const normalizedSamples = this.normalizeStoredSamples(samplesToNormalize);

                        // Store normalized samples with our primary key for future use
                        localStorage.setItem(this.storageKey, JSON.stringify(normalizedSamples));
                        return normalizedSamples;
                    }
                } catch (parseError) {
                    console.error('Error parsing legacy data:', parseError);
                }
            }

            console.log('No local data found in either storage key');
            return [];
        } catch (error) {
            console.error('Error retrieving stored samples:', error);
            return [];
        }
    }

    // Normalize data from different formats (main_list.html vs pipeline format)
    normalizeStoredSamples(samples) {
        console.log('Normalizing samples from storage:', samples);

        if (!Array.isArray(samples)) {
            console.error('Expected samples to be an array, but got:', typeof samples);
            return [];
        }

        return samples.map(sample => {
            const normalizedSample = {};

            console.log('Processing sample:', sample);

            // Handle different property names between formats
            // Special handling for fastq_name which could come from different fields
            if (sample.fastq_name) {
                normalizedSample.fastq_name = sample.fastq_name;
            } else if (sample.name) {
                normalizedSample.fastq_name = sample.name;
                console.log('Using name property for fastq_name:', sample.name);
            } else if (sample.id) {
                normalizedSample.fastq_name = sample.id;
                console.log('Using id property for fastq_name:', sample.id);
            } else {
                normalizedSample.fastq_name = 'Unknown Sample';
                console.warn('No identifier found for sample');
            }

            // Handle batch name variations
            normalizedSample.batch_name = sample.batch_name || sample.batchName || '';

            // Other standard fields
            normalizedSample.organism = sample.organism || '';
            normalizedSample.library_prep = sample.library_prep || sample.libraryPrep || '';
            normalizedSample.ingest_status = sample.ingest_status || sample.ingestStatus || 'Unknown';
            normalizedSample.alignment_status = sample.alignment_status || 'Not Started';
            normalizedSample.postqc_status = sample.postqc_status || 'Not Started';

            // Keep original status if it exists
            if (sample.status) {
                normalizedSample.status = sample.status;
            }

            // Copy any other properties that might be useful
            Object.keys(sample).forEach(key => {
                if (!normalizedSample.hasOwnProperty(key) && sample[key] !== undefined) {
                    normalizedSample[key] = sample[key];
                }
            });

            console.log('Normalized sample:', normalizedSample);
            return normalizedSample;
        });
    }

    storeSamples() {
        try {
            localStorage.setItem(this.storageKey, JSON.stringify(this.selectedSamples));
            console.log(`Stored ${this.selectedSamples.length} samples in localStorage`);
        } catch (error) {
            console.error('Error storing samples:', error);
        }
    }

    handleSampleSubmission(event) {
        // Update selected samples before submission
        this.updateSelectedSamples();

        // Get workflow information
        const workflow = document.getElementById('workflow-type').value;
        const reference = document.getElementById('reference-genome').value;
        const chemistry = document.getElementById('chemistry-version').value;

        // Add workflow info to the stored samples
        this.selectedSamples.forEach(sample => {
            sample.workflow = workflow;
            sample.reference = reference;
            sample.chemistry = chemistry;
            sample.submission_time = new Date().toISOString();
            sample.status = 'Submitted';
        });

        // Store updated samples
        this.storeSamples();

        // Rebuild the table with updated data
        this.rebuildSamplesTable();

        // Close the modal if it's open
        const submitModal = bootstrap.Modal.getInstance(document.getElementById('submit-modal'));
        if (submitModal) {
            submitModal.hide();
        }

        // Show success notification
        this.showSubmissionAlert(this.selectedSamples.length, workflow);
    }

    showSubmissionAlert(count, workflow) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-primary alert-dismissible fade show';
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            <i class="bi bi-play-circle-fill me-2"></i>
            Submitted ${count} samples for ${workflow} processing.
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Insert alert at the top of the page
        const container = document.querySelector('.container-fluid');
        if (container) {
            container.insertBefore(alertDiv, container.firstChild);

            // Auto-dismiss after 8 seconds
            setTimeout(() => {
                try {
                    const bsAlert = new bootstrap.Alert(alertDiv);
                    bsAlert.close();
                } catch (err) {
                    // Fallback if bootstrap Alert API fails
                    if (alertDiv.parentNode) {
                        alertDiv.parentNode.removeChild(alertDiv);
                    }
                }
            }, 8000);
        }
    }

    rebuildSamplesTable() {
        // Get the table body
        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) {
            console.error('Table body not found');
            return;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        // Check if we have stored samples
        if (!this.selectedSamples || this.selectedSamples.length === 0) {
            // Show empty state message
            console.log('No samples to display in the table');

            // Add a message row to indicate empty table
            const emptyRow = document.createElement('tr');
            emptyRow.className = 'text-center text-muted';
            emptyRow.innerHTML = `
                <td colspan="8" class="py-4">
                    <i class="bi bi-inbox-fill me-2" style="font-size: 1.5rem;"></i>
                    <p>No samples selected. Use the Sample Browser to select samples.</p>
                    <a href="/" class="btn btn-sm btn-outline-primary mt-2">
                        <i class="bi bi-table me-1"></i>Go to Sample Browser
                    </a>
                </td>
            `;
            tableBody.appendChild(emptyRow);

            // Disable the submit button
            const submitBtn = document.getElementById('submit-selected');
            if (submitBtn) {
                submitBtn.disabled = true;
            }

            // Update the selected count display
            const selectedCount = document.getElementById('selected-count');
            if (selectedCount) {
                selectedCount.textContent = '0 samples selected';
            }

            return;
        }

        console.log(`Rebuilding table with ${this.selectedSamples.length} samples`, this.selectedSamples);

        // Rebuild table with stored samples
        this.selectedSamples.forEach((sample, index) => {
            const row = document.createElement('tr');
            const sampleName = sample.fastq_name || `Unknown Sample ${index + 1}`;
            row.dataset.fastq = sampleName;

            // Ensure every field has a fallback to prevent empty cells
            const batchName = sample.batch_name || 'Unknown';
            const organism = sample.organism || 'Unknown';
            const libraryPrep = sample.library_prep || 'Unknown';
            const ingestStatus = sample.ingest_status || 'Unknown';
            const alignmentStatus = sample.alignment_status || 'Not Started';
            const postqcStatus = sample.postqc_status || 'Not Started';

            row.innerHTML = `
                <td><input type="checkbox" class="sample-select" checked></td>
                <td>${sampleName}</td>
                <td>${batchName}</td>
                <td>${organism}</td>
                <td>${libraryPrep}</td>
                <td>${this.formatStatus(ingestStatus)}</td>
                <td>${this.formatStatus(alignmentStatus)}</td>
                <td>${this.formatStatus(postqcStatus)}</td>
            `;

            tableBody.appendChild(row);
        });

        // Re-attach event listeners
        this.setupSelectionListeners();

        // Update the active alignments section
        this.updateActiveAlignments();

        // Enable the submit button if we have samples
        const submitBtn = document.getElementById('submit-selected');
        if (submitBtn) {
            submitBtn.disabled = false;
        }

        // Update the selected count display
        const selectedCount = document.getElementById('selected-count');
        if (selectedCount) {
            selectedCount.textContent = `${this.selectedSamples.length} sample${this.selectedSamples.length !== 1 ? 's' : ''} selected`;
        }
    }

    formatStatus(status) {
        // Format status with appropriate badge
        if (!status) return '<span class="badge bg-secondary">Unknown</span>';

        if (status.toLowerCase().includes('completed')) {
            return '<span class="badge bg-success">Completed</span>';
        } else if (status.toLowerCase().includes('progress') || status.toLowerCase().includes('running')) {
            return '<span class="badge bg-warning">In Progress</span>';
        } else if (status.toLowerCase().includes('submitted')) {
            return '<span class="badge bg-info">Submitted</span>';
        } else if (status.toLowerCase().includes('failed')) {
            return '<span class="badge bg-danger">Failed</span>';
        } else if (status.toLowerCase().includes('not started')) {
            return '<span class="badge bg-secondary">Not Started</span>';
        }

        return `<span class="badge bg-secondary">${status}</span>`;
    }

    fetchSamplesFromServer() {
        // This would be replaced with an actual API call
        // For now, we'll use the demo data from the HTML
        console.log('No local data found. Would fetch from server in production.');
    }

    updateActiveAlignments() {
        const activeAlignmentsDiv = document.querySelector('.active-alignments');
        if (!activeAlignmentsDiv) return;

        // Get all samples that are in 'Submitted' or 'In Progress' state
        const runningAlignments = this.selectedSamples.filter(sample =>
            sample.status === 'Submitted' ||
            (sample.alignment_status && sample.alignment_status.toLowerCase().includes('progress')) ||
            (sample.alignment_status && sample.alignment_status.toLowerCase().includes('running'))
        );

        // Clear current alignments
        const noAlignmentsAlert = activeAlignmentsDiv.querySelector('.alert-info');
        const existingTable = activeAlignmentsDiv.querySelector('.table-responsive');

        if (existingTable) {
            existingTable.remove();
        }

        if (runningAlignments.length === 0) {
            // Show "no alignments" message if there are none
            if (!noAlignmentsAlert) {
                const alertDiv = document.createElement('div');
                alertDiv.className = 'alert alert-info';
                alertDiv.textContent = 'No alignments are currently running.';
                activeAlignmentsDiv.appendChild(alertDiv);
            }
            return;
        }

        // Remove "no alignments" message if it exists
        if (noAlignmentsAlert) {
            noAlignmentsAlert.remove();
        }

        // Create table
        const tableResponsive = document.createElement('div');
        tableResponsive.className = 'table-responsive';

        const alignmentTable = document.createElement('table');
        alignmentTable.className = 'table table-sm';

        alignmentTable.innerHTML = `
            <thead>
                <tr>
                    <th>FASTQ Name</th>
                    <th>Demand ID</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${runningAlignments.map(sample => `
                    <tr>
                        <td>${sample.fastq_name}</td>
                        <td>${sample.demand_id || 'Pending...'}</td>
                        <td><span class="badge bg-info">${sample.status || 'Running'}</span></td>
                    </tr>
                `).join('')}
            </tbody>
        `;

        tableResponsive.appendChild(alignmentTable);
        activeAlignmentsDiv.appendChild(tableResponsive);
    }

    // Helper method to clear all stored data
    clearStoredData() {
        try {
            console.log('Clearing stored data');

            // Remove data from localStorage (both keys)
            localStorage.removeItem(this.storageKey);
            localStorage.removeItem(this.legacyStorageKey);

            // Reset the selectedSamples array
            this.selectedSamples = [];

            // Get the sample table body
            const tableBody = document.querySelector('#samples-table tbody');
            if (tableBody) {
                // Clear all rows from the table
                tableBody.innerHTML = '';

                // Add a message row to indicate empty table
                const emptyRow = document.createElement('tr');
                emptyRow.className = 'text-center text-muted';
                emptyRow.innerHTML = `
                    <td colspan="8" class="py-4">
                        <i class="bi bi-inbox-fill me-2" style="font-size: 1.5rem;"></i>
                        <p>No samples selected. Use the Sample Browser to select samples.</p>
                        <a href="/" class="btn btn-sm btn-outline-primary mt-2">
                            <i class="bi bi-table me-1"></i>Go to Sample Browser
                        </a>
                    </td>
                `;
                tableBody.appendChild(emptyRow);

                // Uncheck the "select all" checkbox
                const selectAllCheckbox = document.getElementById('select-all-samples');
                if (selectAllCheckbox) {
                    selectAllCheckbox.checked = false;
                }

                // Disable the submit button
                const submitBtn = document.getElementById('submit-selected');
                if (submitBtn) {
                    submitBtn.disabled = true;
                }

                // Update the selected count display
                const selectedCount = document.getElementById('selected-count');
                if (selectedCount) {
                    selectedCount.textContent = '0 samples selected';
                }

                // Show a feedback message
                this.showClearConfirmation();
            } else {
                console.error('Table body not found when trying to clear selection');
            }

            // Update active alignments to show no running alignments
            const activeAlignmentsDiv = document.querySelector('.active-alignments');
            if (activeAlignmentsDiv) {
                // Clear current alignments table if it exists
                const existingTable = activeAlignmentsDiv.querySelector('.table-responsive');
                if (existingTable) {
                    existingTable.remove();
                }

                // Add "no alignments" message if it doesn't exist
                const noAlignmentsAlert = activeAlignmentsDiv.querySelector('.alert-info');
                if (!noAlignmentsAlert) {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = 'alert alert-info';
                    alertDiv.textContent = 'No alignments are currently running.';
                    activeAlignmentsDiv.appendChild(alertDiv);
                }
            }

            console.log('Data cleared successfully');
            return true;
        } catch (error) {
            console.error('Error clearing stored data:', error);
            return false;
        }
    }

    // Show a confirmation message after clearing
    showClearConfirmation() {
        // Create the alert element
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-success alert-dismissible fade show';
        alertDiv.setAttribute('role', 'alert');
        alertDiv.innerHTML = `
            <i class="bi bi-check-circle-fill me-2"></i>
            All samples have been cleared.
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;

        // Find a container to insert the alert
        const container = document.querySelector('.container-fluid');
        if (container) {
            // Insert at the top of the container
            container.insertBefore(alertDiv, container.firstChild);

            // Auto-dismiss after 3 seconds
            setTimeout(() => {
                try {
                    const bsAlert = new bootstrap.Alert(alertDiv);
                    bsAlert.close();
                } catch (err) {
                    // Fallback if bootstrap Alert API fails
                    if (alertDiv.parentNode) {
                        alertDiv.parentNode.removeChild(alertDiv);
                    }
                }
            }, 3000);
        }
    }

    // Reinitialize to make sure we get the latest data from localStorage
    reinitialize() {
        console.log('Reinitializing PipelineLocalData to check for updated localStorage data');
        // Explicitly check localStorage again
        const legacyData = localStorage.getItem(this.legacyStorageKey);

        if (legacyData) {
            console.log('Found legacy data during reinitialization:', legacyData);
            try {
                // Parse the JSON data
                const parsedData = JSON.parse(legacyData);
                console.log('Parsed legacy data in reinitialize:', parsedData);

                // Check if it's wrapped with timestamp and samples
                if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData) && parsedData.samples) {
                    console.log('Found samples object with timestamp, extracting samples array');

                    // Get the samples array
                    const samplesArray = parsedData.samples;
                    console.log('Sample array from legacy data:', samplesArray);

                    if (samplesArray && Array.isArray(samplesArray) && samplesArray.length > 0) {
                        // This will hold our processed samples
                        const processedSamples = samplesArray.map(sample => {
                            // Fix field mapping issues:
                            // In data from sample browser:
                            // - ingestStatus contains the organism name
                            // - organism contains the sample ID number
                            return {
                                fastq_name: sample.name || sample.id || '',
                                batch_name: sample.batchName || '',
                                // Fix field mixup - ingestStatus contains organism
                                organism: sample.ingestStatus || 'Unknown',
                                library_prep: sample.libraryPrep || '',
                                // Always set to 'Completed' for samples from browser
                                ingest_status: 'Completed',
                                alignment_status: 'Not Started',
                                postqc_status: 'Not Started'
                            };
                        });

                        console.log('Processed samples with fixed field mapping:', processedSamples);

                        // Update the selected samples
                        this.selectedSamples = processedSamples;

                        // Store with primary key
                        localStorage.setItem(this.storageKey, JSON.stringify(this.selectedSamples));
                        console.log('Saved normalized samples to primary key');

                        // Rebuild the table with the new data
                        this.rebuildSamplesTable();

                        return true;  // Successfully processed samples
                    }
                }
            } catch (e) {
                console.error('Error processing legacy data in reinitialize:', e);
            }
        } else {
            console.log('No legacy data found during reinitialization');
        }

        return false;  // No processing occurred
    }
}

// Initialize the pipeline local data handler
console.log('Creating PipelineLocalData instance');
const pipelineLocalData = new PipelineLocalData();

// Make sure pipelineLocalData is accessible globally
window.pipelineLocalData = pipelineLocalData;

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PipelineLocalData, pipelineLocalData };
}

// Add a self-check after initialization
console.log('Pipeline data initialized, checking global availability:',
    typeof window.pipelineLocalData !== 'undefined' ? 'AVAILABLE' : 'NOT AVAILABLE'); 