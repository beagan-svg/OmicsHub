/**
 * pipeline-local-data.js
 * Handles local storage of selected samples and rebuilding the pipeline table
 */

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

class PipelineLocalData {
    // ============================
    // Initialization Methods
    // ============================

    constructor() {
        this.storageKey = 'pipelineSelectedSamples';
        this.selectedSamples = [];
        this.itemsPerPage = 25;
        this.currentPage = 1;
        this.init();
    }

    init() {

        // Add modern Pipeline Checkout class to body for enhanced styling
        document.body.classList.add('modern-pipeline-checkout');

        // Status badges are styled solely by components.css (no injected styles).

        // Load data from localStorage
        this.loadSamples();

        // Set up pagination settings
        this.initializePagination();

        // Set up event listeners
        this.setupEventListenersOnly();

        // Set up submit functionality
        this.initializeSubmitFunctionality();

        // Display the data in the table
        this.rebuildSamplesTable();

    }

    /**
     * Status badges are styled solely by components.css (the design system).
     * The previous injected <style> block was removed so there is one source of
     * truth for badge appearance. Kept as a no-op for any external callers.
     */
    addStatusBadgeStyles() { /* badges styled by components.css */ }

    reinitialize() {

        try {
            // Try to load from localStorage
            const storedData = localStorage.getItem(this.storageKey);

            if (storedData) {
                let newSamples;
                try {
                    newSamples = JSON.parse(storedData);
                } catch (parseError) {
                    console.error('[PipelineLocalData] JSON parse error:', parseError);
                    return false;
                }

                // Check if this is actually new data by comparing with current data
                const currentDataString = JSON.stringify(this.selectedSamples);
                const newDataString = JSON.stringify(newSamples);

                if (currentDataString === newDataString) {
                    return false;
                }

                // Store the count before merge for comparison
                const beforeCount = this.selectedSamples?.length || 0;

                // If we have existing samples, merge; otherwise just load directly
                if (beforeCount > 0) {
                    this.mergeSamples(newSamples);
                } else {
                    this.selectedSamples = newSamples;
                }

                const afterCount = this.selectedSamples?.length || 0;
                const addedCount = afterCount - beforeCount;

                if (addedCount > 0) {
                } else if (afterCount !== beforeCount) {
                }

                // Rebuild the table with the updated samples
                this.rebuildSamplesTable();

                return true;
            } else {
                return false;
            }
        } catch (error) {
            console.error('[PipelineLocalData] Error reinitializing:', error);
            return false;
        }
    }

    // Helper method to merge samples without duplicates
    mergeSamples(newSamples) {

        if (!newSamples || !Array.isArray(newSamples) || newSamples.length === 0) {
            return;
        }

        // Ensure selectedSamples is initialized
        if (!this.selectedSamples) {
            this.selectedSamples = [];
        }

        // Track existing fastq names to avoid duplicates
        const existingFastqNames = new Set(this.selectedSamples.map(sample => {
            const fastqName = sample.fastq_name || sample.fastq || sample.fastq_id;
            return fastqName;
        }));

        let addedCount = 0;
        let skippedCount = 0;

        // Add only non-duplicate samples
        newSamples.forEach((newSample, index) => {
            try {
                // Extract fastq name using multiple possible field names
                const fastqName = newSample.fastq_name || newSample.fastq || newSample.fastq_id;

                if (!fastqName) {
                    console.warn(`[PipelineLocalData] Sample ${index} missing fastq identifier`);
                    return;
                }

                if (!existingFastqNames.has(fastqName)) {
                    // Normalize the sample data structure to ensure consistency
                    const normalizedSample = {
                        fastq_name: fastqName,
                        study_set: newSample.study_set || newSample.studySet || '',
                        load_name: newSample.load_name || newSample.loadName || '',
                        batch_name_from_vendor: newSample.batch_name_from_vendor || newSample.batchNameFromVendor || newSample.batch_name || '',
                        organism_common_name: newSample.organism_common_name || newSample.organismCommonName || newSample.organism || '',
                        library_prep_method: newSample.library_prep_method || newSample.libraryPrepMethod || newSample.library_prep || '',
                        ingest_status: newSample.ingest_status || newSample.ingestStatus || 'Not Started',
                        alignment_status: newSample.alignment_status || newSample.alignmentStatus || 'Not Started',
                        postqc_status: newSample.postqc_status || newSample.postqcStatus || 'Not Started'
                    };

                    this.selectedSamples.push(normalizedSample);
                    existingFastqNames.add(fastqName);
                    addedCount++;
                } else {
                    skippedCount++;
                }
            } catch (sampleError) {
                console.error(`[PipelineLocalData] Error processing sample ${index}:`, sampleError);
            }
        });


        // Save the merged samples
        this.saveSamples();
    }

    initializePagination() {
        const dropdownBtn = document.getElementById('rowsPerPageDropdown');
        if (dropdownBtn) {
            this.itemsPerPage = parseInt(dropdownBtn.textContent.trim()) || 25;
        }

        const currentPageSpan = document.querySelector('.current-page');
        if (currentPageSpan) {
            this.currentPage = parseInt(currentPageSpan.textContent.trim()) || 1;
        }
    }

    // ============================
    // Data Storage and Retrieval
    // ============================

    // Load samples from localStorage
    loadSamples() {
        try {
            const storedData = localStorage.getItem(this.storageKey);

            // Initialize empty array if needed
            if (!this.selectedSamples) {
                this.selectedSamples = [];
            }

            // Load data directly from localStorage (browser already merged it)
            if (storedData) {
                try {
                    const samples = JSON.parse(storedData);
                    if (Array.isArray(samples) && samples.length > 0) {
                        this.selectedSamples = samples;
                    } else {
                        this.selectedSamples = [];
                    }
                } catch (parseError) {
                    console.error('[PipelineLocalData] Error parsing data:', parseError);
                    this.selectedSamples = [];
                }
            } else {
                this.selectedSamples = [];
            }

        } catch (error) {
            console.error('[PipelineLocalData] Load error:', error);
            this.selectedSamples = [];
        }
    }

    saveSamples() {
        try {
            const currentData = localStorage.getItem(this.storageKey);
            const newData = JSON.stringify(this.selectedSamples);

            if (!currentData || currentData !== newData) {
                localStorage.setItem(this.storageKey, newData);
            }

        } catch (error) {
            console.error('[PipelineLocalData] Save error:', error);

            if (error.name === 'QuotaExceededError' || error.code === 22) {
                this._handleStorageFullError();
            }
        }
    }

    // Handle localStorage quota exceeded errors
    _handleStorageFullError() {
        try {
            // Reduce the data by keeping only essential fields
            // Ensure we keep the same field names as the rest of the application
            const minimalSamples = this.selectedSamples.map(sample => ({
                fastq_name: sample.fastq_name,
                study_set: sample.study_set,
                load_name: sample.load_name,
                batch_name_from_vendor: sample.batch_name_from_vendor,
                organism_common_name: sample.organism_common_name,
                ingest_status: sample.ingest_status,
            }));

            // Try to save the minimal data
            localStorage.setItem(this.storageKey, JSON.stringify(minimalSamples));

            // Show warning to user
            this.showToastNotification(
                'Warning: Storage limit reached. Some sample data may be truncated.',
                'warning',
                5000
            );
        } catch (error) {
            console.error('Failed to save even minimal data:', error);
            this.showToastNotification(
                'Error: Unable to save selected samples due to browser storage limits.',
                'danger',
                5000
            );
        }
    }

    clearStoredData() {
        try {
            const tableBody = document.querySelector('#samples-table tbody');
            if (!tableBody) return false;

            // Get selected samples
            const selectedCheckboxes = tableBody.querySelectorAll('.sample-select:checked');
            const selectedFastqNames = new Set();

            // Collect fastq names of selected samples
            selectedCheckboxes.forEach(checkbox => {
                const row = checkbox.closest('tr');
                if (row) {
                    const fastqName = row.querySelector('td:nth-child(2)').textContent.trim();
                    selectedFastqNames.add(fastqName);
                }
            });

            // Filter out the selected samples from storage using consistent field name
            this.selectedSamples = this.selectedSamples.filter(sample =>
                !selectedFastqNames.has(sample.fastq_name)
            );

            // Save to localStorage
            this.saveSamples();

            // Rebuild the table
            this.rebuildSamplesTable();

            // Update UI state
            const selectAllCheckbox = document.getElementById('select-all-samples');
            if (selectAllCheckbox) {
                selectAllCheckbox.checked = false;
            }

            const selectedCount = document.getElementById('selected-count');
            if (selectedCount) {
                selectedCount.textContent = '0 samples selected';
            }

            const submitBtn = document.getElementById('submit-selected');
            if (submitBtn) {
                submitBtn.disabled = true;
            }

            return true;
        } catch (error) {
            console.error('Error clearing selected samples:', error);
            return false;
        }
    }

    // Create a reusable function to show bottom toast notifications
    showToastNotification(message, type = 'success', duration = 2000) {
        // Remove any existing toasts
        document.querySelectorAll('.toast').forEach(toast => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        });

        // Create toast container if needed
        let toastContainer = document.getElementById('toast-container') ||
            (() => {
                const container = document.createElement('div');
                container.id = 'toast-container';
                container.className = 'position-fixed bottom-0 start-50 translate-middle-x p-3';
                document.body.appendChild(container);
                return container;
            })();

        // Create toast element
        const toastDiv = document.createElement('div');
        toastDiv.className = 'toast align-items-center text-white border-0';
        toastDiv.style.cssText = 'background-color: #1976D2; max-width: 250px; min-width: 180px; width: fit-content;';
        toastDiv.setAttribute('role', 'alert');
        toastDiv.setAttribute('aria-live', 'assertive');
        toastDiv.setAttribute('aria-atomic', 'true');
        toastDiv.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-stars me-2" style="animation: sparkle 1.5s infinite ease-in-out;"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        // Add to container and show
        toastContainer.appendChild(toastDiv);
        const bsToast = new bootstrap.Toast(toastDiv, { delay: duration, animation: true });
        bsToast.show();

        // Auto-remove on hide
        toastDiv.addEventListener('hidden.bs.toast', () => {
            if (toastDiv.parentNode) toastDiv.parentNode.removeChild(toastDiv);
        });

        // Define sparkle animation if needed
        if (!document.querySelector('style#sparkle-animation')) {
            const styleEl = document.createElement('style');
            styleEl.id = 'sparkle-animation';
            styleEl.textContent = `
                @keyframes sparkle {
                    0%, 100% { transform: scale(1) rotate(0deg); }
                    25% { transform: scale(1.2) rotate(-5deg); }
                    50% { transform: scale(1.1) rotate(5deg); }
                    75% { transform: scale(1.2) rotate(-3deg); }
                }
            `;
            document.head.appendChild(styleEl);
        }
    }

    // ============================
    // UI Event Handling
    // ============================

    setupEventListeners() {
        // Set up main event listeners
        this.setupSelectionListeners();
        this.setupPaginationListeners();
        this.setupModalHandlers();
        this.setupActionButtons();

        // Rebuild the table initially
        this.rebuildSamplesTable();
    }

    setupEventListenersOnly() {
        // Set up main event listeners without rebuilding table
        this.setupSelectionListeners();
        this.setupPaginationListeners();
        this.setupModalHandlers();
        this.setupActionButtons();
    }

    setupSelectionListeners() {
        // Handle individual sample selection
        document.addEventListener('change', (event) => {
            if (event.target.matches('.sample-select')) {
                this.updateSelectedSamples();
                this.updateSubmitButtonState();

                // Show toast only when checking a sample
                if (event.target.checked) {
                    const count = document.querySelectorAll('.sample-select:checked').length;
                    this.showToastNotification(`${count} sample${count !== 1 ? 's' : ''} selected`, 'info', 750);
                }
            }
        });

        // Handle select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-samples');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (event) => {
                this.handleSelectAllChange(event);

                // Show toast notification only when selecting all
                if (event.target.checked) {
                    const count = document.querySelectorAll('.sample-select').length;
                    this.showToastNotification(`Selecting all ${count} samples...`, 'info', 750);
                }
            });
        }
    }

    setupPaginationListeners() {
        // Helper functions for pagination
        const getCurrentPerPage = () => {
            const dropdownBtn = document.getElementById('rowsPerPageDropdown');
            return dropdownBtn ? parseInt(dropdownBtn.textContent.trim()) : 25;
        };

        const getPageUrl = (pageNum) => {
            const url = new URL(window.location.href);
            url.searchParams.set('page', pageNum);
            url.searchParams.set('per_page', getCurrentPerPage());
            return url.toString();
        };

        // Navigation button handlers
        const paginationNav = document.querySelector('.pagination-navigation');
        if (paginationNav) {
            // First page button
            paginationNav.querySelector('a[title="First page"]')?.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.href = getPageUrl(1);
            });

            // Previous page button
            paginationNav.querySelector('a[title="Previous page"]')?.addEventListener('click', (e) => {
                e.preventDefault();
                const currentPage = parseInt(document.querySelector('.current-page').textContent);
                if (currentPage > 1) window.location.href = getPageUrl(currentPage - 1);
            });

            // Next page button
            paginationNav.querySelector('a[title="Next page"]')?.addEventListener('click', (e) => {
                e.preventDefault();
                const currentPage = parseInt(document.querySelector('.current-page').textContent);
                const totalPages = parseInt(document.querySelector('.total-pages').textContent);
                if (currentPage < totalPages) window.location.href = getPageUrl(currentPage + 1);
            });

            // Last page button
            paginationNav.querySelector('a[title="Last page"]')?.addEventListener('click', (e) => {
                e.preventDefault();
                const totalPages = parseInt(document.querySelector('.total-pages').textContent);
                window.location.href = getPageUrl(totalPages);
            });
        }

        // Go to page form
        document.getElementById('gotoPageForm')?.addEventListener('submit', (e) => {
            e.preventDefault();
            const pageInput = document.getElementById('gotoPage');
            if (pageInput) {
                const pageValue = parseInt(pageInput.value, 10);
                const maxPage = parseInt(pageInput.getAttribute('max'), 10) || 1;

                if (pageValue > 0 && pageValue <= maxPage) {
                    window.location.href = getPageUrl(pageValue);
                } else {
                    this.showToastNotification(`Page must be between 1 and ${maxPage}`, 'danger');
                    pageInput.value = Math.min(Math.max(1, pageValue), maxPage);
                }
            }
        });

        // Rows per page dropdown
        document.querySelectorAll('.pagination-dropdown .dropdown-item').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const perPage = parseInt(link.textContent.trim(), 10);
                if (!isNaN(perPage)) {
                    const url = new URL(window.location.href);
                    url.searchParams.set('per_page', perPage);
                    url.searchParams.set('page', '1');
                    window.location.href = url.toString();
                }
            });
        });
    }

    setupModalHandlers() {

        // The new modal manager handles all modal cleanup automatically
        // We just need to listen for specific events if needed

        document.addEventListener('modalManagerReady', () => {
        });

    }

    setupActionButtons() {
        // Clear toggle
        const clearToggle = document.getElementById('clear-toggle');
        if (clearToggle) {
            clearToggle.addEventListener('change', () => {
                if (clearToggle.checked) {
                    this.showToastNotification('Clearing selections...', 'info', 1000);
                    this.clearStoredData();
                    setTimeout(() => {
                        clearToggle.checked = false;
                    }, 500);
                }
            });
        }

        // Clear ATAC toggle
        const clearAtacToggle = document.getElementById('clear-atac-toggle');
        if (clearAtacToggle) {
            clearAtacToggle.addEventListener('change', () => {
                if (clearAtacToggle.checked) {
                    this.showToastNotification('Clearing ATAC samples...', 'info', 1250);
                    this.clearAtacSamples();
                    setTimeout(() => {
                        clearAtacToggle.checked = false;
                    }, 500);
                }
            });
        }

        // Clear selection button
        const clearBtn = document.getElementById('clear-selection');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearStoredData());
        }
    }

    handleSelectAllChange(event) {
        const selectAllCheckbox = document.getElementById('select-all-samples');
        const isChecked = selectAllCheckbox.checked;

        // Toggle all visible checkboxes
        const checkboxes = document.querySelectorAll('.sample-select');
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });

        // Create hidden rows for samples not on current page when checking all
        if (isChecked) {
            this.selectedSamples.forEach(sample => {
                // Find if there's a row for this sample on the current page
                const existingRow = document.querySelector(`tr[data-fastq="${sample.fastq_name}"]`);
                if (!existingRow) {
                    // If the sample isn't on the current page, create a hidden row for it
                    const hiddenRow = document.createElement('tr');
                    hiddenRow.style.display = 'none';
                    hiddenRow.setAttribute('data-fastq', sample.fastq_name);
                    hiddenRow.innerHTML = `
                        <td>
                            <input type="checkbox" class="sample-select" checked>
                        </td>
                        <td>${sample.fastq_name}</td>
                        <td>${sample.study_set}</td>
                        <td>${sample.load_name}</td>
                        <td>${sample.batch_name_from_vendor}</td>
                        <td>${sample.organism_common_name}</td>
                        <td>${sample.library_prep_method}</td>
                        <td>${sample.ingest_status}</td>
                        <td>${sample.alignment_status}</td>
                        <td>${sample.postqc_status}</td>
                    `;
                    document.querySelector('#samples-table tbody').appendChild(hiddenRow);
                }
            });
        }

        // Update selected samples and UI
        this.updateSelectedSamples();
        this.updateSubmitButtonState();
    }

    updateSubmitButtonState() {
        const submitButton = document.getElementById('submit-selected');
        const actionSubmitButton = document.getElementById('submit-action-btn');
        const selectedSamples = document.querySelectorAll('.sample-select:checked');
        const isDisabled = selectedSamples.length === 0;

        if (submitButton) submitButton.disabled = isDisabled;
        if (actionSubmitButton) actionSubmitButton.disabled = isDisabled;
    }

    // ============================
    // Sample Data Management
    // ============================

    updateSelectedSamples() {
        const selectedRows = document.querySelectorAll('.sample-select:checked');
        const selectedFastqNames = new Set();

        // Get the fastq names of currently selected samples
        selectedRows.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                const fastqCell = row.querySelector('td:nth-child(2)');
                if (fastqCell) {
                    const fastqName = fastqCell.textContent.trim();
                    selectedFastqNames.add(fastqName);
                }
            }
        });

        // Keep only samples that are still selected in the UI
        this.selectedSamples = this.selectedSamples.filter(sample =>
            !selectedFastqNames.has(sample.fastq_name)
        );

        // Add newly selected samples
        selectedRows.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (!row) return;

            try {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 10) {  // Make sure we have all required cells
                    // Create sample with all fields in our standardized format
                    const sample = {
                        fastq_name: cells[1]?.textContent?.trim() || '',
                        study_set: cells[2]?.textContent?.trim() || '',
                        load_name: cells[3]?.textContent?.trim() || '',
                        batch_name_from_vendor: cells[4]?.textContent?.trim() || '',
                        organism_common_name: cells[5]?.textContent?.trim() || '',
                        library_prep_method: cells[6]?.textContent?.trim() || '',
                        ingest_status: cells[7]?.textContent?.trim() || '',
                        alignment_status: cells[8]?.textContent?.trim() || '',
                        postqc_status: cells[9]?.textContent?.trim() || ''
                    };

                    // Only add if we have at least a fastq name
                    if (sample.fastq_name) {
                        this.selectedSamples.push(sample);
                    }
                }
            } catch (error) {
                console.error('Error processing row:', error);
            }
        });

        // Save to localStorage
        this.saveSamples();

        // Update the selected count display if it exists
        const selectedCount = document.getElementById('selected-count');
        if (selectedCount) {
            selectedCount.textContent = `${this.selectedSamples.length} samples selected`;
        }
    }

    clearAtacSamples() {
        // Get all rows in the table for visible UI updates
        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) return;

        // Track removed samples for reporting
        let removedCount = 0;

        // Filter out ATAC samples from selectedSamples
        const originalLength = this.selectedSamples.length;
        this.selectedSamples = this.selectedSamples.filter(sample => {
            // Use consistent snake_case field name
            const sampleBatchName = sample.batch_name_from_vendor;

            // Check if it's an ATAC sample by checking batch name
            const isAtac = sampleBatchName &&
                (sampleBatchName.toUpperCase().startsWith('ATX') ||
                    sampleBatchName.toUpperCase().includes('ATAC'));

            if (isAtac) {
                removedCount++;
            }
            return !isAtac;
        });

        // Save updated samples to localStorage
        this.saveSamples();

        // Update UI
        this.rebuildSamplesTable();

        // Show notification
        if (removedCount > 0) {
            this.showToastNotification(`Removed ${removedCount} ATAC samples`, 'success');
        } else {
            this.showToastNotification('No ATAC samples found to remove', 'info');
        }
    }

    removeSubmittedSamples(submittedSamples) {
        const submittedSet = new Set(submittedSamples.map(sample =>
            typeof sample === 'string' ? sample : sample.fastq_name
        ));

        this.selectedSamples = this.selectedSamples.filter(sample =>
            !submittedSet.has(sample.fastq_name)
        );

        this.saveSamples();

        const selectedCount = document.getElementById('selected-count');
        if (selectedCount) {
            selectedCount.textContent = `${this.selectedSamples.length} samples selected`;
        }
    }

    /**
     * Determine workflow from batch name
     */
    determineWorkflow(batchName) {
        if (!batchName) return null;

        const parts = batchName.split('-');
        if (!parts.length) return null;

        const prefix = parts[0].toUpperCase();

        if (prefix === 'MTX' || batchName.includes('ATX')) {
            return 'MTX';
        } else if (prefix === 'RTX') {
            return 'RTX';
        }

        return 'RTX'; // Default to RTX
    }

    // ============================
    // Table Rendering
    // ============================

    rebuildSamplesTable() {

        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) {
            console.error('[PipelineLocalData] Table body not found');
            return;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        // Handle empty state
        if (!this.selectedSamples || this.selectedSamples.length === 0) {
            this.showEmptyState(tableBody);
            return;
        }

        // Calculate pagination
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = Math.min(startIndex + this.itemsPerPage, this.selectedSamples.length);
        const totalPages = Math.ceil(this.selectedSamples.length / this.itemsPerPage);

        // Update pagination UI
        this.updatePaginationInfo(startIndex, endIndex, totalPages);

        // Build table rows
        const fragment = document.createDocumentFragment();
        const currentPageSamples = this.selectedSamples.slice(startIndex, endIndex);

        currentPageSamples.forEach((sample, index) => {
            try {
                const row = this._createTableRow(sample);
                fragment.appendChild(row);
            } catch (rowError) {
                console.error(`[PipelineLocalData] Error creating row ${index}:`, rowError);
            }
        });

        // Add to DOM and setup listeners
        tableBody.appendChild(fragment);
        this.setupSelectionListeners();
        this.updateSubmitButtonState();

    }

    _createTableRow(sample) {
        const row = document.createElement('tr');
        row.setAttribute('data-fastq', sample.fastq_name || '');

        // Shared status-badge markup (matches the SSR rows + status_badge.html)
        const ingestBadge = this.formatStatusWithBadge(sample.ingest_status);
        const alignmentBadge = this.formatStatusWithBadge(sample.alignment_status);
        const postqcBadge = this.formatStatusWithBadge(sample.postqc_status);

        row.innerHTML = `
            <td class="selection-column"><input type="checkbox" class="sample-select"></td>
            <td class="field-fastq_name">${sample.fastq_name || ''}</td>
            <td>${sample.study_set || ''}</td>
            <td>${sample.load_name || ''}</td>
            <td>${sample.batch_name_from_vendor || ''}</td>
            <td>${sample.organism_common_name || ''}</td>
            <td>${sample.library_prep_method || ''}</td>
            <td>${ingestBadge}</td>
            <td>${alignmentBadge}</td>
            <td>${postqcBadge}</td>
        `;

        return row;
    }

    showEmptyState(tableBody) {
        // Add empty state message
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `
                    <td colspan="10" class="text-center py-5">
                        <div class="d-flex flex-column align-items-center">
                            <div class="mb-3">
                                <i class="bi bi-x-circle" style="font-size: 2rem;"></i>
                            </div>
                            <p class="text-muted mb-4">No samples selected. Use the Sample Browser to select samples.</p>
                            <a href="/" class="btn btn-primary">
                                <i class="bi bi-table me-2"></i>GO TO SAMPLE BROWSER
                            </a>
                        </div>
                    </td>
                `;
        tableBody.appendChild(emptyRow);

        // Reset pagination info
        const paginationInfo = document.querySelector('.pagination-info');
        if (paginationInfo) {
            paginationInfo.textContent = 'Results 0-0 of 0';
        }

        // Update page indicators
        const currentPageSpan = document.querySelector('.current-page');
        if (currentPageSpan) {
            currentPageSpan.textContent = '0';
        }

        const totalPagesSpan = document.querySelector('.total-pages');
        if (totalPagesSpan) {
            totalPagesSpan.textContent = '0';
        }

        // Disable pagination
        document.querySelectorAll('.pagination-navigation a').forEach(btn => {
            btn.classList.add('disabled');
            btn.setAttribute('aria-disabled', 'true');
        });

        // Reset page input
        const gotoPageInput = document.getElementById('gotoPage');
        if (gotoPageInput) {
            gotoPageInput.max = 0;
            gotoPageInput.value = 0;
            gotoPageInput.disabled = true;
        }
    }

    updatePaginationInfo(startIndex, endIndex, totalPages) {
        // Update pagination text
        const paginationInfo = document.querySelector('.pagination-info');
        if (paginationInfo) {
            paginationInfo.textContent = `Results ${startIndex + 1}-${endIndex} of ${this.selectedSamples.length}`;
        }

        // Update page input
        const gotoPageInput = document.getElementById('gotoPage');
        if (gotoPageInput) {
            gotoPageInput.max = totalPages;
            gotoPageInput.value = this.currentPage;
            gotoPageInput.disabled = false;
        }

        // Update page indicators
        const currentPageSpan = document.querySelector('.current-page');
        if (currentPageSpan) {
            currentPageSpan.textContent = this.currentPage.toString();
        }

        const totalPagesSpan = document.querySelector('.total-pages');
        if (totalPagesSpan) {
            totalPagesSpan.textContent = totalPages.toString();
        }

        // Enable/disable navigation buttons
        const prevButtons = document.querySelectorAll('.pagination-navigation a[title="Previous page"], .pagination-navigation a[title="First page"]');
        prevButtons.forEach(btn => {
            if (this.currentPage <= 1) {
                btn.classList.add('disabled');
                btn.setAttribute('aria-disabled', 'true');
            } else {
                btn.classList.remove('disabled');
                btn.setAttribute('aria-disabled', 'false');
            }
        });

        const nextButtons = document.querySelectorAll('.pagination-navigation a[title="Next page"], .pagination-navigation a[title="Last page"]');
        nextButtons.forEach(btn => {
            if (this.currentPage >= totalPages) {
                btn.classList.add('disabled');
                btn.setAttribute('aria-disabled', 'true');
            } else {
                btn.classList.remove('disabled');
                btn.setAttribute('aria-disabled', 'false');
            }
        });
    }

    // ============================
    // Status Formatting
    // ============================

    /**
     * Format status with badge using OCS browser style
     */
    // Display badge for a processing status. Mirrors the shared
    // status_badge.html component (icon + label, shared .status-badge classes).
    // Unknown/empty -> NOT COMPLETED. Single mapping; this is the only place
    // Pipeline Checkout builds a status badge, so its re-render matches the SSR.
    formatStatusWithBadge(status) {
        const s = (status || '').toLowerCase().trim();
        let cls, icon, label;
        if (['completed', 'complete'].includes(s)) {
            cls = 'status-completed'; icon = 'bi-check-circle-fill'; label = 'COMPLETED';
        } else if (s.includes('in progress') || s === 'running') {
            cls = 'status-in-progress'; icon = 'bi-arrow-clockwise'; label = 'IN PROGRESS';
        } else if (s.includes('fail') || s.includes('error') || s.includes('killed')) {
            cls = 'status-failed'; icon = 'bi-x-circle-fill'; label = 'FAILED';
        } else if (s.includes('pending') || s === 'submitted' || s === 'queued') {
            cls = 'status-pending'; icon = 'bi-clock-fill'; label = 'PENDING';
        } else {
            cls = 'status-not-completed'; icon = 'bi-circle'; label = 'NOT COMPLETED';
        }
        return `<span class="status-badge ${cls}" title="${this.escapeHtml(status || 'Not Completed')}"><i class="bi ${icon}"></i><span class="status-text">${label}</span></span>`;
    }

    // Keep a separate formatStatus method that returns just the text for use in logic
    formatStatus(status) {
        if (!status || status === '—' || status === '-' || status === 'NA' ||
            status.trim() === '' || status.toLowerCase().trim() === 'not completed') {
            return 'NOT STARTED';
        }

        status = status.toLowerCase().trim();
        if (status === 'completed' || status === 'complete') {
            return 'COMPLETED';
        } else if (status.includes('in progress') || status === 'running') {
            return 'IN PROGRESS';
        } else if (status.includes('pending') || status === 'submitted' || status === 'queued') {
            return 'PENDING';
        } else if (status.includes('error') || status.includes('fail') || status.includes('killed')) {
            return status.toUpperCase();
        }

        return status.toUpperCase();
    }

    /**
     * HTML escape function
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    // ============================
    // Sample Submission (Pipeline Checkout)
    // ============================

    /**
     * Initialize submit button functionality
     */
    initializeSubmitFunctionality() {
        // Handle submit selected samples button click
        const submitActionBtn = document.getElementById('submit-action-btn');
        if (submitActionBtn) {
            submitActionBtn.addEventListener('click', () => {

                // Get only the checked samples from the table
                const selectedRows = document.querySelectorAll('.sample-select:checked');

                const selectedSamples = [];

                selectedRows.forEach((checkbox, index) => {
                    const row = checkbox.closest('tr');
                    if (row) {
                        const sample = {
                            fastq_name: row.querySelector('td:nth-child(2)')?.textContent?.trim() || '',
                            study_set: row.querySelector('td:nth-child(3)')?.textContent?.trim() || '',
                            load_name: row.querySelector('td:nth-child(4)')?.textContent?.trim() || '',
                            batch_name_from_vendor: row.querySelector('td:nth-child(5)')?.textContent?.trim() || '',
                            organism_common_name: row.querySelector('td:nth-child(6)')?.textContent?.trim() || '',
                            library_prep: row.querySelector('td:nth-child(7)')?.textContent?.trim() || '',
                            ingest_status: row.querySelector('td:nth-child(8)')?.textContent?.trim() || '',
                            alignment_status: row.querySelector('td:nth-child(9)')?.textContent?.trim() || '',
                            postqc_status: row.querySelector('td:nth-child(10)')?.textContent?.trim() || ''
                        };
                        selectedSamples.push(sample);
                    }
                });


                if (selectedSamples.length === 0) {
                    this.showToastNotification('Please select at least one sample', 'warning');
                    return;
                }

                // Prepare samples for submission
                this.prepareSubmissionModal(selectedSamples);
            });
        }
    }

    /**
     * Prepare submission modal with sample validation
     */
    prepareSubmissionModal(selectedSamples) {
        const modal = new bootstrap.Modal(document.getElementById('submit-modal'));
        const samplesList = document.getElementById('submit-sample-list');
        const incompleteWarning = document.getElementById('incomplete-samples-warning');
        const incompleteList = document.getElementById('incomplete-samples-list');
        const submitBtn = document.getElementById('confirm-submit');

        // Reset modal
        samplesList.innerHTML = '';
        incompleteList.innerHTML = '';
        incompleteWarning.classList.add('d-none');

        // Check each sample for ingest status
        const incompleteSamples = [];
        const validSamples = [];

        selectedSamples.forEach(sample => {
            const ingestStatus = sample.ingest_status || 'Not Started';
            const isComplete = ingestStatus === 'Completed';

            if (!isComplete) {
                incompleteSamples.push(sample);
            } else {
                validSamples.push(sample);
            }

            // Create row for sample
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${sample.fastq_name}</td>
                <td>${sample.load_name}</td>
                <td>${sample.batch_name_from_vendor}</td>
                <td>${this.determineWorkflow(sample.batch_name_from_vendor) || 'RTX (default)'}</td>
                <td>${sample.organism_common_name}</td>
                <td>${sample.library_prep}</td>
                <td><span class="badge ${isComplete ? 'bg-success' : 'bg-warning'}">${ingestStatus}</span></td>
                <td>${sample.alignment_status}</td>
                <td>${sample.postqc_status}</td>
            `;

            // Add color coding for incomplete samples
            if (!isComplete) {
                row.classList.add('table-warning');
            }

            samplesList.appendChild(row);
        });

        // Show warning if there are incomplete samples
        if (incompleteSamples.length > 0) {
            incompleteWarning.classList.remove('d-none');

            // Populate incomplete samples list
            incompleteSamples.forEach(sample => {
                const li = document.createElement('li');
                li.textContent = sample.fastq_name;
                incompleteList.appendChild(li);
            });
        }

        // Set up submit button handler
        submitBtn.onclick = () => {
            const includeIncomplete = document.getElementById('include-incomplete-samples')?.checked || false;
            const samplesToSubmit = includeIncomplete ? selectedSamples : validSamples;

            if (samplesToSubmit.length === 0) {
                this.showToastNotification('No valid samples to submit', 'warning');
                return;
            }

            this.submitSamples(samplesToSubmit);
        };

        // Show the modal
        modal.show();
    }

    /**
     * Submit samples to the API
     */
    submitSamples(samples) {

        const forceSubmit = document.getElementById('forceSubmitCheck')?.checked || false;
        const modal = bootstrap.Modal.getInstance(document.getElementById('submit-modal'));

        this.showToastNotification('Submitting samples...', 'info');
        modal.hide();

        // Call API to submit samples
        fetch('/api/pipeline/submit-samples/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({
                samples: samples.map(s => s.fastq_name),
                force_submit: forceSubmit
            })
        })
            .then(response => {
                return response.json();
            })
            .then(data => {

                if (data.status === 'success') {
                    this.showToastNotification(`Successfully submitted ${data.submitted_count} samples`, 'success');
                    if (data.skipped_count > 0) {
                        this.showToastNotification(`Skipped ${data.skipped_count} samples due to errors`, 'warning');
                    }

                    // Remove submitted samples from Pipeline Checkout
                    const submitted = new Set(data.submitted || []);
                    this.removeSubmittedSamples(Array.from(submitted));

                } else {
                    console.error('[PipelineLocalData] API error:', data.message);
                    this.showToastNotification(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('[PipelineLocalData] Submit error:', error);
                this.showToastNotification('Failed to submit samples', 'danger');
            });
    }

    /**
     * Get CSRF token for API requests
     */
    getCsrfToken() {
        return document.querySelector('input[name="csrfmiddlewaretoken"]')?.value || '';
    }

    // ============================
    // Sample Data Management
    // ============================

    /**
     * Show summary of samples by source and timestamp for debugging
     */
    showSamplesSummary() {

        if (!this.selectedSamples || this.selectedSamples.length === 0) {
            return;
        }


        // Group by source
        const bySource = {};
        const byTimestamp = {};

        this.selectedSamples.forEach(sample => {
            const source = sample.source || 'unknown';
            const timestamp = sample.timestamp || 'no-timestamp';

            if (!bySource[source]) bySource[source] = [];
            if (!byTimestamp[timestamp]) byTimestamp[timestamp] = [];

            bySource[source].push(sample);
            byTimestamp[timestamp].push(sample);
        });

        Object.entries(bySource).forEach(([source, samples]) => {
        });

        Object.entries(byTimestamp).forEach(([timestamp, samples]) => {
            const date = timestamp !== 'no-timestamp' ? new Date(parseInt(timestamp)).toLocaleString() : 'No timestamp';
        });

        this.selectedSamples.slice(0, 5).forEach((sample, index) => {
            const timestamp = sample.timestamp ? new Date(sample.timestamp).toLocaleString() : 'No timestamp';
        });

    }

    /**
     * Debug function to check current state - can be called from console
     */
    debugSummary() {



        if (this.selectedSamples && this.selectedSamples.length > 0) {
        }

        const storedData = localStorage.getItem(this.storageKey);

        if (storedData) {
            try {
                const parsed = JSON.parse(storedData);
            } catch (e) {
            }
        }

        const tableBody = document.querySelector('#samples-table tbody');

        const submitBtn = document.getElementById('submit-action-btn');

        const legacyData = localStorage.getItem('selectedSamplesForPipeline');


        return {
            storageKey: this.storageKey,
            samplesCount: this.selectedSamples?.length || 0,
            tableRows: tableBody?.children?.length || 0,
            checkedBoxes: document.querySelectorAll('.sample-select:checked').length,
            hasStorageData: !!storedData,
            submitButtonDisabled: submitBtn?.disabled
        };
    }
}

// Initialize and export
const pipelineLocalData = new PipelineLocalData();
window.pipelineLocalData = pipelineLocalData;

// Make debug function available globally for console debugging
window.debugPipelineData = () => {
    if (window.pipelineLocalData && typeof window.pipelineLocalData.debugSummary === 'function') {
        return window.pipelineLocalData.debugSummary();
    } else {
        console.error('PipelineLocalData not available or debugSummary method missing');
        return null;
    }
};

// Make samples summary function available globally
window.showSamplesSummary = () => {
    if (window.pipelineLocalData && typeof window.pipelineLocalData.showSamplesSummary === 'function') {
        return window.pipelineLocalData.showSamplesSummary();
    } else {
        console.error('PipelineLocalData not available or showSamplesSummary method missing');
        return null;
    }
};

