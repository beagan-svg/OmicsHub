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
    constructor() {
        this.storageKey = 'pipelineSelectedSamples';
        this.legacyStorageKey = 'selectedSamplesForPipeline';
        this.selectedSamples = [];
        this.itemsPerPage = 25;
        this.currentPage = 1;
        this.init();
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
                container.style.zIndex = '11';
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

    init() {
        // Initialize data and UI
        this.loadSamples();
        this.initializePagination();

        // Set up event listeners when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this._initializeAfterDOM());
        } else {
            this._initializeAfterDOM();
        }
    }

    _initializeAfterDOM() {
        this.setupEventListeners();
        this.reinitialize();
    }

    loadSamples() {
        try {
            // Load primary storage
            const storedData = localStorage.getItem(this.storageKey);
            let primarySamples = storedData ? JSON.parse(storedData) : [];

            // Load and merge legacy storage if it exists
            const legacyData = localStorage.getItem(this.legacyStorageKey);
            if (legacyData) {
                try {
                    const parsedData = JSON.parse(legacyData);

                    // Process legacy data to match current format
                    let legacySamples = [];
                    if (Array.isArray(parsedData)) {
                        legacySamples = this._convertLegacySamples(parsedData);
                    } else if (parsedData?.samples) {
                        legacySamples = this._convertLegacySamples(parsedData.samples);
                    } else if (parsedData && typeof parsedData === 'object') {
                        legacySamples = this._convertLegacySamples([parsedData]);
                    }

                    // Merge samples without duplicates
                    const existingSamplesMap = new Map(primarySamples.map(s => [s.fastq_name, true]));
                    this.selectedSamples = [
                        ...primarySamples,
                        ...legacySamples.filter(s => !existingSamplesMap.has(s.fastq_name))
                    ];

                    // Save merged samples and remove legacy data
                    this.saveSamples();
                    localStorage.removeItem(this.legacyStorageKey);
                } catch (parseError) {
                    console.error('Legacy data parse error:', parseError);
                    this.selectedSamples = primarySamples;
                }
            } else {
                this.selectedSamples = primarySamples;
            }
        } catch (error) {
            console.error('Sample loading error:', error);
            this.selectedSamples = [];
        }
    }

    // Convert legacy samples to current format
    _convertLegacySamples(samples) {
        return samples.map(sample => ({
            fastq_name: sample.fastq_name || sample.name || sample.id || '',
            study_set: sample.study_set || sample.studySet || '',
            load_name: sample.load_name || sample.loadName || '',
            batch_name_from_vendor: sample.batch_name_from_vendor || sample.batchName || '',
            organism_common_name: sample.organism_common_name || sample.organism || sample.ingestStatus || 'Unknown',
            library_prep_method: sample.library_prep_method || sample.libraryPrep || '',
            ingest_status: sample.ingest_status || 'Completed',
            alignment_status: sample.alignment_status || 'Not Started',
            postqc_status: sample.postqc_status || 'Not Started',
        }));
    }

    // Simplified reinitialize method
    reinitialize() {
        try {
            // Try to load from localStorage
            const storedData = localStorage.getItem(this.storageKey);
            if (storedData) {
                this.selectedSamples = JSON.parse(storedData);

                // Rebuild the table with the loaded samples
                this.rebuildSamplesTable();
                return true;
            }

            // Try legacy storage if primary storage is empty
            const legacyData = localStorage.getItem(this.legacyStorageKey);
            if (legacyData) {
                try {
                    const parsedData = JSON.parse(legacyData);
                    if (parsedData && parsedData.samples && Array.isArray(parsedData.samples)) {
                        this.selectedSamples = this._convertLegacySamples(parsedData.samples);
                        this.saveSamples();
                        localStorage.removeItem(this.legacyStorageKey);
                        this.rebuildSamplesTable();
                        return true;
                    }
                } catch (e) {
                    console.error('Error processing legacy data:', e);
                }
            }

            return false;
        } catch (error) {
            console.error('Error reinitializing pipeline data:', error);
            return false;
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
            console.error('Save error:', error);
            if (error.name === 'QuotaExceededError' || error.code === 22) {
                this._handleStorageFullError();
            }
        }
    }

    // Handle localStorage quota exceeded errors
    _handleStorageFullError() {
        try {
            // Attempt to clear any legacy data
            localStorage.removeItem(this.legacyStorageKey);

            // Reduce the data by keeping only essential fields
            const minimalSamples = this.selectedSamples.map(sample => ({
                fastq_name: sample.fastq_name,
                study_set: sample.study_set,
                load_name: sample.load_name,
                batch_name_from_vendor: sample.batch_name_from_vendor,
                ingest_status: sample.ingest_status
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

    setupEventListeners() {
        // Set up main event listeners
        this.setupSelectionListeners();
        this.setupPaginationListeners();
        this.setupModalHandlers();
        this.setupActionButtons();

        // Rebuild the table initially
        this.rebuildSamplesTable();
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
        // Submit button handling
        const submitActionBtn = document.getElementById('submit-action-btn');
        if (submitActionBtn) {
            submitActionBtn.addEventListener('click', () => {
                this.showToastNotification('Submitting selected samples...', 'info');
                const submitModal = new bootstrap.Modal(document.getElementById('submit-modal'));
                submitModal.show();
            });
        }

        // Show submit modal with sample list
        const submitSelectedBtn = document.getElementById('submit-selected');
        if (submitSelectedBtn) {
            submitSelectedBtn.addEventListener('click', () => {
                const selectedRows = document.querySelectorAll('.sample-select:checked');
                const sampleList = document.getElementById('submit-sample-list');

                if (sampleList) {
                    // Clear previous list
                    sampleList.innerHTML = '';

                    // Add selected samples to the list
                    selectedRows.forEach(checkbox => {
                        const row = checkbox.closest('tr');
                        const fastqName = row.querySelector('td:nth-child(2)').textContent;
                        const batchName = row.querySelector('td:nth-child(3)').textContent;

                        const li = document.createElement('li');
                        li.innerHTML = `<strong>${fastqName}</strong> (${batchName})`;
                        sampleList.appendChild(li);
                    });

                    const submitModal = new bootstrap.Modal(document.getElementById('submit-modal'));
                    submitModal.show();
                }
            });
        }

        // Add modal cleanup handlers
        document.querySelectorAll('.modal').forEach(modalEl => {
            modalEl.addEventListener('hidden.bs.modal', function () {
                // Remove any lingering backdrops
                const backdrops = document.querySelectorAll('.modal-backdrop');
                backdrops.forEach(backdrop => backdrop.remove());
                // Remove modal-open class from body
                document.body.classList.remove('modal-open');
                // Remove inline styles from body
                document.body.style.removeProperty('padding-right');
                document.body.style.removeProperty('overflow');
            });
        });
    }

    setupActionButtons() {
        // Submit button
        const submitBtn = document.getElementById('confirm-submit');
        if (submitBtn) {
            submitBtn.addEventListener('click', (e) => this.handleSampleSubmission(e));
        }

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

    clearAtacSamples() {
        // Get all rows in the table for visible UI updates
        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) return;

        // Track removed samples for reporting
        let removedCount = 0;

        // Filter out ATAC samples from selectedSamples
        const originalLength = this.selectedSamples.length;
        this.selectedSamples = this.selectedSamples.filter(sample => {
            const isAtac = sample.batch_name_from_vendor &&
                (sample.batch_name_from_vendor.toUpperCase().startsWith('ATX') ||
                    sample.batch_name_from_vendor.toUpperCase().includes('ATAC'));
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

    updateSubmitButtonState() {
        const submitButton = document.getElementById('submit-selected');
        const actionSubmitButton = document.getElementById('submit-action-btn');
        const selectedSamples = document.querySelectorAll('.sample-select:checked');
        const isDisabled = selectedSamples.length === 0;

        if (submitButton) submitButton.disabled = isDisabled;
        if (actionSubmitButton) actionSubmitButton.disabled = isDisabled;
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

            // Filter out the selected samples from storage
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

    rebuildSamplesTable() {
        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody) return;

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
        const statusBadgeCache = this._createStatusBadgeCache();

        currentPageSamples.forEach(sample =>
            fragment.appendChild(this._createTableRow(sample, statusBadgeCache))
        );

        // Add to DOM and setup listeners
        tableBody.appendChild(fragment);
        this.setupSelectionListeners();
        this.updateSubmitButtonState();
    }

    _createStatusBadgeCache() {
        return {
            'Completed': '<span class="badge bg-success">Completed</span>',
            'In Progress': '<span class="badge bg-warning">In Progress</span>',
            'Not Started': '<span class="badge bg-secondary">Not Started</span>',
            'Pending': '<span class="badge bg-info">Pending</span>',
            'Error': '<span class="badge bg-danger">Error</span>',
            'Failed': '<span class="badge bg-danger">Failed</span>'
        };
    }

    _createTableRow(sample, statusBadgeCache) {
        const row = document.createElement('tr');
        row.setAttribute('data-fastq', sample.fastq_name || '');

        // Get badge HTML from cache or create it
        const ingestBadge = statusBadgeCache[this.formatStatus(sample.ingest_status)] ||
            this.formatStatusWithBadge(sample.ingest_status);
        const alignmentBadge = statusBadgeCache[this.formatStatus(sample.alignment_status)] ||
            this.formatStatusWithBadge(sample.alignment_status);
        const postqcBadge = statusBadgeCache[this.formatStatus(sample.postqc_status)] ||
            this.formatStatusWithBadge(sample.postqc_status);

        row.innerHTML = `
            <td><input type="checkbox" class="sample-select"></td>
            <td>${sample.fastq_name || ''}</td>
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

    formatStatusWithBadge(status) {
        // Format the status text
        let formattedStatus = 'Not Started';

        if (status) {
            status = status.toLowerCase().trim();

            if (['—', '-', 'na', '', 'not completed'].includes(status)) {
                formattedStatus = 'Not Started';
            } else if (['completed', 'complete'].includes(status)) {
                formattedStatus = 'Completed';
            } else if (status.includes('in progress') || status === 'running') {
                formattedStatus = 'In Progress';
            } else if (status.includes('pending') || status === 'submitted' || status === 'queued') {
                formattedStatus = 'Pending';
            } else if (status.includes('error') || status.includes('fail') || status.includes('killed')) {
                formattedStatus = status.charAt(0).toUpperCase() + status.slice(1);
            } else {
                formattedStatus = status.charAt(0).toUpperCase() + status.slice(1);
            }
        }

        // Determine badge class
        let badgeClass = 'bg-secondary';
        switch (formattedStatus.toLowerCase()) {
            case 'completed': badgeClass = 'bg-success'; break;
            case 'in progress': badgeClass = 'bg-warning'; break;
            case 'pending':
            case 'submitted':
            case 'queued': badgeClass = 'bg-info'; break;
            case 'not started': badgeClass = 'bg-secondary'; break;
            case 'error':
            case 'failed':
            case 'killed': badgeClass = 'bg-danger'; break;
        }

        return `<span class="badge ${badgeClass}">${formattedStatus}</span>`;
    }

    // Keep a separate formatStatus method that returns just the text for use in logic
    formatStatus(status) {
        if (!status || status === '—' || status === '-' || status === 'NA' ||
            status.trim() === '' || status.toLowerCase().trim() === 'not completed') {
            return 'Not Started';
        }

        status = status.toLowerCase().trim();
        if (status === 'completed' || status === 'complete') {
            return 'Completed';
        } else if (status.includes('in progress') || status === 'running') {
            return 'In Progress';
        } else if (status.includes('pending') || status === 'submitted' || status === 'queued') {
            return 'Pending';
        } else if (status.includes('error') || status.includes('fail') || status.includes('killed')) {
            return status.charAt(0).toUpperCase() + status.slice(1);
        }

        return status.charAt(0).toUpperCase() + status.slice(1);
    }

    handleSampleSubmission(event) {
        event.preventDefault();

        if (!this.selectedSamples || this.selectedSamples.length === 0) {
            this.showToastNotification('No samples selected for submission', 'danger');
            return;
        }

        // Check for samples with pending ingest
        const pendingIngest = this.selectedSamples.filter(sample =>
            sample.ingest_status !== 'Completed'
        );

        // Populate modal
        this.populateSubmitModal(pendingIngest);

        // Setup submit handler
        const confirmSubmitBtn = document.getElementById('confirm-submit');
        const forceSubmitCheckbox = document.getElementById('include-incomplete-samples');

        if (confirmSubmitBtn) {
            confirmSubmitBtn.disabled = this.selectedSamples.length === 0;
            confirmSubmitBtn.onclick = () => {
                // Get force submit option
                const forceSubmit = forceSubmitCheckbox && forceSubmitCheckbox.checked;

                // Submit samples
                this.submitSamplesToAlignment(this.selectedSamples, forceSubmit);

                // Close modal
                const modal = bootstrap.Modal.getInstance(document.getElementById('submit-modal'));
                if (modal) modal.hide();
            };
        }
    }

    populateSubmitModal(pendingIngest) {
        const sampleList = document.getElementById('submit-sample-list');
        if (sampleList) {
            sampleList.innerHTML = '';

            // Group samples by ingest status
            const completedSamples = this.selectedSamples.filter(sample =>
                sample.ingest_status === 'Completed'
            );

            // Add completed samples
            if (completedSamples.length > 0) {
                this.addSampleGroupToModal(sampleList, completedSamples, 'Ready for Submission:', 'bg-success', 'Ready');
            }

            // Add pending ingest samples
            if (pendingIngest.length > 0) {
                this.addSampleGroupToModal(sampleList, pendingIngest, 'Not Ready (Ingest Incomplete):', 'bg-warning', 'Pending Ingest');

                // Show warning about pending ingest samples
                const warningDiv = document.createElement('div');
                warningDiv.className = 'alert alert-warning mt-3';
                warningDiv.innerHTML = `
                    <small>
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${pendingIngest.length} sample${pendingIngest.length !== 1 ? 's' : ''} have not completed ingest. 
                        These samples will be skipped unless you force submission.
                    </small>
                `;
                sampleList.appendChild(warningDiv);

                // Show incomplete samples warning
                const incompleteWarning = document.getElementById('incomplete-samples-warning');
                if (incompleteWarning) {
                    incompleteWarning.classList.remove('d-none');

                    // Populate incomplete samples list
                    const incompleteList = document.getElementById('incomplete-samples-list');
                    if (incompleteList) {
                        incompleteList.innerHTML = '';
                        pendingIngest.slice(0, 5).forEach(sample => {
                            const li = document.createElement('li');
                            li.textContent = sample.fastq_name;
                            incompleteList.appendChild(li);
                        });

                        if (pendingIngest.length > 5) {
                            const li = document.createElement('li');
                            li.textContent = `...and ${pendingIngest.length - 5} more`;
                            incompleteList.appendChild(li);
                        }
                    }
                }
            } else {
                // Hide incomplete samples warning
                const incompleteWarning = document.getElementById('incomplete-samples-warning');
                if (incompleteWarning) {
                    incompleteWarning.classList.add('d-none');
                }
            }
        }
    }

    addSampleGroupToModal(container, samples, headerText, badgeClass, badgeText) {
        const header = document.createElement('h6');
        header.className = 'mt-3 mb-2';
        header.innerHTML = headerText;
        container.appendChild(header);

        samples.forEach(sample => {
            const li = document.createElement('li');
            li.className = 'd-flex justify-content-between align-items-center mb-1';
            li.innerHTML = `
                <div>
                    <strong>${sample.fastq_name}</strong>
                    <span class="ms-2 badge ${badgeClass}">${badgeText}</span>
                </div>
                <small class="text-muted">${this.determineWorkflow(sample.batch_name_from_vendor)}</small>
            `;
            container.appendChild(li);
        });
    }

    submitSamplesToAlignment(samples, forceSubmit = false) {
        this.showToastNotification('Submitting samples for processing...', 'info', 3000);

        fetch('/api/pipeline/submit-alignment/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ samples, force_submit: forceSubmit })
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success' || data.status === 'warning') {
                    // Handle successfully submitted samples
                    if (data.submitted_samples && Array.isArray(data.submitted_samples)) {
                        this.removeSubmittedSamples(data.submitted_samples);
                    }

                    // Show success/warning notification
                    this.showToastNotification(
                        data.message,
                        data.status === 'warning' ? 'warning' : 'success',
                        5000
                    );

                    // Redirect to jobs page or rebuild table
                    if (this.selectedSamples.length === 0) {
                        setTimeout(() => window.location.href = '/pipeline/jobs/', 2000);
                    } else {
                        this.rebuildSamplesTable();
                        this.updateSubmitButtonState();
                    }
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger', 5000);
                }
            })
            .catch(error => {
                console.error('Error submitting samples:', error);
                this.showToastNotification('Error submitting samples for alignment', 'danger', 5000);
            });
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

    determineWorkflow(batchName) {
        if (!batchName) return 'RTX';

        const batchNameUpper = batchName.toUpperCase();

        if (batchNameUpper.startsWith('MTX') || batchNameUpper.includes('ATX')) {
            return 'MTX';
        }

        return 'RTX'; // Default for RTX prefix or any unrecognized pattern
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
}

// Initialize and export
const pipelineLocalData = new PipelineLocalData();
window.pipelineLocalData = pipelineLocalData;