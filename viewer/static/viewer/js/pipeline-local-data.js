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
        this.selectedSamples = new Set();
        this.init();

        // Log constructor completion
        console.log('PipelineLocalData constructor complete');
    }

    // Create a reusable function to show bottom toast notifications
    showToastNotification(message, type = 'success', duration = 1500) {
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'position-fixed bottom-0 start-50 translate-middle-x p-3';
            toastContainer.style.zIndex = '11'; // Above most content
            document.body.appendChild(toastContainer);
        }

        // Create the toast element
        const toastDiv = document.createElement('div');
        toastDiv.className = `toast align-items-center text-white bg-${type} border-0`;
        toastDiv.setAttribute('role', 'alert');
        toastDiv.setAttribute('aria-live', 'assertive');
        toastDiv.setAttribute('aria-atomic', 'true');

        // Set inner HTML for toast
        toastDiv.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-funnel-fill me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        // Add to container
        toastContainer.appendChild(toastDiv);

        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toastDiv, { delay: duration });
        bsToast.show();

        // Remove after hiding
        toastDiv.addEventListener('hidden.bs.toast', () => {
            if (toastDiv.parentNode) {
                toastDiv.parentNode.removeChild(toastDiv);
            }
        });
    }

    init() {
        // Initialize the selected samples from local storage
        this.selectedSamples = this.getStoredSamples();

        // Track pagination state
        this.currentPage = 1;
        this.itemsPerPage = 25;

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
            });
        } else {
            console.log('Clear button not found!');
        }

        // Setup pagination go-to form handler
        const gotoPageForm = document.getElementById('gotoPageForm');
        if (gotoPageForm) {
            gotoPageForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const pageInput = document.getElementById('gotoPage');
                if (pageInput) {
                    const pageValue = parseInt(pageInput.value, 10);
                    const maxPage = parseInt(pageInput.getAttribute('max'), 10) || 1;

                    // Ensure the page number is within valid range
                    if (pageValue > 0 && pageValue <= maxPage) {
                        // Go to the requested page
                        this.goToPage(pageValue);
                    } else {
                        // Show error for invalid page number
                        this.showToastNotification(`Page must be between 1 and ${maxPage}`, 'danger');

                        // Reset to a valid value
                        pageInput.value = Math.min(Math.max(1, pageValue), maxPage);
                    }
                }
            });
        }

        // Setup pagination navigation buttons
        const pageNavLinks = document.querySelectorAll('.pagination-navigation a, .pagination-navigation button:not(.disabled)');
        pageNavLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                if (link.classList.contains('disabled')) return;

                let targetPage = 1;
                if (link.getAttribute('href')) {
                    // Extract page number from href
                    const href = link.getAttribute('href');
                    const pageMatch = href.match(/[?&]page=(\d+)/);
                    if (pageMatch && pageMatch[1]) {
                        targetPage = parseInt(pageMatch[1], 10);
                    }
                } else if (link.getAttribute('data-page')) {
                    // Get page from data attribute
                    targetPage = parseInt(link.getAttribute('data-page'), 10);
                }

                this.goToPage(targetPage);
            });
        });

        // Setup rows per page dropdown
        const rowsPerPageLinks = document.querySelectorAll('.pagination-dropdown .dropdown-item');
        rowsPerPageLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const perPage = parseInt(link.textContent.trim(), 10);
                if (!isNaN(perPage)) {
                    this.changeRowsPerPage(perPage);
                }
            });
        });

        // Rebuild the table on page load
        this.rebuildSamplesTable();

        // Sample checkbox change handler
        document.addEventListener('change', (event) => {
            if (event.target.matches('.sample-select')) {
                this.handleSampleCheckboxChange(event);
                this.updateSubmitButtonState();
            }
        });

        // Select all checkbox change handler
        const selectAllCheckbox = document.getElementById('select-all-samples');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (event) => {
                this.handleSelectAllChange(event);
                this.updateSubmitButtonState();
            });
        }

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
                    study_set: row.querySelector('td:nth-child(3)').textContent.trim(),
                    load_name: row.querySelector('td:nth-child(4)').textContent.trim(),
                    batch_name_from_vendor: row.querySelector('td:nth-child(5)').textContent.trim(),
                    organism_common_name: row.querySelector('td:nth-child(6)').textContent.trim(),
                    library_prep: row.querySelector('td:nth-child(7)').textContent.trim(),
                    ingest_status: row.querySelector('td:nth-child(8)').textContent.trim(),
                    alignment_status: row.querySelector('td:nth-child(9)').textContent.trim(),
                    postqc_status: row.querySelector('td:nth-child(10)').textContent.trim()
                });
            }
        });

        this.selectedSamples = samples;
        this.storeSamples();
    }

    // Utility method to merge samples with duplicate detection
    mergeSamplesWithDuplicateDetection(existingSamples, newSamples) {
        if (!newSamples || newSamples.length === 0) {
            return {
                combinedSamples: existingSamples,
                added: 0,
                duplicates: 0
            };
        }

        // Create a map of existing samples by ID for quick lookup during deduplication
        const existingSampleMap = new Map();
        existingSamples.forEach(sample => {
            const key = (sample.id || sample.fastq_name || sample.name || '').toLowerCase();
            if (key) existingSampleMap.set(key, sample);
        });

        // Add new samples, avoiding duplicates
        let duplicateCount = 0;
        let addedCount = 0;
        const combinedSamples = [...existingSamples]; // Create a new array with existing samples

        newSamples.forEach(newSample => {
            // Generate possible ID keys for duplicate detection
            const idKeys = [
                (newSample.id || '').toLowerCase(),
                (newSample.fastq_name || '').toLowerCase(),
                (newSample.name || '').toLowerCase()
            ].filter(key => key); // Remove empty keys

            // Check if this sample is a duplicate
            let isDuplicate = false;
            for (const key of idKeys) {
                if (existingSampleMap.has(key)) {
                    isDuplicate = true;
                    duplicateCount++;
                    console.log(`Skipping duplicate sample: ${key}`);
                    break;
                }
            }

            // If not a duplicate, add to the combined list
            if (!isDuplicate) {
                combinedSamples.push(newSample);
                // Also add to the map to detect duplicates within the new samples
                idKeys.forEach(key => existingSampleMap.set(key, newSample));
                addedCount++;
            }
        });

        return {
            combinedSamples,
            added: addedCount,
            duplicates: duplicateCount
        };
    }

    getStoredSamples() {
        try {
            console.log('getStoredSamples called');
            let allSamples = [];

            // First try with our primary key
            const storedData = localStorage.getItem(this.storageKey);
            if (storedData) {
                console.log(`Found data using primary key: ${this.storageKey}`);

                // Log the raw data before parsing
                console.log('RAW PRIMARY STORAGE DATA:', storedData);

                const parsedData = JSON.parse(storedData);

                // Log the parsed data structure
                console.log('PARSED PRIMARY STORAGE DATA:', parsedData);

                allSamples = this.normalizeStoredSamples(parsedData);
                console.log(`Loaded ${allSamples.length} samples from primary storage`);
            }

            // Check the legacy key from main_list.html
            const legacyStoredData = localStorage.getItem(this.legacyStorageKey);
            if (legacyStoredData) {
                console.log(`Found data using legacy key: ${this.legacyStorageKey}`);

                // Parse the JSON data
                try {
                    const parsedData = JSON.parse(legacyStoredData);
                    console.log('Parsed legacy data:', parsedData);

                    // Check various possible formats
                    let samplesToNormalize = [];

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

                    // Normalize the legacy samples
                    if (samplesToNormalize && samplesToNormalize.length > 0) {
                        console.log(`Normalizing ${samplesToNormalize.length} legacy samples`);
                        const normalizedLegacySamples = this.normalizeStoredSamples(samplesToNormalize);

                        // Merge the samples with duplicate detection
                        if (allSamples.length > 0) {
                            const mergeResult = this.mergeSamplesWithDuplicateDetection(allSamples, normalizedLegacySamples);
                            allSamples = mergeResult.combinedSamples;

                            console.log(`Combined initial samples: ${allSamples.length} total (${mergeResult.added} added, ${mergeResult.duplicates} duplicates skipped)`);
                        } else {
                            // No existing samples, just use the legacy ones
                            allSamples = normalizedLegacySamples;
                            console.log(`Using ${allSamples.length} legacy samples as initial set`);
                        }

                        // Store the combined samples with our primary key for future use
                        localStorage.setItem(this.storageKey, JSON.stringify(allSamples));
                        console.log(`Saved ${allSamples.length} initial combined samples to primary key`);

                        // Clear the legacy storage after successfully transferring data to primary storage
                        localStorage.removeItem(this.legacyStorageKey);
                        console.log(`Cleared legacy storage key ${this.legacyStorageKey} after successful processing`);
                    }
                } catch (parseError) {
                    console.error('Error parsing legacy data:', parseError);
                }
            }

            if (allSamples.length === 0) {
                console.log('No local data found in either storage key');
            }
            return allSamples;
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

        // Debug: Log original sample fields before normalization
        if (samples.length > 0) {
            console.log('DEBUG - Original sample field structure:', {
                sample: samples[0],
                fields: Object.keys(samples[0])
            });
        }

        return samples.map(sample => {
            // Create a new normalized sample object with exactly the fields we want
            const normalizedSample = {
                fastq_name: '',
                study_set: '',
                load_name: '',
                batch_name_from_vendor: '',
                organism_common_name: '',
                library_prep: '',
                ingest_status: '',
                alignment_status: '',
                postqc_status: ''
            };

            // Map fields exactly according to specified mappings
            // Fastq Name - only map from fastq_name
            if (sample.fastq_name) normalizedSample.fastq_name = sample.fastq_name;

            // Study Set - map from study_set or studySet
            if (sample.study_set) normalizedSample.study_set = sample.study_set;
            else if (sample.studySet) normalizedSample.study_set = sample.studySet;

            // Load Name - map from load_name or loadName
            if (sample.load_name) normalizedSample.load_name = sample.load_name;
            else if (sample.loadName) normalizedSample.load_name = sample.loadName;

            // Batch Name From Vendor - map from batch_name_from_vendor or batchNameFromVendor
            if (sample.batch_name_from_vendor) normalizedSample.batch_name_from_vendor = sample.batch_name_from_vendor;
            else if (sample.batchNameFromVendor) normalizedSample.batch_name_from_vendor = sample.batchNameFromVendor;

            // Organism Common Name - only map from organism_common_name
            if (sample.organism_common_name) normalizedSample.organism_common_name = sample.organism_common_name;

            // Library Prep Method - map from library_prep or libraryPrep
            if (sample.library_prep) normalizedSample.library_prep = sample.library_prep;
            else if (sample.libraryPrep) normalizedSample.library_prep = sample.libraryPrep;

            // Ingest Status - map from ingest_status or ingestStatus
            if (sample.ingest_status) normalizedSample.ingest_status = sample.ingest_status;
            else if (sample.ingestStatus) normalizedSample.ingest_status = sample.ingestStatus;

            // Alignment Status - map from alignment_status or alignmentStatus
            if (sample.alignment_status) normalizedSample.alignment_status = sample.alignment_status;
            else if (sample.alignmentStatus) normalizedSample.alignment_status = sample.alignmentStatus;

            // PostQC Status - map from postqc_status or postqcStatus
            if (sample.postqc_status) normalizedSample.postqc_status = sample.postqc_status;
            else if (sample.postqcStatus) normalizedSample.postqc_status = sample.postqcStatus;

            return normalizedSample;
        });
    }

    storeSamples() {
        try {
            // Ensure all required fields are present in each sample
            const samplesToStore = this.selectedSamples.map(sample => ({
                fastq_name: sample.fastq_name || '',
                study_set: sample.study_set || '',
                load_name: sample.load_name || '',
                batch_name_from_vendor: sample.batch_name_from_vendor || '',
                organism_common_name: sample.organism_common_name || '',
                library_prep: sample.library_prep || '',
                ingest_status: sample.ingest_status || '',
                alignment_status: sample.alignment_status || '',
                postqc_status: sample.postqc_status || ''
            }));

            localStorage.setItem(this.storageKey, JSON.stringify(samplesToStore));
            console.log(`Stored ${samplesToStore.length} samples in localStorage`);
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

    formatStatus(status) {
        // If status is empty, a dash, NA, or Not Completed, return "Not Started"
        if (!status || status === '—' || status === '-' || status === 'NA' || status.trim() === '' ||
            status.toLowerCase().trim() === 'not completed') {
            return 'Not Started';
        }

        // Handle other status cases
        status = status.toLowerCase().trim();
        if (status === 'completed' || status === 'complete') {
            return 'Completed';
        } else if (status.includes('in progress') || status === 'running') {
            return 'In Progress';
        } else if (status.includes('pending') || status === 'submitted' || status === 'queued') {
            return 'Pending';
        } else if (status.includes('error') || status.includes('fail') || status.includes('killed')) {
            return status.charAt(0).toUpperCase() + status.slice(1); // Capitalize first letter
        }

        // For any other status, return it with first letter capitalized
        return status.charAt(0).toUpperCase() + status.slice(1);
    }

    formatStatusWithBadge(status) {
        const formattedStatus = this.formatStatus(status);
        let badgeClass = 'bg-secondary'; // Default badge style

        // Determine badge class based on status
        switch (formattedStatus.toLowerCase()) {
            case 'completed':
                badgeClass = 'bg-success';
                break;
            case 'in progress':
                badgeClass = 'bg-warning';
                break;
            case 'pending':
            case 'submitted':
            case 'queued':
                badgeClass = 'bg-info';
                break;
            case 'not started':
                badgeClass = 'bg-secondary';
                break;
            case 'error':
            case 'failed':
            case 'killed':
                badgeClass = 'bg-danger';
                break;
        }

        return `<span class="badge ${badgeClass}">${formattedStatus}</span>`;
    }

    updateSubmitButtonState() {
        const submitButton = document.getElementById('submit-selected');
        if (submitButton) {
            const selectedSamples = document.querySelectorAll('.sample-select:checked');
            submitButton.disabled = selectedSamples.length === 0;
        }
    }

    rebuildSamplesTable() {
        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) {
            console.warn('Table body not found');
            return;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        // Get stored samples
        const samples = this.getStoredSamples();
        console.log('Rebuilding table with samples:', samples);

        if (!samples || samples.length === 0) {
            // Add a "no samples" message row
            const messageRow = document.createElement('tr');
            messageRow.innerHTML = `
                <td colspan="9" class="text-center text-muted py-4">
                    <i class="bi bi-info-circle me-2"></i>
                    No samples selected. Select samples from the main page to view them here.
                </td>
            `;
            tableBody.appendChild(messageRow);

            // Update pagination info to show 0 results
            const paginationInfo = document.querySelector('.pagination-info');
            if (paginationInfo) {
                paginationInfo.textContent = `Results 0-0 of 0`;
            }

            // Update goto page input max value
            const gotoPageInput = document.getElementById('gotoPage');
            if (gotoPageInput) {
                gotoPageInput.max = 1;
                gotoPageInput.value = 1;
            }

            return;
        }

        // Pagination settings
        const itemsPerPage = this.itemsPerPage;
        const currentPage = this.currentPage;
        const startIndex = (currentPage - 1) * itemsPerPage;
        const endIndex = Math.min(startIndex + itemsPerPage, samples.length);
        const totalPages = Math.ceil(samples.length / itemsPerPage);

        // Update pagination info
        const paginationInfo = document.querySelector('.pagination-info');
        if (paginationInfo) {
            paginationInfo.textContent = `Results ${startIndex + 1}-${endIndex} of ${samples.length}`;
        }

        // Update goto page input max value
        const gotoPageInput = document.getElementById('gotoPage');
        if (gotoPageInput) {
            gotoPageInput.max = totalPages;
            gotoPageInput.value = currentPage;
        }

        // Update current page indicator and pagination buttons
        this.updatePaginationUI();

        // Build rows for each sample in the current page
        const currentPageSamples = samples.slice(startIndex, endIndex);
        currentPageSamples.forEach(sample => {
            const row = document.createElement('tr');
            row.setAttribute('data-fastq', sample.fastq_name || '');

            row.innerHTML = `
                <td>
                    <input type="checkbox" class="sample-select">
                </td>
                <td>${sample.fastq_name || ''}</td>
                <td>${sample.study_set || ''}</td>
                <td>${sample.load_name || ''}</td>
                <td>${sample.batch_name_from_vendor || ''}</td>
                <td>${sample.organism_common_name || ''}</td>
                <td>${sample.library_prep || ''}</td>
                <td>${this.formatStatusWithBadge(sample.ingest_status)}</td>
                <td>${this.formatStatusWithBadge(sample.alignment_status)}</td>
                <td>${this.formatStatusWithBadge(sample.postqc_status)}</td>
            `;

            tableBody.appendChild(row);
        });

        // Reattach event listeners
        this.setupSelectionListeners();

        // Update submit button state
        this.updateSubmitButtonState();
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
                    <td colspan="9" class="py-4">
                        <i class="bi bi-x-circle me-2" style="font-size: 1.5rem;"></i>
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
        // Show a toast notification at the bottom of the screen with blue background
        this.showToastNotification('Clearing filters...', 'primary', 1500);
    }

    // Reinitialize to make sure we get the latest data from localStorage
    reinitialize() {
        console.log('Reinitializing PipelineLocalData to check for updated localStorage data');

        // Get existing samples from primary storage
        let existingSamples = [];
        const existingData = localStorage.getItem(this.storageKey);
        if (existingData) {
            try {
                existingSamples = JSON.parse(existingData);
                console.log(`Found ${existingSamples.length} existing samples in primary storage`);
            } catch (e) {
                console.error('Error parsing existing data:', e);
                existingSamples = [];
            }
        }

        // Check for new samples in legacy storage
        const legacyData = localStorage.getItem(this.legacyStorageKey);
        if (!legacyData) {
            console.log('No legacy data found during reinitialization');
            return false;  // No processing occurred
        }

        console.log('Found legacy data during reinitialization:', legacyData);
        try {
            // Parse the JSON data
            const parsedData = JSON.parse(legacyData);
            console.log('Parsed legacy data in reinitialize:', parsedData);

            // Extract samples array from various possible formats
            let newSamples = [];

            // Format 1: {timestamp, samples} from multiselect-filters.js
            if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData) && parsedData.samples) {
                console.log('Found samples object with timestamp, extracting samples array');
                newSamples = parsedData.samples;
            }
            // Format 2: Direct array of samples
            else if (Array.isArray(parsedData)) {
                console.log('Found data as direct array of samples');
                newSamples = parsedData;
            }
            // Format 3: Single sample object
            else if (parsedData && typeof parsedData === 'object' && !Array.isArray(parsedData)) {
                console.log('Found data as single sample object, wrapping in array');
                newSamples = [parsedData];
            }

            if (!newSamples || newSamples.length === 0) {
                console.log('No valid samples found in legacy data');
                // Clear legacy data even if there are no samples to prevent repeated processing
                localStorage.removeItem(this.legacyStorageKey);
                console.log(`Cleared empty legacy storage key ${this.legacyStorageKey}`);
                return false;
            }

            console.log(`Found ${newSamples.length} new samples in legacy data:`, newSamples);

            // Use the normalizeStoredSamples method for consistent field mapping
            const processedNewSamples = this.normalizeStoredSamples(newSamples);
            console.log('Processed new samples with fixed field mapping:', processedNewSamples);

            // Merge the samples with duplicate detection
            const mergeResult = this.mergeSamplesWithDuplicateDetection(existingSamples, processedNewSamples);
            this.selectedSamples = mergeResult.combinedSamples;

            console.log(`Combined samples: ${this.selectedSamples.length} total (${mergeResult.added} added, ${mergeResult.duplicates} duplicates skipped)`);

            // Store the combined set in primary key
            localStorage.setItem(this.storageKey, JSON.stringify(this.selectedSamples));
            console.log(`Saved accumulated samples to primary key: ${this.selectedSamples.length} samples`);

            // Clear the legacy storage after successfully transferring data to primary storage
            localStorage.removeItem(this.legacyStorageKey);
            console.log(`Cleared legacy storage key ${this.legacyStorageKey} after successful processing`);

            // Rebuild the table with the combined data
            this.rebuildSamplesTable();

            return true;  // Successfully processed samples
        } catch (e) {
            console.error('Error processing legacy data in reinitialize:', e);
        }

        return false;  // No processing occurred
    }

    handleSampleCheckboxChange(event) {
        const checkbox = event.target;
        const row = checkbox.closest('tr');
        if (row) {
            // Update the select all checkbox state
            const selectAllCheckbox = document.getElementById('select-all-samples');
            if (selectAllCheckbox) {
                const allCheckboxes = document.querySelectorAll('.sample-select');
                const allChecked = Array.from(allCheckboxes).every(cb => cb.checked);
                selectAllCheckbox.checked = allChecked;
            }
            // Update selected samples
            this.updateSelectedSamples();
        }
    }

    handleSelectAllChange(event) {
        const selectAllCheckbox = event.target;
        const sampleCheckboxes = document.querySelectorAll('.sample-select');
        sampleCheckboxes.forEach(checkbox => {
            checkbox.checked = selectAllCheckbox.checked;
        });
        // Update selected samples
        this.updateSelectedSamples();
    }

    populateTableManually(samples) {
        if (!samples || !samples.length) return;

        console.log('Raw samples data to display:', samples);

        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) {
            console.error('Table body not found');
            return;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        // Add the samples
        samples.forEach(sample => {
            const row = document.createElement('tr');

            // Use the sample ID/name for the data-fastq attribute
            row.dataset.fastq = sample.fastqName || sample.id;

            // Field mapping
            const sampleName = sample.fastqName || sample.id || '';
            const studySet = sample.studySet || '';
            const loadName = sample.loadName || '';
            const batchNameFromVendor = sample.batchNameFromVendor || sample.batch_name_from_vendor || '';
            const organismCommonName = sample.organismCommon || '';
            const libraryPrepMethod = sample.libraryPrepMethod || '';
            const ingestStatus = sample.ingestStatus || '';
            const alignmentStatus = sample.alignmentStatus || '';
            const postqcStatus = sample.postqcStatus || '';

            // Create the HTML content with correct field mapping
            row.innerHTML = `
                <td><input type="checkbox" class="sample-select" checked></td>
                <td>${sampleName}</td>
                <td>${studySet}</td>
                <td>${loadName}</td>
                <td>${batchNameFromVendor}</td>
                <td>${organismCommonName}</td>
                <td>${libraryPrepMethod}</td>
                <td>${ingestStatus}</td>
                <td>${alignmentStatus}</td>
                <td>${postqcStatus}</td>
            `;

            tableBody.appendChild(row);
        });

        // Update pagination info
        const paginationInfo = document.querySelector('.pagination-info');
        if (paginationInfo) {
            paginationInfo.textContent = `Results 1-${samples.length} of ${samples.length}`;
        }

        // Update goto page input max value
        const totalPages = Math.ceil(samples.length / 25); // Using 25 as default page size
        const gotoPageInput = document.getElementById('gotoPage');
        if (gotoPageInput) {
            gotoPageInput.max = totalPages > 0 ? totalPages : 1;
            gotoPageInput.value = 1;
        }

        // Enable submit button
        const submitBtn = document.getElementById('submit-selected');
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    }

    // Go to specific page
    goToPage(pageNumber) {
        const samples = this.getStoredSamples();
        if (!samples || samples.length === 0) return;

        const totalPages = Math.ceil(samples.length / this.itemsPerPage);

        // Validate page number
        pageNumber = Math.min(Math.max(1, pageNumber), totalPages);
        this.currentPage = pageNumber;

        // Update pagination UI
        this.updatePaginationUI();

        // Rebuild table with current page
        this.rebuildSamplesTable();

        // Update URL without reloading page
        const url = new URL(window.location);
        url.searchParams.set('page', pageNumber);
        window.history.pushState({}, '', url);
    }

    // Change number of rows per page
    changeRowsPerPage(perPage) {
        // Verify perPage is a number and reasonable
        if (isNaN(perPage) || perPage < 1) perPage = 25;

        this.itemsPerPage = perPage;
        this.currentPage = 1; // Reset to first page

        // Update dropdown button text
        const dropdownBtn = document.getElementById('rowsPerPageDropdown');
        if (dropdownBtn) {
            dropdownBtn.textContent = perPage;
        }

        // Update the active class in dropdown
        const perPageLinks = document.querySelectorAll('.pagination-dropdown .dropdown-item');
        perPageLinks.forEach(link => {
            if (parseInt(link.textContent.trim(), 10) === perPage) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Update pagination UI and table
        this.updatePaginationUI();
        this.rebuildSamplesTable();
    }

    // Update pagination UI elements
    updatePaginationUI() {
        const samples = this.getStoredSamples();
        if (!samples) return;

        const totalPages = Math.ceil(samples.length / this.itemsPerPage);
        const currentPage = this.currentPage;

        // Update current page display
        const currentPageSpan = document.querySelector('.current-page');
        if (currentPageSpan) {
            currentPageSpan.textContent = currentPage;
        }

        // Update total pages display
        const totalPagesSpan = document.querySelector('.total-pages');
        if (totalPagesSpan) {
            totalPagesSpan.textContent = totalPages;
        }

        // Enable/disable previous page buttons
        const prevButtons = document.querySelectorAll('.pagination-navigation a[title="Previous page"], .pagination-navigation a[title="First page"]');
        prevButtons.forEach(btn => {
            if (currentPage <= 1) {
                btn.classList.add('disabled');
                btn.setAttribute('aria-disabled', 'true');
            } else {
                btn.classList.remove('disabled');
                btn.setAttribute('aria-disabled', 'false');
            }
        });

        // Enable/disable next page buttons
        const nextButtons = document.querySelectorAll('.pagination-navigation a[title="Next page"], .pagination-navigation a[title="Last page"]');
        nextButtons.forEach(btn => {
            if (currentPage >= totalPages) {
                btn.classList.add('disabled');
                btn.setAttribute('aria-disabled', 'true');
            } else {
                btn.classList.remove('disabled');
                btn.setAttribute('aria-disabled', 'false');
            }
        });

        // Update goto page input
        const gotoPageInput = document.getElementById('gotoPage');
        if (gotoPageInput) {
            gotoPageInput.value = currentPage;
            gotoPageInput.max = totalPages;
        }
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