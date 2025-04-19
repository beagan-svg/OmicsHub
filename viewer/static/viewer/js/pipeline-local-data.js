/**
 * pipeline-local-data.js
 * Handles local storage of selected samples and rebuilding the pipeline table
 */

// Add immediate debugging to see if script is loaded
console.log('pipeline-local-data.js is being loaded');

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
        // Remove any existing toasts to prevent duplicates
        const existingToasts = document.querySelectorAll('.toast');
        existingToasts.forEach(toast => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        });

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
        toastDiv.className = 'toast align-items-center text-white border-0';
        toastDiv.style.backgroundColor = '#1976D2'; // Use consistent blue background
        toastDiv.setAttribute('role', 'alert');
        toastDiv.setAttribute('aria-live', 'assertive');
        toastDiv.setAttribute('aria-atomic', 'true');

        // Set inner HTML for toast with sparkle icon
        toastDiv.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi bi-stars me-2" style="animation: sparkle 1.5s infinite ease-in-out;"></i>
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

        // Define sparkle animation if it doesn't exist
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
            document.addEventListener('DOMContentLoaded', () => {
                this.setupEventListeners();
                this.reinitialize();
            });
        } else {
            this.setupEventListeners();
            this.reinitialize();
        }
    }

    loadSamples() {
        try {
            // First try with primary storage key
            const storedData = localStorage.getItem(this.storageKey);
            let primarySamples = [];

            if (storedData) {
                primarySamples = JSON.parse(storedData);
            }

            // Check legacy storage
            const legacyData = localStorage.getItem(this.legacyStorageKey);
            if (legacyData) {
                let legacySamples = [];

                try {
                    const parsedData = JSON.parse(legacyData);

                    // Handle different data formats
                    if (Array.isArray(parsedData)) {
                        legacySamples = this.normalizeSamples(parsedData);
                    } else if (parsedData && typeof parsedData === 'object' && parsedData.samples) {
                        legacySamples = this.normalizeSamples(parsedData.samples);
                    } else if (parsedData && typeof parsedData === 'object') {
                        legacySamples = this.normalizeSamples([parsedData]);
                    }

                    // Merge samples from both storages
                    this.selectedSamples = this.mergeSamples(primarySamples, legacySamples);

                    // Save to primary storage and clear legacy
                    this.saveSamples();
                    localStorage.removeItem(this.legacyStorageKey);
                } catch (parseError) {
                    console.error('Error parsing legacy data:', parseError);
                    this.selectedSamples = primarySamples;
                }
            } else {
                // Just use primary samples
                this.selectedSamples = primarySamples;
            }
        } catch (error) {
            console.error('Error loading samples:', error);
            this.selectedSamples = [];
        }
    }

    // Add this method to merge samples without duplicates
    mergeSamples(primarySamples, legacySamples) {
        console.log('Merging samples from different sources');

        // Create a map of existing samples by fastq_name for quick lookup
        const existingSamplesMap = new Map();
        primarySamples.forEach(sample => {
            existingSamplesMap.set(sample.fastq_name, sample);
        });

        // Add new samples that don't already exist
        legacySamples.forEach(sample => {
            if (!existingSamplesMap.has(sample.fastq_name)) {
                primarySamples.push(sample);
                existingSamplesMap.set(sample.fastq_name, sample);
            }
        });

        console.log(`Merged result: ${primarySamples.length} total samples`);
        return primarySamples;
    }

    // Add back reinitialize method
    reinitialize() {
        // Backup current samples
        const currentSamples = [...this.selectedSamples];

        // Load samples again, which will merge from both storage keys
        this.loadSamples();

        // Check if samples changed
        if (this.selectedSamples.length !== currentSamples.length) {
            // Rebuild the table to reflect the updated samples
            this.rebuildSamplesTable();
            return true;
        }

        return false;
    }

    normalizeSamples(samples) {
        return samples.map(sample => ({
            fastq_name: sample.fastq_name || sample.fastqName || '',
            study_set: sample.study_set || sample.studySet || '',
            load_name: sample.load_name || sample.loadName || '',
            batch_name_from_vendor: sample.batch_name_from_vendor || sample.batchNameFromVendor || '',
            organism_common_name: sample.organism_common_name || sample.organismCommonName || '',
            library_prep: sample.library_prep || sample.libraryPrep || '',
            ingest_status: sample.ingest_status || sample.ingestStatus || '',
            alignment_status: sample.alignment_status || sample.alignmentStatus || '',
            postqc_status: sample.postqc_status || sample.postqcStatus || '',
        }));
    }

    saveSamples() {
        try {
            // Check if the data has actually changed before saving
            const currentData = localStorage.getItem(this.storageKey);
            const newData = JSON.stringify(this.selectedSamples);

            // Only save if the data has changed or doesn't exist
            if (!currentData || currentData !== newData) {
                localStorage.setItem(this.storageKey, newData);
            }
        } catch (error) {
            console.error('Error saving samples to localStorage:', error);

            // If localStorage is full, try to save only essential data
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
            }
        });

        // Handle select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-samples');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (event) => {
                this.handleSelectAllChange(event);
            });
        }
    }

    setupPaginationListeners() {
        // Pagination navigation
        const paginationNav = document.querySelector('.pagination-navigation');
        if (paginationNav) {
            // Get current rows per page
            const getCurrentPerPage = () => {
                const dropdownBtn = document.getElementById('rowsPerPageDropdown');
                return dropdownBtn ? parseInt(dropdownBtn.textContent.trim()) : 25;
            };

            // Generate page URL
            const getPageUrl = (pageNum) => {
                const url = new URL(window.location.href);
                url.searchParams.set('page', pageNum);
                url.searchParams.set('per_page', getCurrentPerPage());
                return url.toString();
            };

            // First page
            const firstPageBtn = paginationNav.querySelector('a[title="First page"]');
            if (firstPageBtn) {
                firstPageBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    window.location.href = getPageUrl(1);
                });
            }

            // Previous page
            const prevPageBtn = paginationNav.querySelector('a[title="Previous page"]');
            if (prevPageBtn) {
                prevPageBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const currentPage = parseInt(document.querySelector('.current-page').textContent);
                    if (currentPage > 1) {
                        window.location.href = getPageUrl(currentPage - 1);
                    }
                });
            }

            // Next page
            const nextPageBtn = paginationNav.querySelector('a[title="Next page"]');
            if (nextPageBtn) {
                nextPageBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const currentPage = parseInt(document.querySelector('.current-page').textContent);
                    const totalPages = parseInt(document.querySelector('.total-pages').textContent);
                    if (currentPage < totalPages) {
                        window.location.href = getPageUrl(currentPage + 1);
                    }
                });
            }

            // Last page
            const lastPageBtn = paginationNav.querySelector('a[title="Last page"]');
            if (lastPageBtn) {
                lastPageBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const totalPages = parseInt(document.querySelector('.total-pages').textContent);
                    window.location.href = getPageUrl(totalPages);
                });
            }
        }

        // Go to page form
        const gotoPageForm = document.getElementById('gotoPageForm');
        if (gotoPageForm) {
            gotoPageForm.addEventListener('submit', (e) => {
                e.preventDefault();
                const pageInput = document.getElementById('gotoPage');
                if (pageInput) {
                    const pageValue = parseInt(pageInput.value, 10);
                    const maxPage = parseInt(pageInput.getAttribute('max'), 10) || 1;

                    if (pageValue > 0 && pageValue <= maxPage) {
                        this.goToPage(pageValue);
                    } else {
                        this.showToastNotification(`Page must be between 1 and ${maxPage}`, 'danger');
                        pageInput.value = Math.min(Math.max(1, pageValue), maxPage);
                    }
                }
            });
        }

        // Rows per page dropdown
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
    }

    setupActionButtons() {
        // Submit button
        const submitBtn = document.getElementById('confirm-submit');
        if (submitBtn) {
            submitBtn.addEventListener('click', (e) => this.handleSampleSubmission(e));
        }

        // Clear selection button
        const clearBtn = document.getElementById('clear-selection');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearStoredData());
        }

        // Refresh jobs button
        const refreshJobsBtn = document.getElementById('refreshJobsBtn');
        if (refreshJobsBtn) {
            refreshJobsBtn.addEventListener('click', () => this.refreshJobs());
        }

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('autoRefreshToggle');
        if (autoRefreshToggle) {
            let refreshInterval;
            autoRefreshToggle.addEventListener('change', function () {
                if (this.checked) {
                    refreshInterval = setInterval(() => this.refreshJobs(), 30000);
                } else {
                    clearInterval(refreshInterval);
                }
            }.bind(this));
        }

        // View Queue button (in job monitor)
        const viewQueueBtn = document.getElementById('view-queue-btn');
        if (viewQueueBtn) {
            viewQueueBtn.addEventListener('click', () => this.showQueueModal());
        }

        // Refresh Queue button (in queue modal)
        const refreshQueueBtn = document.getElementById('refresh-queue');
        if (refreshQueueBtn) {
            refreshQueueBtn.addEventListener('click', () => this.fetchQueueData());
        }
    }

    refreshJobs() {
        fetch('/pipeline/api/update_all_jobs/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    window.location.reload();
                }
            })
            .catch(error => console.error('Error updating jobs:', error));
    }

    updateSelectedSamples() {
        const selectedRows = document.querySelectorAll('.sample-select:checked');
        const selectedFastqNames = new Set();

        // Get the fastq names of currently selected samples
        selectedRows.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                const fastqName = row.querySelector('td:nth-child(2)').textContent.trim();
                selectedFastqNames.add(fastqName);
            }
        });

        // Keep only samples that are still selected in the UI
        this.selectedSamples = this.selectedSamples.filter(sample =>
            !selectedFastqNames.has(sample.fastq_name)
        );

        // Add newly selected samples
        selectedRows.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                const sample = {
                    fastq_name: row.querySelector('td:nth-child(2)').textContent.trim(),
                    study_set: row.querySelector('td:nth-child(3)').textContent.trim(),
                    load_name: row.querySelector('td:nth-child(4)').textContent.trim(),
                    batch_name_from_vendor: row.querySelector('td:nth-child(5)').textContent.trim(),
                    organism_common_name: row.querySelector('td:nth-child(6)').textContent.trim(),
                    library_prep: row.querySelector('td:nth-child(7)').textContent.trim(),
                    ingest_status: row.querySelector('td:nth-child(8)').textContent.trim(),
                    alignment_status: row.querySelector('td:nth-child(9)').textContent.trim(),
                    postqc_status: row.querySelector('td:nth-child(10)').textContent.trim()
                };
                this.selectedSamples.push(sample);
            }
        });

        // Save to localStorage
        this.saveSamples();
    }

    updateSubmitButtonState() {
        const submitButton = document.getElementById('submit-selected');
        if (submitButton) {
            const selectedSamples = document.querySelectorAll('.sample-select:checked');
            submitButton.disabled = selectedSamples.length === 0;
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

        // Get stored samples
        if (!this.selectedSamples || this.selectedSamples.length === 0) {
            this.showEmptyState(tableBody);
            return;
        }

        // Calculate pagination values
        const startIndex = (this.currentPage - 1) * this.itemsPerPage;
        const endIndex = Math.min(startIndex + this.itemsPerPage, this.selectedSamples.length);
        const totalPages = Math.ceil(this.selectedSamples.length / this.itemsPerPage);

        // Update pagination info
        this.updatePaginationInfo(startIndex, endIndex, totalPages);

        // Use document fragment for better performance
        const fragment = document.createDocumentFragment();

        // Build rows for current page
        const currentPageSamples = this.selectedSamples.slice(startIndex, endIndex);

        // Pre-cache status badge HTML for performance
        const statusBadgeCache = {
            'Completed': '<span class="badge bg-success">Completed</span>',
            'In Progress': '<span class="badge bg-warning">In Progress</span>',
            'Not Started': '<span class="badge bg-secondary">Not Started</span>',
            'Pending': '<span class="badge bg-info">Pending</span>',
            'Error': '<span class="badge bg-danger">Error</span>',
            'Failed': '<span class="badge bg-danger">Failed</span>'
        };

        // Create all rows at once for better performance
        for (let i = 0; i < currentPageSamples.length; i++) {
            const sample = currentPageSamples[i];
            const row = document.createElement('tr');
            row.setAttribute('data-fastq', sample.fastq_name || '');

            // Format status with cached badges when possible
            const ingestStatus = this.formatStatus(sample.ingest_status);
            const alignmentStatus = this.formatStatus(sample.alignment_status);
            const postqcStatus = this.formatStatus(sample.postqc_status);

            const ingestBadge = statusBadgeCache[ingestStatus] || this.formatStatusWithBadge(sample.ingest_status);
            const alignmentBadge = statusBadgeCache[alignmentStatus] || this.formatStatusWithBadge(sample.alignment_status);
            const postqcBadge = statusBadgeCache[postqcStatus] || this.formatStatusWithBadge(sample.postqc_status);

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
                <td>${ingestBadge}</td>
                <td>${alignmentBadge}</td>
                <td>${postqcBadge}</td>
            `;

            fragment.appendChild(row);
        }

        // Add fragment to DOM in one operation
        tableBody.appendChild(fragment);

        // Update UI state
        setTimeout(() => {
            this.setupSelectionListeners();
            this.updateSubmitButtonState();
        }, 0);
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

    formatStatusWithBadge(status) {
        const formattedStatus = this.formatStatus(status);
        let badgeClass = 'bg-secondary';

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
        const sampleList = document.getElementById('submit-sample-list');
        if (sampleList) {
            sampleList.innerHTML = '';

            // Group samples by ingest status
            const completedSamples = this.selectedSamples.filter(sample =>
                sample.ingest_status === 'Completed'
            );

            // Add completed samples
            if (completedSamples.length > 0) {
                const completedHeader = document.createElement('h6');
                completedHeader.className = 'mt-3 mb-2';
                completedHeader.innerHTML = 'Ready for Submission:';
                sampleList.appendChild(completedHeader);

                completedSamples.forEach(sample => {
                    const li = document.createElement('li');
                    li.className = 'd-flex justify-content-between align-items-center mb-1';
                    li.innerHTML = `
                        <div>
                            <strong>${sample.fastq_name}</strong>
                            <span class="ms-2 badge bg-success">Ready</span>
                        </div>
                        <small class="text-muted">${sample.workflow || this.determineWorkflow(sample.batch_name_from_vendor)}</small>
                    `;
                    sampleList.appendChild(li);
                });
            }

            // Add pending ingest samples
            if (pendingIngest.length > 0) {
                const pendingHeader = document.createElement('h6');
                pendingHeader.className = 'mt-3 mb-2 text-warning';
                pendingHeader.innerHTML = 'Not Ready (Ingest Incomplete):';
                sampleList.appendChild(pendingHeader);

                pendingIngest.forEach(sample => {
                    const li = document.createElement('li');
                    li.className = 'd-flex justify-content-between align-items-center mb-1';
                    li.innerHTML = `
                        <div>
                            <strong>${sample.fastq_name}</strong>
                            <span class="ms-2 badge bg-warning">Pending Ingest</span>
                    </div>
                        <small class="text-muted">${sample.workflow || this.determineWorkflow(sample.batch_name_from_vendor)}</small>
                    `;
                    sampleList.appendChild(li);
                });

                // Add warning about pending ingest samples
                const warning = document.createElement('div');
                warning.className = 'alert alert-warning mt-3';
                warning.innerHTML = `
                    <small>
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        ${pendingIngest.length} sample${pendingIngest.length !== 1 ? 's' : ''} have not completed ingest. 
                        These samples will be skipped unless you force submission.
                    </small>
                `;
                sampleList.appendChild(warning);
            }
        }

        // Setup submit handler
        const confirmSubmitBtn = document.getElementById('confirm-submit');
        const forceSubmitCheckbox = document.getElementById('force-submit');

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

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('submit-modal'));
        modal.show();
    }

    determineWorkflow(batchName) {
        if (!batchName) {
            return 'RTX';  // Default to RTX if no batch name
        }

        const batchNameUpper = batchName.toUpperCase();

        if (batchNameUpper.startsWith('MTX') || batchNameUpper.includes('ATX')) {
            return 'MTX';
        } else if (batchNameUpper.startsWith('RTX')) {
            return 'RTX';
        } else {
            return 'RTX';  // Default to RTX for unrecognized patterns
        }
    }

    submitSamplesToAlignment(samples, forceSubmit = false) {
        this.showToastNotification('Submitting samples for processing...', 'info', 3000);

        fetch('/api/pipeline/submit-alignment/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({
                samples,
                force_submit: forceSubmit
            })
        })
            .then(response => response.json())
            .then(data => {
                // Check if confirmation is required for samples with incomplete ingest
                if (data.status === 'warning' && data.requires_confirmation) {
                    // Show confirmation dialog for samples with incomplete ingest
                    this.showConfirmationDialog(
                        data.message,
                        () => {
                            // User confirmed - resubmit with force_submit=true
                            this.submitSamplesToAlignment(samples, true);
                        }
                    );
                    return;
                }

                if (data.status === 'success' || data.status === 'warning') {
                    // Remove successfully submitted samples
                    if (data.submitted_samples && Array.isArray(data.submitted_samples)) {
                        this.removeSubmittedSamples(data.submitted_samples);
                    }

                    this.showToastNotification(
                        data.message,
                        data.status === 'warning' ? 'warning' : 'success',
                        5000
                    );

                    // Only redirect if there are no remaining samples
                    if (this.selectedSamples.length === 0) {
                        setTimeout(() => {
                            window.location.href = '/pipeline/jobs/';
                        }, 2000);
                    } else {
                        // Rebuild the table with remaining samples
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

    showConfirmationDialog(message, onConfirm) {
        // Create confirmation modal
        const modalId = 'confirmation-dialog';
        let confirmModal = document.getElementById(modalId);

        // Remove existing modal if present
        if (confirmModal) {
            document.body.removeChild(confirmModal);
        }

        // Create new modal
        confirmModal = document.createElement('div');
        confirmModal.id = modalId;
        confirmModal.className = 'modal fade';
        confirmModal.setAttribute('tabindex', '-1');
        confirmModal.setAttribute('aria-hidden', 'true');

        confirmModal.innerHTML = `
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Confirm Submission</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                    <div class="modal-body">
                        <div class="alert alert-warning">
                            <i class="bi bi-exclamation-triangle me-2"></i>
                            ${message}
                        </div>
                        <p>Would you like to proceed with only the valid samples, or force submission of all samples?</p>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="proceed-valid-only">
                            Submit Valid Only
                        </button>
                        <button type="button" class="btn btn-warning" id="force-submit-all">
                            Force Submit All
                        </button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(confirmModal);

        // Initialize Bootstrap modal
        const bsModal = new bootstrap.Modal(confirmModal);
        bsModal.show();

        // Add event listeners
        document.getElementById('proceed-valid-only').addEventListener('click', () => {
            bsModal.hide();
            this.showToastNotification('Submitting valid samples only...', 'info');
            // Submit only valid samples
            const validSamples = this.selectedSamples.filter(
                sample => sample.ingest_status === 'Completed'
            );
            this.submitSamplesToAlignment(validSamples, false);
        });

        document.getElementById('force-submit-all').addEventListener('click', () => {
            bsModal.hide();
            if (typeof onConfirm === 'function') {
                onConfirm();
            }
        });
    }

    removeSubmittedSamples(submittedSamples) {
        // Create a Set of submitted sample names for faster lookup
        const submittedSet = new Set(submittedSamples.map(sample =>
            typeof sample === 'string' ? sample : sample.fastq_name
        ));

        // Filter out submitted samples
        this.selectedSamples = this.selectedSamples.filter(sample =>
            !submittedSet.has(sample.fastq_name)
        );

        // Save updated samples to localStorage
        this.saveSamples();

        // Update UI elements
        const selectedCount = document.getElementById('selected-count');
        if (selectedCount) {
            selectedCount.textContent = `${this.selectedSamples.length} samples selected`;
        }
    }

    goToPage(pageNumber) {
        if (!this.selectedSamples || this.selectedSamples.length === 0) return;

        const totalPages = Math.ceil(this.selectedSamples.length / this.itemsPerPage);
        pageNumber = Math.min(Math.max(1, pageNumber), totalPages);

        const url = new URL(window.location);
        url.searchParams.set('page', pageNumber);
        url.searchParams.set('per_page', this.itemsPerPage);
        window.location.href = url.toString();
    }

    changeRowsPerPage(perPage) {
        if (isNaN(perPage) || perPage < 1) perPage = 25;

        const url = new URL(window.location);
        url.searchParams.set('per_page', perPage);
        url.searchParams.set('page', '1');
        window.location.href = url.toString();
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
                        <td>${sample.library_prep}</td>
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

    showQueueModal() {
        // Fetch and display queue data
        this.fetchQueueData();

        // Show the modal
        const queueModal = new bootstrap.Modal(document.getElementById('queue-modal'));
        queueModal.show();
    }

    fetchQueueData() {
        // Show loading indicators
        document.getElementById('alignment-queue-body').innerHTML = '<tr><td colspan="7" class="text-center">Loading queue data...</td></tr>';
        document.getElementById('postqc-queue-body').innerHTML = '<tr><td colspan="7" class="text-center">Loading queue data...</td></tr>';

        // Fetch data from API
        fetch('/api/pipeline/get-queue-data/', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Update alignment queue
                    this.displayQueueData(
                        data.alignment_queue,
                        'alignment-queue-body',
                        'alignment-count'
                    );

                    // Update post-QC queue
                    this.displayQueueData(
                        data.postqc_queue,
                        'postqc-queue-body',
                        'postqc-count'
                    );
                } else {
                    this.showToastNotification(`Error fetching queue data: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error fetching queue data:', error);
                this.showToastNotification('Error fetching queue data from server', 'danger');
            });
    }

    displayQueueData(queueItems, tableBodyId, countId) {
        const tableBody = document.getElementById(tableBodyId);
        const countBadge = document.getElementById(countId);

        if (!tableBody) return;

        // Update count badge
        if (countBadge) {
            countBadge.textContent = queueItems.length;
        }

        // Clear table
        tableBody.innerHTML = '';

        if (queueItems.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="7" class="text-center">No items in queue</td></tr>';
            return;
        }

        // Add rows for each queue item
        queueItems.forEach(item => {
            // Parse metadata if available
            let metadata = {};
            if (item.metadata) {
                try {
                    metadata = JSON.parse(item.metadata);
                } catch (e) {
                    console.error('Error parsing metadata JSON:', e);
                }
            }

            // Create badge based on status
            let statusBadge = '';
            switch (item.status) {
                case 'pending':
                    statusBadge = '<span class="badge bg-secondary">Pending</span>';
                    break;
                case 'submitted':
                    statusBadge = '<span class="badge bg-info">Submitted</span>';
                    break;
                case 'running':
                    statusBadge = '<span class="badge bg-warning">Running</span>';
                    break;
                case 'completed':
                    statusBadge = '<span class="badge bg-success">Completed</span>';
                    break;
                case 'failed':
                    statusBadge = '<span class="badge bg-danger">Failed</span>';
                    break;
                default:
                    statusBadge = `<span class="badge bg-secondary">${item.status}</span>`;
            }

            // Format dates
            const addedTime = new Date(item.added_time).toLocaleString();
            const startTime = item.start_time ? new Date(item.start_time).toLocaleString() : '-';

            // Create row
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.fastq_name}</td>
                <td><span class="badge ${item.workflow === 'MTX' ? 'bg-info' : 'bg-primary'}">${item.workflow}</span></td>
                <td>${statusBadge}</td>
                <td>${item.demand_id || '-'}</td>
                <td>${addedTime}</td>
                <td>${startTime}</td>
                <td>
                    <div class="btn-group btn-group-sm">
                        <button type="button" class="btn btn-outline-info btn-sm view-details-btn" 
                                data-fastq="${item.fastq_name}" data-bs-toggle="tooltip" title="View Details">
                            <i class="bi bi-info-circle"></i>
                        </button>
                        <button type="button" class="btn btn-outline-primary btn-sm refresh-status-btn"
                                data-fastq="${item.fastq_name}" data-bs-toggle="tooltip" title="Refresh Status">
                            <i class="bi bi-arrow-repeat"></i>
                        </button>
                    </div>
                </td>
            `;
            tableBody.appendChild(row);

            // Add event listeners for the buttons
            const viewDetailsBtn = row.querySelector('.view-details-btn');
            if (viewDetailsBtn) {
                viewDetailsBtn.addEventListener('click', () => {
                    this.showSampleDetails(item, metadata);
                });
            }

            const refreshStatusBtn = row.querySelector('.refresh-status-btn');
            if (refreshStatusBtn) {
                refreshStatusBtn.addEventListener('click', () => {
                    this.refreshSampleStatus(item.fastq_name, item.demand_id);
                });
            }
        });

        // Initialize tooltips
        const tooltips = [].slice.call(tableBody.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltips.map(function (tooltipNode) {
            return new bootstrap.Tooltip(tooltipNode);
        });
    }

    showSampleDetails(item, metadata) {
        // Create modal for displaying sample details
        const modalId = 'sample-details-modal';
        let detailsModal = document.getElementById(modalId);

        // Remove existing modal if present
        if (detailsModal) {
            document.body.removeChild(detailsModal);
        }

        // Determine workflow from batch name
        const workflow = item.workflow || this.determineWorkflow(metadata.batch_name_from_vendor || '');

        // Format the command for display with line breaks
        let formattedCommand = '';
        if (item.command) {
            formattedCommand = item.command.replace(/\n/g, '<br>');
        }

        // Create details modal
        detailsModal = document.createElement('div');
        detailsModal.id = modalId;
        detailsModal.className = 'modal fade';
        detailsModal.setAttribute('tabindex', '-1');
        detailsModal.setAttribute('aria-hidden', 'true');

        detailsModal.innerHTML = `
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Sample Details: ${item.fastq_name}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                    </div>
                    <div class="modal-body">
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <h6>Status Information</h6>
                                <table class="table table-sm table-bordered">
                                    <tr>
                                        <th>Workflow:</th>
                                        <td><span class="badge ${workflow === 'MTX' ? 'bg-info' : 'bg-primary'}">${workflow}</span></td>
                                    </tr>
                                    <tr>
                                        <th>Status:</th>
                                        <td>${item.status || 'Unknown'}</td>
                                    </tr>
                                    <tr>
                                        <th>Demand ID:</th>
                                        <td>${item.demand_id || 'Not yet assigned'}</td>
                                    </tr>
                                    <tr>
                                        <th>Added:</th>
                                        <td>${new Date(item.added_time).toLocaleString()}</td>
                                    </tr>
                                    <tr>
                                        <th>Started:</th>
                                        <td>${item.start_time ? new Date(item.start_time).toLocaleString() : 'Not started'}</td>
                                    </tr>
                                </table>
                            </div>
                            <div class="col-md-6">
                                <h6>Sample Metadata</h6>
                                <table class="table table-sm table-bordered">
                                    <tr>
                                        <th>FASTQ Name:</th>
                                        <td>${metadata.fastq_name || item.fastq_name}</td>
                                    </tr>
                                    <tr>
                                        <th>Organism:</th>
                                        <td>${metadata.organism_common_name || 'Unknown'}</td>
                                    </tr>
                                    <tr>
                                        <th>Batch:</th>
                                        <td>${metadata.batch_name_from_vendor || 'Unknown'}</td>
                                    </tr>
                                    <tr>
                                        <th>Load Name:</th>
                                        <td>${metadata.load_name || 'Unknown'}</td>
                                    </tr>
                                    <tr>
                                        <th>Library Prep:</th>
                                        <td>${metadata.library_prep || 'Unknown'}</td>
                                    </tr>
                                </table>
                            </div>
                        </div>
                        
                        <h6>Command</h6>
                        <div class="border rounded p-2 bg-light">
                            <pre class="mb-0"><code>${formattedCommand || 'Command not available'}</code></pre>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(detailsModal);

        // Initialize and show Bootstrap modal
        const bsModal = new bootstrap.Modal(detailsModal);
        bsModal.show();
    }

    refreshSampleStatus(fastqName, demandId) {
        // Show toast notification
        this.showToastNotification(`Refreshing status for ${fastqName}...`, 'info');

        // Determine which endpoint to use based on available info
        let url = '/api/pipeline/check-alignment-status/';
        if (demandId) {
            url += `?demand_id=${demandId}`;
        } else {
            url += `?fastq_name=${fastqName}`;
        }

        // Fetch updated status
        fetch(url, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    this.showToastNotification(`Status updated: ${data.job_status || 'Unknown'}`, 'success');

                    // Refresh queue data to show updated status
                    this.fetchQueueData();
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error refreshing status:', error);
                this.showToastNotification('Error refreshing sample status', 'danger');
            });
    }

    // Add the bulkAddSamples method for efficient bulk operations
    bulkAddSamples(samples) {
        if (!samples || !samples.length) return;

        // Create a map of existing samples for faster lookups
        const existingSamplesMap = new Map();
        this.selectedSamples.forEach(sample => {
            existingSamplesMap.set(sample.fastq_name, true);
        });

        // Add only non-duplicate samples
        let newSamplesCount = 0;
        samples.forEach(sample => {
            if (!existingSamplesMap.has(sample.fastq_name)) {
                this.selectedSamples.push(sample);
                newSamplesCount++;
            }
        });

        // Only save if we actually added new samples
        if (newSamplesCount > 0) {
            // Debounce the save operation for better performance
            this._debouncedSave();
        }

        return newSamplesCount;
    }

    // Private method for debounced saving
    _debouncedSave() {
        // Clear any pending save operation
        if (this._saveTimeout) {
            clearTimeout(this._saveTimeout);
        }

        // Schedule a new save operation
        this._saveTimeout = setTimeout(() => {
            this.saveSamples();
            this._saveTimeout = null;
        }, 300); // Wait 300ms to batch multiple operations
    }
}

// Initialize and export
const pipelineLocalData = new PipelineLocalData();
window.pipelineLocalData = pipelineLocalData;