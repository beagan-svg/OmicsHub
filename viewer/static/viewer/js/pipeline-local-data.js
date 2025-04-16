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
                // Add a small delay to reinitialize after page is fully loaded
                setTimeout(() => this.reinitialize(), 300);
            });
        } else {
            this.setupEventListeners();
            // Add a small delay to reinitialize after page is fully loaded
            setTimeout(() => this.reinitialize(), 300);
        }
    }

    loadSamples() {
        console.log('Loading samples from storage');
        try {
            // First try with primary storage key
            const storedData = localStorage.getItem(this.storageKey);
            let primarySamples = [];

            if (storedData) {
                primarySamples = JSON.parse(storedData);
                console.log(`Found ${primarySamples.length} samples in primary storage`);
            }

            // Check legacy storage
            const legacyData = localStorage.getItem(this.legacyStorageKey);
            if (legacyData) {
                console.log('Found legacy data, processing it');
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

                    console.log(`Processed ${legacySamples.length} samples from legacy storage`);

                    // Merge samples from both storages
                    this.selectedSamples = this.mergeSamples(primarySamples, legacySamples);
                    console.log(`Combined total: ${this.selectedSamples.length} samples after merging`);

                    // Save to primary storage and clear legacy
                    this.saveSamples();
                    localStorage.removeItem(this.legacyStorageKey);
                    console.log('Legacy data processed and cleared');
                } catch (parseError) {
                    console.error('Error parsing legacy data:', parseError);
                    this.selectedSamples = primarySamples;
                }
            } else {
                // Just use primary samples
                this.selectedSamples = primarySamples;
                console.log('No legacy data found, using only primary storage');
            }

            // Add console log to show final samples count
            console.log(`Loaded ${this.selectedSamples.length} total samples`);
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
        console.log('Reinitializing PipelineLocalData to check for updated localStorage data');

        // Backup current samples
        const currentSamples = [...this.selectedSamples];

        // Load samples again, which will merge from both storage keys
        this.loadSamples();

        // Check if samples changed
        if (this.selectedSamples.length !== currentSamples.length) {
            console.log(`Sample count changed from ${currentSamples.length} to ${this.selectedSamples.length}`);
            // Rebuild the table to reflect the updated samples
            this.rebuildSamplesTable();
            return true;
        }

        console.log('No changes in samples detected during reinitialization');
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
        localStorage.setItem(this.storageKey, JSON.stringify(this.selectedSamples));
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

        // Build rows for current page
        const currentPageSamples = this.selectedSamples.slice(startIndex, endIndex);
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

        // Update UI state
        this.setupSelectionListeners();
        this.updateSubmitButtonState();
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

        if (pendingIngest.length > 0) {
            this.showToastNotification(
                `${pendingIngest.length} samples have not completed ingest and will be skipped`,
                'warning'
            );
        }

        // Populate modal
        const sampleList = document.getElementById('submit-sample-list');
        if (sampleList) {
            sampleList.innerHTML = '';
            this.selectedSamples.forEach(sample => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <strong>${sample.fastq_name}</strong>
                    <span class="ms-2 badge ${sample.ingest_status === 'Completed' ? 'bg-success' : 'bg-warning'}">
                        ${sample.ingest_status}
                    </span>
                `;
                sampleList.appendChild(li);
            });
        }

        // Setup submit handler
        const confirmSubmitBtn = document.getElementById('confirm-submit');
        if (confirmSubmitBtn) {
            confirmSubmitBtn.disabled = this.selectedSamples.length === 0;
            confirmSubmitBtn.onclick = () => {
                this.submitSamplesToAlignment(this.selectedSamples);
                const modal = bootstrap.Modal.getInstance(document.getElementById('submit-modal'));
                if (modal) modal.hide();
            };
        }

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('submit-modal'));
        modal.show();
    }

    submitSamplesToAlignment(samples) {
        this.showToastNotification('Submitting samples for processing...', 'info', 3000);

        fetch('/api/pipeline/submit-alignment/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify({ samples })
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success' || data.status === 'warning') {
                    this.showToastNotification(
                        data.message,
                        data.status === 'warning' ? 'warning' : 'success',
                        5000
                    );

                    setTimeout(() => {
                        window.location.href = '/pipeline/jobs/';
                    }, 2000);
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger', 5000);
                }
            })
            .catch(error => {
                console.error('Error submitting samples:', error);
                this.showToastNotification('Error submitting samples for alignment', 'danger', 5000);
            });
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

        // Skip showing any notification here
        // Toast notification is exclusively handled in dashboard.html
    }
}

// Initialize and export
const pipelineLocalData = new PipelineLocalData();
window.pipelineLocalData = pipelineLocalData;