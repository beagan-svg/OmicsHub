/**
 * local-data.js
 * Handles local storage of selected samples and rebuilding the pipeline table
 */

class PipelineLocalData {
    constructor() {
        this.storageKey = 'pipelineSelectedSamples';
        this.legacyStorageKey = 'selectedSamplesForPipeline';
        this.selectedSamples = [];
        this.itemsPerPage = 25;
        this.currentPage = 1;
        this.init();
    }

    init() {
        console.log('Initializing PipelineLocalData');

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

    // Merge samples without duplicates
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

    // Reinitialize to check for updated localStorage data
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

    // Normalize sample data to consistent format
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

    // Save samples to localStorage
    saveSamples() {
        localStorage.setItem(this.storageKey, JSON.stringify(this.selectedSamples));
    }

    // Initialize pagination settings
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

    // Set up all event listeners
    setupEventListeners() {
        // Set up main event listeners
        this.setupSelectionListeners();
        this.setupPaginationListeners();
        this.setupActionButtons();

        // Rebuild the table initially
        this.rebuildSamplesTable();
    }

    // Setup listeners for sample selection
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

    // Setup listeners for pagination controls
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

            // Pagination button listeners
            ['first', 'prev', 'next', 'last'].forEach(type => {
                const selector = `a[title="${type.charAt(0).toUpperCase() + type.slice(1)} page"]`;
                const btn = paginationNav.querySelector(selector);
                if (btn) {
                    btn.addEventListener('click', (e) => {
                        e.preventDefault();
                        const currentPage = parseInt(document.querySelector('.current-page').textContent);
                        const totalPages = parseInt(document.querySelector('.total-pages').textContent);

                        let targetPage;
                        if (type === 'first') targetPage = 1;
                        else if (type === 'prev') targetPage = Math.max(1, currentPage - 1);
                        else if (type === 'next') targetPage = Math.min(totalPages, currentPage + 1);
                        else if (type === 'last') targetPage = totalPages;

                        window.location.href = getPageUrl(targetPage);
                    });
                }
            });
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
                        window.AppUtils.showToastNotification(`Page must be between 1 and ${maxPage}`, 'danger');
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

    // Setup action button listeners
    setupActionButtons() {
        // Clear selection button
        const clearBtn = document.getElementById('clear-toggle');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearSelectedSamples());
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-now-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.refreshJobData());
        }
    }

    // Update selected samples based on checkboxes
    updateSelectedSamples() {
        const selectedCheckboxes = document.querySelectorAll('.sample-select:checked');
        const newSelectedSamples = [];

        selectedCheckboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                const sample = this.extractSampleFromRow(row);
                if (sample.fastq_name) {
                    newSelectedSamples.push(sample);
                }
            }
        });

        // Update the selected samples and save
        this.selectedSamples = newSelectedSamples;
        this.saveSamples();

        // Update selected count display
        this.updateSelectedCount();
    }

    // Extract sample data from a table row
    extractSampleFromRow(row) {
        return {
            fastq_name: row.cells[1].textContent.trim(),
            study_set: row.cells[2].textContent.trim(),
            load_name: row.cells[3].textContent.trim(),
            batch_name_from_vendor: row.cells[4].textContent.trim(),
            organism_common_name: row.cells[5].textContent.trim(),
            library_prep: row.cells[6].textContent.trim(),
            ingest_status: row.cells[7].querySelector('.badge').textContent.trim(),
            alignment_status: row.cells[8].querySelector('.badge').textContent.trim(),
            postqc_status: row.cells[9].querySelector('.badge').textContent.trim(),
        };
    }

    // Update the selected samples count display
    updateSelectedCount() {
        const countElement = document.getElementById('selected-count');
        if (countElement) {
            countElement.textContent = `${this.selectedSamples.length} sample${this.selectedSamples.length !== 1 ? 's' : ''} selected`;
        }
    }

    // Update the submit button state (enabled/disabled)
    updateSubmitButtonState() {
        const submitBtn = document.getElementById('submit-action-btn');
        if (submitBtn) {
            submitBtn.disabled = this.selectedSamples.length === 0;
        }
    }

    // Handle "Select All" checkbox changes
    handleSelectAllChange(event) {
        const selectAllCheckbox = event.target;
        const isChecked = selectAllCheckbox.checked;

        // Update all visible checkboxes
        const checkboxes = document.querySelectorAll('.sample-select');
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });

        // Update selected samples
        this.updateSelectedSamples();
        this.updateSubmitButtonState();
    }

    // Navigate to a specific page
    goToPage(pageNumber) {
        const url = new URL(window.location.href);
        url.searchParams.set('page', pageNumber);
        window.location.href = url.toString();
    }

    // Change rows per page
    changeRowsPerPage(perPage) {
        const url = new URL(window.location.href);
        url.searchParams.set('per_page', perPage);
        url.searchParams.set('page', 1); // Reset to first page
        window.location.href = url.toString();
    }

    // Rebuild samples table with selected items
    rebuildSamplesTable() {
        const tableBody = document.querySelector('#samples-table tbody');
        if (!tableBody || this.selectedSamples.length === 0) {
            this.updateSelectedCount();
            this.updateSubmitButtonState();
            return;
        }

        // Get existing rows and create a map of fastq names to checkboxes
        const existingRows = tableBody.querySelectorAll('tr');
        const fastqToCheckbox = new Map();

        existingRows.forEach(row => {
            const fastqCell = row.cells[1];
            const checkbox = row.querySelector('.sample-select');
            if (fastqCell && checkbox) {
                const fastqName = fastqCell.textContent.trim();
                fastqToCheckbox.set(fastqName, checkbox);
            }
        });

        // Check/uncheck boxes based on selected samples
        this.selectedSamples.forEach(sample => {
            const checkbox = fastqToCheckbox.get(sample.fastq_name);
            if (checkbox) {
                checkbox.checked = true;
            }
        });

        // Update UI elements
        this.updateSelectedCount();
        this.updateSubmitButtonState();
    }

    // Clear all selected samples
    clearSelectedSamples() {
        console.log('Clearing selected samples');

        // Clear checkboxes
        const checkboxes = document.querySelectorAll('.sample-select:checked');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });

        // Clear selected samples
        this.selectedSamples = [];
        this.saveSamples();

        // Update UI
        this.updateSelectedCount();
        this.updateSubmitButtonState();

        // Show notification
        window.AppUtils.showToastNotification('Selection cleared', 'success');
    }

    // Refresh job data
    async refreshJobData() {
        const refreshBtn = document.getElementById('refresh-now-btn');
        if (!refreshBtn) return;

        try {
            // Set loading state
            refreshBtn.disabled = true;
            refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Refreshing...';

            // Show progress indicator
            const progressContainer = document.createElement('div');
            progressContainer.className = 'alert alert-info mb-3';
            progressContainer.innerHTML = '<i class="bi bi-arrow-repeat me-2"></i>Updating job statuses...';
            document.querySelector('.container-fluid').prepend(progressContainer);

            // Fetch updated job data
            const jobData = await window.API.getJobData();

            // Process the response
            if (jobData.status === 'success') {
                // Update job counts
                const totalCount = jobData.alignment_count + jobData.postqc_count;
                document.getElementById('job-count-badge').textContent = totalCount;
                document.getElementById('alignment-count').textContent = jobData.alignment_count;
                document.getElementById('postqc-count').textContent = jobData.postqc_count;

                // Update running jobs section
                this.updateRunningJobs(jobData.running_jobs);

                // Update completed jobs section
                this.updateCompletedJobs(jobData.completed_jobs);

                // Show success message
                window.AppUtils.showToastNotification('Job data updated successfully', 'success');
            } else {
                throw new Error(jobData.message || 'Failed to update job data');
            }
        } catch (error) {
            window.AppUtils.showToastNotification(`Error: ${error.message}`, 'error');
        } finally {
            // Reset button
            refreshBtn.disabled = false;
            refreshBtn.innerHTML = '<i class="bi bi-arrow-clockwise me-2"></i>Refresh Now';

            // Remove progress indicator
            const progressContainer = document.querySelector('.container-fluid .alert-info');
            if (progressContainer) {
                progressContainer.remove();
            }
        }
    }

    // Update running jobs display
    updateRunningJobs(runningJobs) {
        const container = document.querySelector('.active-alignments');
        if (!container) return;

        const tableBody = container.querySelector('tbody');
        if (!tableBody) return;

        if (runningJobs && runningJobs.length > 0) {
            // Clear existing rows
            tableBody.innerHTML = '';

            // Add new rows
            runningJobs.forEach(job => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${job.fastq_name}</td>
                    <td>${job.demand_id}</td>
                    <td><span class="badge bg-info">${job.status}</span></td>
                `;
                tableBody.appendChild(row);
            });

            // Show table
            const noJobsAlert = container.querySelector('.alert-info');
            if (noJobsAlert) noJobsAlert.style.display = 'none';
            container.querySelector('table').style.display = 'table';
        } else {
            // Show "no jobs" message
            tableBody.innerHTML = '';
            const noJobsAlert = container.querySelector('.alert-info');
            if (noJobsAlert) noJobsAlert.style.display = 'block';
            container.querySelector('table').style.display = 'none';
        }
    }

    // Update completed jobs display
    updateCompletedJobs(completedJobs) {
        const container = document.querySelector('.completed-alignments');
        if (!container) return;

        const tableBody = container.querySelector('tbody');
        if (!tableBody) return;

        if (completedJobs && completedJobs.length > 0) {
            // Clear existing rows
            tableBody.innerHTML = '';

            // Add new rows
            completedJobs.forEach(job => {
                const row = document.createElement('tr');
                const status = job.status.toLowerCase();
                const statusClass = status === 'completed' ? 'bg-success' :
                    status === 'failed' ? 'bg-danger' : 'bg-secondary';

                row.innerHTML = `
                    <td>${job.fastq_name}</td>
                    <td>${job.demand_id}</td>
                    <td><span class="badge ${statusClass}">${job.status}</span></td>
                `;
                tableBody.appendChild(row);
            });

            // Show table
            const noJobsAlert = container.querySelector('.alert-info');
            if (noJobsAlert) noJobsAlert.style.display = 'none';
            container.querySelector('table').style.display = 'table';
        } else {
            // Show "no jobs" message
            tableBody.innerHTML = '';
            const noJobsAlert = container.querySelector('.alert-info');
            if (noJobsAlert) noJobsAlert.style.display = 'block';
            container.querySelector('table').style.display = 'none';
        }
    }
}

// Initialize and expose local data manager
document.addEventListener('DOMContentLoaded', () => {
    window.pipelineLocalData = new PipelineLocalData();
}); 