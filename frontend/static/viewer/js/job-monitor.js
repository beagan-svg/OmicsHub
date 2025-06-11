/**
 * job-monitor.js
 * Handles functionality for job monitoring dashboard
 */

// Get CSRF token for secure API requests
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

class JobMonitor {
    constructor() {
        console.log('Initializing Job Monitor...');

        // Add initial data logging
        document.addEventListener('DOMContentLoaded', () => {
            console.log('DOM Content Loaded - Getting initial running jobs data');
            const runningJobsTable = document.querySelector('#running-jobs-table tbody');
            if (runningJobsTable) {
                const rows = runningJobsTable.querySelectorAll('tr');
                const initialJobs = [];

                rows.forEach(row => {
                    if (!row.querySelector('.alert-info')) {  // Skip the "no jobs" message row
                        const job = {
                            fastq_name: row.cells[0].textContent.trim(),
                            command: row.cells[1].querySelector('code').textContent.trim(),
                            demand_id: row.cells[2].querySelector('.text-monospace').textContent.trim(),
                            attempts: row.cells[3].textContent.trim(),
                            time: row.cells[4].textContent.trim()
                        };
                        initialJobs.push(job);
                    }
                });

                console.log('Initial running jobs data:', initialJobs);
            } else {
                console.log('Running jobs table not found during initialization');
            }
        });

        this.initializeEventListeners();
        this.updateJobsInProgress = false;

        // Initialize automatic data fetching
        this.autoRefreshInterval = null;
        this.autoRefreshTime = 30000; // 30 seconds

        // Set progress bar width dynamically
        this.setProgressBarWidth();

        // Initialize copy-to-clipboard for Demand IDs
        this.initializeCopyToClipboard();

        // Initialize pagination
        this.pagination = {
            running: {
                currentPage: 1,
                totalPages: 1,
                perPage: 10,
                totalItems: 0,
                data: []
            },
            completed: {
                currentPage: 1,
                totalPages: 1,
                perPage: 25,
                totalItems: 0,
                data: []
            }
        };

        this.initializePagination();
    }

    /**
     * Sets the width of the progress bar based on the job_counts.total value
     */
    setProgressBarWidth() {
        // Find the progress bar element
        const progressBar = document.querySelector('.job-count-progress');
        if (progressBar) {
            // Get the value from the aria-valuenow attribute
            const value = progressBar.getAttribute('aria-valuenow');
            // Set the width directly using style
            if (value !== null) {
                progressBar.style.width = `${value}%`;
            }
        }
    }

    initializeEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('Initializing event listeners for job monitor...');

            // Set up refresh jobs button
            const refreshNowBtn = document.getElementById('refreshNowBtn');
            if (refreshNowBtn) {
                refreshNowBtn.addEventListener('click', () => this.refreshNow(true));
            }

            // Set up update all jobs button
            const updateAllJobsBtn = document.getElementById('updateAllJobsBtn');
            if (updateAllJobsBtn) {
                updateAllJobsBtn.addEventListener('click', () => this.updateAllJobs());
            }

            // Set up auto-refresh toggle
            const autoRefreshToggle = document.getElementById('autoRefreshToggle');
            if (autoRefreshToggle) {
                autoRefreshToggle.addEventListener('change', () => {
                    if (autoRefreshToggle.checked) {
                        this.startAutoRefresh();
                        this.showToastNotification('Auto-refresh enabled - updating every 30 seconds', 'info');
                    } else {
                        this.stopAutoRefresh();
                        this.showToastNotification('Auto-refresh disabled', 'info');
                    }
                });
            }

            // Set up stop job confirmation
            const confirmStopBtn = document.getElementById('confirmStopBtn');
            if (confirmStopBtn) {
                console.log('Found confirm stop button:', confirmStopBtn);
                confirmStopBtn.addEventListener('click', () => {
                    const demandId = confirmStopBtn.getAttribute('data-demand-id');
                    console.log('Confirm stop button clicked with demand ID:', demandId);
                    if (demandId) {
                        this.stopJob(demandId);
                    } else {
                        console.error('No demand ID found on confirm stop button');
                    }
                });
            } else {
                console.warn('Confirm stop button not found in DOM');
            }

            // Set up check status buttons
            document.querySelectorAll('.check-status-btn').forEach(button => {
                button.addEventListener('click', (e) => {
                    const demandId = e.currentTarget.dataset.demandId;
                    this.checkJobStatus(demandId);
                });
            });

            // Stop job buttons
            const stopButtons = document.querySelectorAll('.stop-job-btn');
            console.log('Found stop job buttons:', stopButtons.length);
            stopButtons.forEach(button => {
                console.log('Setting up stop button listener for:', button);
                button.addEventListener('click', (e) => {
                    const demandId = e.currentTarget.dataset.demandId;
                    console.log('Stop button clicked with demand ID:', demandId);
                    if (!demandId) {
                        console.error('No demand ID found on stop button');
                        return;
                    }
                    this.showStopJobConfirmation(demandId);
                });
            });

            // Job details buttons
            const jobDetailsButtons = document.querySelectorAll('.job-details-btn');
            console.log('Found job details buttons:', jobDetailsButtons.length);
            jobDetailsButtons.forEach(button => {
                button.addEventListener('click', (e) => {
                    const fastqName = e.currentTarget.dataset.fastqName;
                    const alignmentDemandId = e.currentTarget.dataset.alignmentDemandId;
                    const postqcDemandId = e.currentTarget.dataset.postqcDemandId;
                    console.log('Job details button clicked for:', fastqName);

                    // Find the row to extract job data
                    const row = e.currentTarget.closest('tr');
                    if (row) {
                        this.extractAndShowJobDetails(row, fastqName, alignmentDemandId, postqcDemandId);
                    }
                });
            });

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

            // Call setProgressBarWidth after DOM is fully loaded
            this.setProgressBarWidth();

            // Initialize copy to clipboard after DOM is loaded
            this.initializeCopyToClipboard();

            // Perform initial refresh to get fresh data
            console.log('Performing initial data refresh...');
            setTimeout(() => {
                this.refreshDisplay(false);
            }, 100);
        });
    }

    /**
     * Initialize copy to clipboard functionality for Demand IDs
     */
    initializeCopyToClipboard() {
        document.querySelectorAll('.demand-id-cell').forEach(cell => {
            // Add ripple effect
            cell.addEventListener('mousedown', function (e) {
                const x = e.pageX - this.getBoundingClientRect().left;
                const y = e.pageY - this.getBoundingClientRect().top;

                const rippleElement = document.createElement('div');
                rippleElement.classList.add('ripple');
                rippleElement.style.top = y + 'px';
                rippleElement.style.left = x + 'px';

                this.appendChild(rippleElement);

                setTimeout(() => {
                    rippleElement.remove();
                }, 600);
            });

            // Add click to copy 
            cell.addEventListener('click', function (e) {
                const demandId = this.textContent.trim();
                if (demandId) {
                    navigator.clipboard.writeText(demandId)
                        .then(() => {
                            // Add copied class for visual feedback
                            this.classList.add('copied');

                            // Show toast notification
                            const toast = document.createElement('div');
                            toast.className = 'material-toast';
                            toast.innerHTML = `
                                <div class="material-toast-icon">
                                    <i class="bi bi-clipboard-check"></i>
                                </div>
                                <div class="material-toast-message">
                                    Demand ID copied to clipboard
                                </div>
                            `;

                            document.body.appendChild(toast);

                            // Show toast with slight delay for better animation
                            setTimeout(() => {
                                toast.classList.add('show');
                            }, 10);

                            // Remove toast after delay
                            setTimeout(() => {
                                toast.classList.remove('show');
                                setTimeout(() => {
                                    toast.remove();
                                }, 300);
                            }, 2500);

                            // Remove copied class after animation
                            setTimeout(() => {
                                this.classList.remove('copied');
                            }, 1500);
                        })
                        .catch(err => {
                            console.error('Failed to copy:', err);
                            this.showToastNotification('Failed to copy to clipboard', 'error');
                        });
                }
            });
        });
    }

    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshCycle = 0; // Track refresh cycles
        this.autoRefreshInterval = setInterval(() => {
            this.autoRefreshCycle++;

            // More aggressive refresh strategy for job monitoring:
            // - Every cycle (30s): Refresh display (may use 1-minute cache)
            // - Every 2nd cycle (60s): Force fresh data from database
            // - Every 4th cycle (120s): Full OCS status update

            if (this.autoRefreshCycle % 4 === 0) {
                console.log('Auto-refresh: Performing full job status update with OCS check');
                this.updateAllJobs();
            } else if (this.autoRefreshCycle % 2 === 0) {
                console.log('Auto-refresh: Forcing fresh data from database');
                this.refreshNow(false); // Force fresh data
            } else {
                console.log('Auto-refresh: Refreshing display (may use cache)');
                this.refreshDisplay(false); // May use 1-minute cache
            }
        }, this.autoRefreshTime);
    }

    /**
     * Stop auto-refresh interval
     */
    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    /**
     * Update the job statistics display
     */
    updateJobStatistics(jobCounts) {
        console.group('Job Statistics Update');
        console.log('Received job counts:', jobCounts);

        // Update alignment jobs count
        const alignCountElement = document.querySelector('.row .col-6:first-child .text-center h2');
        if (alignCountElement) {
            const oldCount = alignCountElement.textContent;
            alignCountElement.textContent = jobCounts.align_count || 0;
            console.log('Alignment count:', {
                old: oldCount,
                new: jobCounts.align_count || 0,
                element: alignCountElement
            });
        } else {
            console.warn('Alignment count element not found');
        }

        // Update post-QC jobs count
        const postAlignCountElement = document.querySelector('.row .col-6:last-child .text-center h2');
        if (postAlignCountElement) {
            const oldCount = postAlignCountElement.textContent;
            postAlignCountElement.textContent = jobCounts.post_align_count || 0;
            console.log('Post-align count:', {
                old: oldCount,
                new: jobCounts.post_align_count || 0,
                element: postAlignCountElement
            });
        } else {
            console.warn('Post-align count element not found');
        }

        // Update total jobs count
        const totalCountElement = document.querySelector('.row .col-12 .text-center h3');
        if (totalCountElement) {
            const oldTotal = totalCountElement.textContent;
            const total = jobCounts.total || 0;
            totalCountElement.textContent = total;
            console.log('Total count:', {
                old: oldTotal,
                new: total,
                element: totalCountElement
            });
        } else {
            console.warn('Total count element not found');
        }

        // Update progress bar
        const progressBar = document.querySelector('.job-count-progress');
        if (progressBar) {
            const oldWidth = progressBar.style.width;
            const total = jobCounts.total || 0;
            progressBar.style.width = `${total}%`;
            progressBar.setAttribute('aria-valuenow', total);
            progressBar.textContent = `${total}%`;
            console.log('Progress bar update:', {
                old: oldWidth,
                new: `${total}%`,
                element: progressBar
            });
        } else {
            console.warn('Progress bar element not found');
        }

        console.groupEnd();
    }

    /**
     * Refresh display - can use cached data for performance (used by auto-refresh)
     * @param {boolean} showSuccessToast - Whether to show the success toast notification
     */
    async refreshDisplay(showSuccessToast = false) {
        if (this.updateJobsInProgress) return;
        this.updateJobsInProgress = true;

        try {
            console.log('Fetching job data (may use cache)...');
            const response = await fetch('/api/pipeline/get-job-data/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken')
                }
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            console.log('Received job data from server:', data);

            // Update data source indicator
            this.updateDataSourceIndicator(data.from_cache || false, false);

            if (data.running_jobs) {
                console.log(`Found ${data.running_jobs.length} running jobs`);
                this.updateRunningJobsTable(data.running_jobs);
            } else {
                console.warn('No running_jobs data in response:', data);
            }

            // Update completed jobs table if data is available
            if (data.completed_jobs) {
                console.log(`Found ${data.completed_jobs.length} completed jobs`);
                this.updateCompletedJobsTable(data.completed_jobs);
            } else {
                console.warn('No completed_jobs data in response:', data);
            }

            if (data.job_counts) {
                console.log('Updating job counts:', data.job_counts);
                this.updateJobStatistics(data.job_counts);
            }

            // Update header count badges
            const runningCount = data.running_jobs ? data.running_jobs.length : 0;
            const completedCount = data.completed_jobs ? data.completed_jobs.length : 0;
            this.updateHeaderCounts(runningCount, completedCount);

            // Only show success toast if explicitly requested
            if (showSuccessToast) {
                this.showToastNotification('Display refreshed!', 'success');
            }

        } catch (error) {
            console.error('Error refreshing display:', error);
            if (showSuccessToast) { // Only show error toast if user initiated the action
                this.showToastNotification('Error refreshing display', 'error');
            }
        } finally {
            this.updateJobsInProgress = false;
        }
    }

    /**
     * Force refresh - bypasses all caches (used by "Refresh Now" button)
     * @param {boolean} showSuccessToast - Whether to show the success toast notification
     */
    async refreshNow(showSuccessToast = false) {
        if (this.updateJobsInProgress) return;
        this.updateJobsInProgress = true;

        const refreshBtn = document.getElementById('refreshNowBtn');
        const icon = refreshBtn.querySelector('.refresh-icon');
        const spinner = refreshBtn.querySelector('.refresh-spinner');

        icon.classList.add('d-none');
        spinner.classList.remove('d-none');

        try {
            console.log('Fetching fresh job data (bypassing cache)...');
            const response = await fetch('/api/pipeline/get-job-data/?force_refresh=true', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Cache-Control': 'no-cache', // Also prevent browser caching
                    'Pragma': 'no-cache'
                }
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            console.log('Received fresh job data from server (bypassed cache):', data);

            // Update data source indicator
            this.updateDataSourceIndicator(false, false); // Always fresh from database

            if (data.running_jobs) {
                console.log(`Found ${data.running_jobs.length} running jobs`);
                this.updateRunningJobsTable(data.running_jobs);
            } else {
                console.warn('No running_jobs data in response:', data);
            }

            // Update completed jobs table if data is available
            if (data.completed_jobs) {
                console.log(`Found ${data.completed_jobs.length} completed jobs`);
                this.updateCompletedJobsTable(data.completed_jobs);
            } else {
                console.warn('No completed_jobs data in response:', data);
            }

            if (data.job_counts) {
                console.log('Updating job counts:', data.job_counts);
                this.updateJobStatistics(data.job_counts);
            }

            // Update header count badges
            const runningCount = data.running_jobs ? data.running_jobs.length : 0;
            const completedCount = data.completed_jobs ? data.completed_jobs.length : 0;
            this.updateHeaderCounts(runningCount, completedCount);

            // Only show success toast if explicitly requested
            if (showSuccessToast) {
                this.showToastNotification('Page refreshed with latest data!', 'success');
            }

        } catch (error) {
            console.error('Error updating jobs:', error);
            this.showToastNotification('Error updating jobs', 'error');
        } finally {
            icon.classList.remove('d-none');
            spinner.classList.add('d-none');
            this.updateJobsInProgress = false;
        }
    }

    /**
     * Updates the running jobs table with the provided jobs data
     * @param {Array} jobs - Array of job objects from running_jobs table
     */
    updateRunningJobsTable(jobs) {
        console.log('Updating running jobs table with data:', jobs);

        // Update pagination data
        this.pagination.running.data = jobs || [];
        this.pagination.running.totalItems = jobs ? jobs.length : 0;

        // Update pagination UI and render table
        this.updatePagination('running');
        this.renderTable('running');

        console.log('Finished updating running jobs table');
    }

    /**
     * Updates the completed jobs table with the provided jobs data
     * @param {Array} jobs - Array of job objects from completed_jobs table
     */
    updateCompletedJobsTable(jobs) {
        console.log('Updating completed jobs table with data:', jobs);

        // Update pagination data
        this.pagination.completed.data = jobs || [];
        this.pagination.completed.totalItems = jobs ? jobs.length : 0;

        // Update pagination UI and render table
        this.updatePagination('completed');
        this.renderTable('completed');

        console.log('Finished updating completed jobs table');
    }

    /**
     * Update header count badges for running and completed jobs
     * @param {number} runningCount - Number of running jobs
     * @param {number} completedCount - Number of completed jobs
     */
    updateHeaderCounts(runningCount, completedCount) {
        console.log(`Updating header counts: Running=${runningCount}, Completed=${completedCount}`);

        // Update running jobs header badge
        const runningJobsBadge = document.querySelector('.card-header .badge.bg-light.text-primary');
        if (runningJobsBadge) {
            runningJobsBadge.textContent = runningCount || 0;
            console.log('Updated running jobs header badge');
        } else {
            console.warn('Running jobs header badge not found');
        }

        // Update completed jobs header badge
        const completedJobsBadge = document.querySelector('.card-header .badge.bg-light.text-success');
        if (completedJobsBadge) {
            completedJobsBadge.textContent = completedCount || 0;
            console.log('Updated completed jobs header badge');
        } else {
            console.warn('Completed jobs header badge not found');
        }
    }

    formatDate(dateString) {
        if (!dateString) return 'N/A';

        const date = new Date(dateString);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });
    }

    /**
     * Check status of a specific job
     */
    async checkJobStatus(demandId) {
        console.log(`Checking job status for demand ID: ${demandId}`);

        if (!demandId) {
            console.error('No demand ID provided for job status check');
            this.showToastNotification('Missing demand ID for job status check', 'error');
            return;
        }

        // Show loading state on the button
        const statusButton = document.querySelector(`.check-status-btn[data-demand-id="${demandId}"]`);
        if (statusButton) {
            const icon = statusButton.querySelector('i');
            if (icon) {
                icon.className = 'spinner-border spinner-border-sm';
            }
            statusButton.disabled = true;
        }

        try {
            const jobRow = document.querySelector(`tr[data-demand-id="${demandId}"]`);
            if (!jobRow) {
                console.warn(`No job row found for demand ID: ${demandId}`);
                // Continue anyway as the job might exist in the database but not in the UI
            } else {
                console.log(`Found job row for demand ID: ${demandId}`, jobRow);
            }

            console.log(`Sending status check request for demand ID: ${demandId}`);
            const response = await fetch(`/api/pipeline/check-job-status/${demandId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            console.log(`Received response status: ${response.status}`);
            if (!response.ok) {
                throw new Error(`Network response error: ${response.status} ${response.statusText}`);
            }

            const data = await response.json();
            console.log(`Job status data:`, data);

            if (data.status === 'success') {
                const status = data.job_status || 'UNKNOWN';
                const demandType = data.demand_type || 'align';
                console.log(`Job status: ${status}, type: ${demandType}`);

                // Show a different message based on job status
                if (status === 'COMPLETED' || status === 'Completed') {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job completed successfully`, 'success');
                } else if (status === 'FAILED') {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job failed`, 'error');
                } else if (status === 'ABORTED') {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job was aborted`, 'warning');
                } else {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job status: ${status}`, 'info');
                }

                // If job is complete, refresh data to reflect changes
                if (['COMPLETED', 'FAILED', 'ABORTED'].includes(status)) {
                    console.log('Job is complete, refreshing job data to reflect changes');

                    // Don't manually remove the row - let refreshNow handle the table update
                    // This prevents race conditions where we remove the job but then it gets re-added
                    // from stale cached data

                    // Immediately refresh data to get the updated job lists
                    // The backend should have moved the job from running to completed/failed
                    await this.refreshNow();
                }
            } else {
                console.error('Error in job status check:', data.message);
                this.showToastNotification(`Error checking job status: ${data.message}`, 'error');
            }

        } catch (error) {
            console.error('Error checking job status:', error);
            this.showToastNotification(`Error checking job status: ${error.message}`, 'error');
        } finally {
            // Reset button state
            if (statusButton) {
                const icon = statusButton.querySelector('i');
                if (icon) {
                    icon.className = 'bi bi-arrow-clockwise';
                }
                statusButton.disabled = false;
            }
        }
    }

    /**
     * Show stop job confirmation modal
     */
    showStopJobConfirmation(demandId) {
        console.log('Showing stop job confirmation for demand ID:', demandId);

        const jobRow = document.querySelector(`tr[data-demand-id="${demandId}"]`);
        if (!jobRow) {
            console.error('Job row not found for demand ID:', demandId);
            this.showToastNotification('Job not found in the table.', 'error');
            return;
        }

        console.log('Found job row:', jobRow);
        // Get FASTQ name from the first cell
        const fastqName = jobRow.cells[0]?.textContent.trim() || '[Unknown]';
        // Get command from the second cell (index 1) which contains the command
        const commandCell = jobRow.cells[1];
        if (!commandCell) {
            console.error('Command cell not found in job row');
            this.showToastNotification('Could not find job command.', 'error');
            return;
        }
        const commandElement = commandCell.querySelector('code');
        if (!commandElement) {
            console.error('Command code element not found in cell');
            this.showToastNotification('Could not find job command.', 'error');
            return;
        }
        const command = commandElement.textContent;
        console.log('Job command:', command);

        // Construct the abort command for display
        const abortCommand = `ocs core gwo demand stop --demand-id ${demandId}`;
        console.log('Abort command:', abortCommand);

        const jobInfo = document.querySelector('#confirmStopModal .job-info');
        if (!jobInfo) {
            console.error('Job info element not found in modal');
            return;
        }

        jobInfo.innerHTML = `
            <div class="alert alert-warning">
                <p class="mb-2">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    <strong>Warning:</strong> This action will abort the following job and cannot be undone.
                </p>
                <div class="mb-2"><strong>FASTQ Name:</strong> <span class="text-monospace">${fastqName}</span></div>
                <div class="mb-2"><strong>Abort Command:</strong>
                    <div class="bg-light p-2 rounded"><code class="text-wrap">${abortCommand}</code></div>
                        </div>
                <div><strong>Original Job Command:</strong>
                    <div class="bg-light p-2 rounded"><code class="text-wrap">${command}</code></div>
                </div>
            </div>
        `;

        const confirmBtn = document.getElementById('confirmStopBtn');
        if (!confirmBtn) {
            console.error('Confirm stop button not found in modal');
            return;
        }

        confirmBtn.setAttribute('data-demand-id', demandId);
        console.log('Set demand ID on confirm button:', demandId);

        const modal = new bootstrap.Modal(document.getElementById('confirmStopModal'));
        modal.show();
        console.log('Stop job confirmation modal shown');
    }

    /**
     * Stop a running job
     */
    async stopJob(demandId) {
        console.log('Attempting to stop job with demand ID:', demandId);

        try {
            const jobRow = document.querySelector(`tr[data-demand-id="${demandId}"]`);
            if (!jobRow) {
                console.error('Job row not found for demand ID:', demandId);
                this.showToastNotification('Job not found in the table.', 'error');
                return;
            }

            // Get fastq name from the first cell
            const fastqName = jobRow.cells[0].textContent.trim();
            console.log('Found FASTQ name:', fastqName);

            // Get job type (based on command in second cell)
            let jobType = 'alignment';
            const command = jobRow.cells[1].querySelector('code').textContent.trim();
            if (command.includes('post-align')) {
                jobType = 'post-QC';
            }
            console.log('Job type determined as:', jobType);

            // Show loading state on the button
            const stopButton = jobRow.querySelector('.stop-job-btn');
            if (stopButton) {
                const icon = stopButton.querySelector('i');
                if (icon) {
                    icon.className = 'spinner-border spinner-border-sm';
                }
                stopButton.disabled = true;
            }

            console.log('Sending stop job request to server...');
            const response = await fetch(`/api/pipeline/stop-job/${demandId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken'),
                },
                body: JSON.stringify({ fastq_name: fastqName })
            });

            console.log('Received response:', response.status);
            const data = await response.json();
            console.log('Response data:', data);

            // Reset button state
            if (stopButton) {
                const icon = stopButton.querySelector('i');
                if (icon) {
                    icon.className = 'bi bi-stop-fill';
                }
                stopButton.disabled = false;
            }

            if (response.ok) {
                console.log('Job stopped successfully');
                this.showToastNotification(`${jobType} job for ${fastqName} has been aborted`, 'success');

                // If there was a warning but still successful
                if (data.warning) {
                    console.warn('Warning when stopping job:', data.warning);
                    this.showToastNotification(`Warning: ${data.warning}`, 'warning');
                }

                // Remove the row and refresh data
                jobRow.remove();
                await this.refreshNow();
            } else {
                console.error('Failed to stop job:', data.message);
                this.showToastNotification(`Failed to abort ${jobType} job: ${data.message}`, 'error');
            }
        } catch (error) {
            console.error('Error stopping job:', error);
            this.showToastNotification(`Error stopping job: ${error.message}`, 'error');

            // Reset any loading buttons
            const stopButton = document.querySelector(`.stop-job-btn[data-demand-id="${demandId}"]`);
            if (stopButton) {
                const icon = stopButton.querySelector('i');
                if (icon) {
                    icon.className = 'bi bi-stop-fill';
                }
                stopButton.disabled = false;
            }
        }
    }

    /**
     * Shows a toast notification
     */
    showToastNotification(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = 'material-toast';
        toast.innerHTML = `
            <div class="material-toast-icon">
                <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : 'info-circle'}"></i>
            </div>
            <div class="material-toast-message">
                ${message}
            </div>
        `;

        document.body.appendChild(toast);

        // Show toast with slight delay for better animation
        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        // Remove toast after delay
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, duration);
    }

    /**
     * Initialize pagination controls for both tables
     */
    initializePagination() {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('Initializing pagination controls...');

            // Initialize pagination for both tables
            this.setupPaginationControls('running');
            this.setupPaginationControls('completed');

            // Get initial data and set up pagination
            this.loadInitialTableData();
        });
    }

    /**
     * Set up pagination controls for a specific table
     * @param {string} tableType - 'running' or 'completed'
     */
    setupPaginationControls(tableType) {
        // Navigation buttons
        document.querySelectorAll(`[data-table="${tableType}"][data-pagination-action]`).forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const action = button.dataset.paginationAction;
                this.handlePaginationAction(tableType, action, button);
            });
        });

        // Per-page dropdown items
        document.querySelectorAll(`[data-table="${tableType}"][data-per-page]`).forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const perPage = parseInt(item.dataset.perPage);
                this.changePerPage(tableType, perPage);
            });
        });

        // Go to page button
        const gotoBtn = document.querySelector(`[data-table="${tableType}"].goto-btn`);
        if (gotoBtn) {
            gotoBtn.addEventListener('click', () => {
                const input = document.getElementById(`${tableType}-goto-page`);
                if (input) {
                    const page = parseInt(input.value);
                    this.goToPage(tableType, page);
                }
            });
        }

        // Go to page input (Enter key)
        const gotoInput = document.getElementById(`${tableType}-goto-page`);
        if (gotoInput) {
            gotoInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    const page = parseInt(e.target.value);
                    this.goToPage(tableType, page);
                }
            });
        }
    }

    /**
     * Handle pagination action (first, prev, next, last)
     * @param {string} tableType - 'running' or 'completed'
     * @param {string} action - 'first', 'prev', 'next', 'last'
     * @param {HTMLElement} button - The clicked button
     */
    handlePaginationAction(tableType, action, button) {
        const pagination = this.pagination[tableType];
        let newPage = pagination.currentPage;

        switch (action) {
            case 'first':
                newPage = 1;
                break;
            case 'prev':
                newPage = Math.max(1, pagination.currentPage - 1);
                break;
            case 'next':
                newPage = Math.min(pagination.totalPages, pagination.currentPage + 1);
                break;
            case 'last':
                newPage = pagination.totalPages;
                break;
        }

        if (newPage !== pagination.currentPage) {
            this.goToPage(tableType, newPage);
        }
    }

    /**
     * Change items per page for a table
     * @param {string} tableType - 'running' or 'completed'
     * @param {number} perPage - New items per page
     */
    changePerPage(tableType, perPage) {
        const pagination = this.pagination[tableType];
        pagination.perPage = perPage;
        pagination.currentPage = 1; // Reset to first page

        // Update dropdown button text
        const dropdownBtn = document.getElementById(`${tableType}-per-page-btn`);
        if (dropdownBtn) {
            dropdownBtn.textContent = perPage;
        }

        // Update active state in dropdown
        document.querySelectorAll(`[data-table="${tableType}"][data-per-page]`).forEach(item => {
            item.classList.remove('active');
            if (parseInt(item.dataset.perPage) === perPage) {
                item.classList.add('active');
            }
        });

        this.updatePagination(tableType);
        this.renderTable(tableType);
    }

    /**
     * Go to a specific page
     * @param {string} tableType - 'running' or 'completed'
     * @param {number} page - Page number to go to
     */
    goToPage(tableType, page) {
        const pagination = this.pagination[tableType];

        if (page < 1 || page > pagination.totalPages) {
            this.showToastNotification(`Page ${page} is out of range (1-${pagination.totalPages})`, 'error');
            return;
        }

        pagination.currentPage = page;
        this.updatePagination(tableType);
        this.renderTable(tableType);
    }

    /**
     * Update pagination UI elements
     * @param {string} tableType - 'running' or 'completed'
     */
    updatePagination(tableType) {
        const pagination = this.pagination[tableType];

        // Calculate total pages
        pagination.totalPages = Math.max(1, Math.ceil(pagination.totalItems / pagination.perPage));

        // Ensure current page is within bounds
        pagination.currentPage = Math.min(pagination.currentPage, pagination.totalPages);

        // Update page indicator
        const currentPageEl = document.getElementById(`${tableType}-current-page`);
        const totalPagesEl = document.getElementById(`${tableType}-total-pages`);
        if (currentPageEl) currentPageEl.textContent = pagination.currentPage;
        if (totalPagesEl) totalPagesEl.textContent = pagination.totalPages;

        // Update goto input
        const gotoInput = document.getElementById(`${tableType}-goto-page`);
        if (gotoInput) {
            gotoInput.value = pagination.currentPage;
            gotoInput.max = pagination.totalPages;
        }

        // Update navigation buttons
        const firstBtn = document.querySelector(`[data-table="${tableType}"][data-pagination-action="first"]`);
        const prevBtn = document.querySelector(`[data-table="${tableType}"][data-pagination-action="prev"]`);
        const nextBtn = document.querySelector(`[data-table="${tableType}"][data-pagination-action="next"]`);
        const lastBtn = document.querySelector(`[data-table="${tableType}"][data-pagination-action="last"]`);

        const isFirstPage = pagination.currentPage === 1;
        const isLastPage = pagination.currentPage === pagination.totalPages;

        if (firstBtn) {
            firstBtn.disabled = isFirstPage;
            firstBtn.classList.toggle('disabled', isFirstPage);
        }
        if (prevBtn) {
            prevBtn.disabled = isFirstPage;
            prevBtn.classList.toggle('disabled', isFirstPage);
        }
        if (nextBtn) {
            nextBtn.disabled = isLastPage;
            nextBtn.classList.toggle('disabled', isLastPage);
        }
        if (lastBtn) {
            lastBtn.disabled = isLastPage;
            lastBtn.classList.toggle('disabled', isLastPage);
        }

        // Update pagination info
        const startItem = (pagination.currentPage - 1) * pagination.perPage + 1;
        const endItem = Math.min(pagination.currentPage * pagination.perPage, pagination.totalItems);
        const paginationInfo = document.getElementById(`${tableType}-pagination-info`);
        if (paginationInfo) {
            if (pagination.totalItems === 0) {
                paginationInfo.textContent = `No results to display`;
            } else {
                paginationInfo.textContent = `Results ${startItem}-${endItem} of ${pagination.totalItems}`;
            }
        }
    }

    /**
     * Load initial table data from DOM
     */
    loadInitialTableData() {
        // Load running jobs data
        const runningJobsTable = document.querySelector('#running-jobs-table tbody');
        if (runningJobsTable) {
            const rows = runningJobsTable.querySelectorAll('tr');
            const runningJobs = [];

            rows.forEach(row => {
                if (!row.querySelector('.alert-info')) {  // Skip the "no jobs" message row
                    const job = {
                        fastq_name: row.cells[0].textContent.trim(),
                        command: row.cells[1].querySelector('code')?.textContent.trim() || '',
                        demand_id: row.cells[2].querySelector('.text-monospace')?.textContent.trim() || '',
                        attempts: row.cells[3].textContent.trim(),
                        time: row.cells[4].textContent.trim()
                    };
                    runningJobs.push(job);
                }
            });

            this.pagination.running.data = runningJobs;
            this.pagination.running.totalItems = runningJobs.length;
            this.updatePagination('running');
            this.renderTable('running');
        }

        // Load completed jobs data
        const completedJobsTable = document.querySelector('#completed-jobs-table tbody');
        if (completedJobsTable) {
            const rows = completedJobsTable.querySelectorAll('tr');
            const completedJobs = [];

            rows.forEach(row => {
                if (!row.querySelector('.alert-info')) {
                    let workflow = '';
                    const workflowBadge = row.cells[1]?.querySelector('.workflow-badge');
                    if (workflowBadge) {
                        workflow = workflowBadge.textContent.trim();
                    }

                    // Extract alignment demand ID
                    const alignmentDemandCell = row.cells[2];
                    let alignmentDemandId = '';
                    if (alignmentDemandCell && !alignmentDemandCell.textContent.includes('-')) {
                        const demandSpan = alignmentDemandCell.querySelector('.text-monospace');
                        if (demandSpan) {
                            alignmentDemandId = demandSpan.textContent.trim();
                        }
                    }

                    // Extract alignment status
                    let alignmentStatus = '';
                    const alignmentStatusCell = row.cells[3];
                    if (alignmentStatusCell) {
                        const statusBadge = alignmentStatusCell.querySelector('.badge');
                        if (statusBadge) {
                            alignmentStatus = statusBadge.textContent.trim();
                        }
                    }

                    // Extract post-QC demand ID
                    const postqcDemandCell = row.cells[4];
                    let postqcDemandId = '';
                    if (postqcDemandCell && !postqcDemandCell.textContent.includes('-')) {
                        const demandSpan = postqcDemandCell.querySelector('.text-monospace');
                        if (demandSpan) {
                            postqcDemandId = demandSpan.textContent.trim();
                        }
                    }

                    // Extract post-QC status
                    let postqcStatus = 'Not Started';
                    const postqcStatusCell = row.cells[5];
                    if (postqcStatusCell) {
                        const statusBadge = postqcStatusCell.querySelector('.badge');
                        if (statusBadge) {
                            postqcStatus = statusBadge.textContent.trim();
                        }
                    }

                    const job = {
                        fastq_name: row.cells[0].textContent.trim(),
                        workflow: workflow,
                        alignment_demand_id: alignmentDemandId,
                        alignment_status: alignmentStatus,
                        postqc_demand_id: postqcDemandId,
                        postqc_status: postqcStatus,
                        total_duration: row.cells[6]?.textContent.trim() || '0',
                        latest_update: row.cells[7]?.textContent.trim() || 'N/A'
                    };
                    completedJobs.push(job);
                }
            });

            this.pagination.completed.data = completedJobs;
            this.pagination.completed.totalItems = completedJobs.length;
            this.updatePagination('completed');
            this.renderTable('completed');
        }
    }

    /**
     * Render table with pagination
     * @param {string} tableType - 'running' or 'completed'
     */
    renderTable(tableType) {
        const pagination = this.pagination[tableType];
        const startIndex = (pagination.currentPage - 1) * pagination.perPage;
        const endIndex = startIndex + pagination.perPage;
        const pageData = pagination.data.slice(startIndex, endIndex);

        if (tableType === 'running') {
            this.renderRunningJobsTable(pageData);
        } else if (tableType === 'completed') {
            this.renderCompletedJobsTable(pageData);
        }
    }

    /**
     * Render running jobs table with paginated data
     * @param {Array} jobs - Jobs to display
     */
    renderRunningJobsTable(jobs) {
        const tableBody = document.querySelector('#running-jobs-table tbody');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        if (jobs.length === 0) {
            const noJobsRow = document.createElement('tr');
            noJobsRow.innerHTML = `
                <td colspan="6" class="text-center">
                    <div class="alert alert-info mb-0">
                        <i class="bi bi-info-circle-fill me-2"></i>
                        No jobs are currently running.
                    </div>
                </td>
            `;
            tableBody.appendChild(noJobsRow);
            return;
        }

        jobs.forEach(job => {
            const row = document.createElement('tr');
            row.className = 'running-job';
            row.dataset.demandId = job.demand_id;

            // Format time properly
            const formattedTime = job.time ? this.formatDate(job.time) : 'N/A';

            row.innerHTML = `
                <td class="field-fastq_name">${job.fastq_name}</td>
                <td class="field-command">
                    <div class="text-wrap" style="max-width: 500px;">
                        <code class="small">${job.command || 'N/A'}</code>
                    </div>
                </td>
                <td class="demand-id-cell">
                    <span class="text-monospace">${job.demand_id}</span>
                </td>
                <td data-field="attempts">${job.attempts || 0}</td>
                <td data-field="time">${formattedTime}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary check-status-btn" data-demand-id="${job.demand_id}">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger stop-job-btn" data-demand-id="${job.demand_id}">
                        <i class="bi bi-stop-fill"></i>
                    </button>
                </td>
            `;

            // Add event listeners for the new row's buttons
            const checkStatusBtn = row.querySelector('.check-status-btn');
            if (checkStatusBtn) {
                checkStatusBtn.addEventListener('click', () => this.checkJobStatus(job.demand_id));
            }

            const stopJobBtn = row.querySelector('.stop-job-btn');
            if (stopJobBtn) {
                stopJobBtn.addEventListener('click', () => this.showStopJobConfirmation(job.demand_id));
            }

            tableBody.appendChild(row);
        });

        // Reinitialize copy-to-clipboard functionality
        this.initializeCopyToClipboard();
    }

    /**
     * Render completed jobs table with paginated data
     * @param {Array} jobs - Jobs to display
     */
    renderCompletedJobsTable(jobs) {
        const tableBody = document.querySelector('#completed-jobs-table tbody');
        if (!tableBody) return;

        tableBody.innerHTML = '';

        if (jobs.length === 0) {
            const noJobsRow = document.createElement('tr');
            noJobsRow.innerHTML = `
                <td colspan="9" class="text-center">
                    <div class="alert alert-info mb-0">
                        <i class="bi bi-info-circle-fill me-2"></i>
                        No completed jobs found.
                    </div>
                </td>
            `;
            tableBody.appendChild(noJobsRow);
            return;
        }

        // Process jobs: add calculated fields and sort by latest update
        const processedJobs = jobs.map(job => {
            // Determine workflow from batch name
            let workflow = 'RTX'; // default
            const batch = job.batch_name_from_vendor || '';
            if (batch.includes('MTX')) {
                workflow = 'MTX';
            }

            // Calculate total duration in minutes
            let totalDuration = 0;
            if (job.alignment_start_time && job.alignment_end_time) {
                const alignStart = new Date(job.alignment_start_time);
                const alignEnd = new Date(job.alignment_end_time);
                totalDuration += (alignEnd - alignStart) / (1000 * 60); // convert to minutes
            }
            if (job.postqc_start_time && job.postqc_end_time) {
                const postStart = new Date(job.postqc_start_time);
                const postEnd = new Date(job.postqc_end_time);
                totalDuration += (postEnd - postStart) / (1000 * 60); // convert to minutes
            }
            totalDuration = Math.round(totalDuration);

            // Determine latest update time
            let latestUpdate = null;
            const times = [job.alignment_end_time, job.postqc_end_time, job.alignment_start_time, job.postqc_start_time].filter(t => t);
            if (times.length > 0) {
                latestUpdate = times.sort((a, b) => new Date(b) - new Date(a))[0];
            }

            return {
                ...job,
                workflow: workflow,
                total_duration: totalDuration,
                latest_update: latestUpdate
            };
        });

        // Sort by latest update time (most recent first)
        processedJobs.sort((a, b) => {
            const timeA = a.latest_update || '-';
            const timeB = b.latest_update || '-';
            return new Date(timeB) - new Date(timeA);
        });

        processedJobs.forEach(job => {
            const row = document.createElement('tr');
            row.dataset.alignmentDemandId = job.alignment_demand_id || '';
            row.dataset.postqcDemandId = job.postqc_demand_id || '';

            // Create alignment status badge
            let alignmentStatusHtml = '';
            const alignmentStatus = job.alignment_status || 'Not Started';
            if (alignmentStatus === 'COMPLETED' || alignmentStatus === 'Completed') {
                const alignmentEndTime = job.alignment_end_time ? this.formatDate(job.alignment_end_time) : '';
                alignmentStatusHtml = `
                    <span class="badge bg-success" title="Alignment completed at ${alignmentEndTime}">
                        <i class="bi bi-check-circle-fill me-1"></i>Completed
                    </span>
                `;
            } else if (alignmentStatus === 'FAILED') {
                alignmentStatusHtml = `
                    <span class="badge bg-danger" title="Alignment failed">
                        <i class="bi bi-x-circle-fill me-1"></i>Failed
                    </span>
                `;
            } else if (alignmentStatus === 'ABORTED') {
                alignmentStatusHtml = `
                    <span class="badge bg-secondary" title="Alignment aborted">
                        <i class="bi bi-stop-circle-fill me-1"></i>Aborted
                    </span>
                `;
            } else if (alignmentStatus && alignmentStatus !== 'Not Started') {
                alignmentStatusHtml = `
                    <span class="badge bg-warning text-dark" title="Alignment status: ${alignmentStatus}">
                        <i class="bi bi-clock-fill me-1"></i>${alignmentStatus}
                    </span>
                `;
            } else {
                alignmentStatusHtml = `
                    <span class="badge bg-light text-muted" title="Alignment not started">
                        <i class="bi bi-circle me-1"></i>Not Started
                    </span>
                `;
            }

            // Create post-QC status badge
            let postqcStatusHtml = '';
            const postqcStatus = job.postqc_status || 'Not Started';
            if (postqcStatus === 'COMPLETED' || postqcStatus === 'Completed') {
                const postqcEndTime = job.postqc_end_time ? this.formatDate(job.postqc_end_time) : '';
                postqcStatusHtml = `
                    <span class="badge bg-success" title="Post-QC completed at ${postqcEndTime}">
                        <i class="bi bi-check-circle-fill me-1"></i>Completed
                    </span>
                `;
            } else if (postqcStatus === 'FAILED') {
                postqcStatusHtml = `
                    <span class="badge bg-danger" title="Post-QC failed">
                        <i class="bi bi-x-circle-fill me-1"></i>Failed
                    </span>
                `;
            } else if (postqcStatus === 'ABORTED') {
                postqcStatusHtml = `
                    <span class="badge bg-secondary" title="Post-QC aborted">
                        <i class="bi bi-stop-circle-fill me-1"></i>Aborted
                    </span>
                `;
            } else if (postqcStatus && postqcStatus !== 'Not Started') {
                postqcStatusHtml = `
                    <span class="badge bg-warning text-dark" title="Post-QC status: ${postqcStatus}">
                        <i class="bi bi-clock-fill me-1"></i>${postqcStatus}
                    </span>
                `;
            } else {
                postqcStatusHtml = `
                    <span class="badge bg-light text-muted" title="Post-QC not started">
                        <i class="bi bi-circle me-1"></i>Not Started
                    </span>
                `;
            }

            // Format latest update time
            const formattedLatestUpdate = job.latest_update ? this.formatDate(job.latest_update) : 'N/A';

            row.innerHTML = `
                <td class="field-fastq_name">${job.fastq_name}</td>
                <td>
                    <span class="badge workflow-badge ${job.workflow === 'MTX' ? 'badge-mtx' : 'bg-primary'}">
                        ${job.workflow}
                    </span>
                </td>
                <td class="alignment-status-cell">
                    ${alignmentStatusHtml}
                </td>
                <td class="postqc-status-cell">
                    ${postqcStatusHtml}
                </td>
                <td class="demand-id-cell">
                    ${job.alignment_demand_id ?
                    `<span class="text-monospace small">${job.alignment_demand_id}</span>` :
                    `<span class="text-muted">-</span>`
                }
                </td>
                <td class="demand-id-cell">
                    ${job.postqc_demand_id ?
                    `<span class="text-monospace small">${job.postqc_demand_id}</span>` :
                    `<span class="text-muted">-</span>`
                }
                </td>
                <td data-field="total_duration">${this.formatDuration(job.total_duration)}</td>
                <td data-field="latest_update">${formattedLatestUpdate}</td>
                <td>
                    <button class="btn btn-sm btn-outline-info job-details-btn" 
                            data-fastq-name="${job.fastq_name}"
                            data-alignment-demand-id="${job.alignment_demand_id || ''}"
                            data-postqc-demand-id="${job.postqc_demand_id || ''}"
                            title="View job details">
                        <i class="bi bi-info-circle"></i>
                    </button>
                </td>
            `;

            // Add event listener for the details button
            const detailsBtn = row.querySelector('.job-details-btn');
            if (detailsBtn) {
                detailsBtn.addEventListener('click', () => {
                    this.showJobDetails(job);
                });
            }

            tableBody.appendChild(row);
        });

        // Reinitialize copy-to-clipboard functionality
        this.initializeCopyToClipboard();
    }

    /**
     * Format duration in minutes to days-hours-minutes format
     * @param {number} totalMinutes - Total duration in minutes
     * @returns {string} Formatted duration string
     */
    formatDuration(totalMinutes) {
        if (!totalMinutes || totalMinutes <= 0) {
            return '0m';
        }

        const days = Math.floor(totalMinutes / (24 * 60));
        const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
        const minutes = Math.floor(totalMinutes % 60);

        const parts = [];
        if (days > 0) parts.push(`${days}d`);
        if (hours > 0) parts.push(`${hours}h`);
        if (minutes > 0) parts.push(`${minutes}m`);

        return parts.length > 0 ? parts.join(' ') : '0m';
    }

    /**
     * Update all running jobs by checking their status with OCS
     */
    async updateAllJobs() {
        if (this.updateJobsInProgress) return;
        this.updateJobsInProgress = true;

        const updateAllJobsBtn = document.getElementById('updateAllJobsBtn');
        const icon = updateAllJobsBtn.querySelector('.refresh-icon');
        const spinner = updateAllJobsBtn.querySelector('.refresh-spinner');

        icon.classList.add('d-none');
        spinner.classList.remove('d-none');

        try {
            console.log('Updating all running jobs status...');
            const response = await fetch('/api/pipeline/update_all_jobs/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            console.log('Update all jobs response:', data);

            if (data.status === 'success') {
                // Show success message with details
                const message = data.message || 'All jobs updated successfully';
                this.showToastNotification(message, 'success');

                // Now refresh the display to show updated data
                await this.refreshNow(false);
            } else {
                throw new Error(data.message || 'Failed to update jobs');
            }

        } catch (error) {
            console.error('Error updating all jobs:', error);
            this.showToastNotification(`Error updating jobs: ${error.message}`, 'error');
        } finally {
            icon.classList.remove('d-none');
            spinner.classList.add('d-none');
            this.updateJobsInProgress = false;
        }
    }

    /**
     * Show job details in a modal
     * @param {Object} job - Job object with details
     */
    showJobDetails(job) {
        console.log('Showing job details for:', job.fastq_name);

        // Create details modal if it doesn't exist
        let detailsModal = document.getElementById('jobDetailsModal');
        if (!detailsModal) {
            const modalHtml = `
                <div class="modal fade" id="jobDetailsModal" tabindex="-1" aria-labelledby="jobDetailsModalLabel" aria-hidden="true">
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header bg-primary text-white">
                                <h5 class="modal-title text-white" id="jobDetailsModalLabel" style="color: white !important;">
                                    <i class="bi bi-info-circle-fill me-2" style="color: white !important;"></i>
                                    Job Details
                                </h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
                            </div>
                            <div class="modal-body">
                                <div id="jobDetailsContent">
                                    <!-- Content will be populated by JavaScript -->
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            detailsModal = document.getElementById('jobDetailsModal');
        }

        // Populate modal content
        const content = document.getElementById('jobDetailsContent');
        const alignmentEndTime = job.alignment_end_time ? this.formatDate(job.alignment_end_time) : 'N/A';
        const alignmentStartTime = job.alignment_start_time ? this.formatDate(job.alignment_start_time) : 'N/A';
        const postqcEndTime = job.postqc_end_time ? this.formatDate(job.postqc_end_time) : 'N/A';
        const postqcStartTime = job.postqc_start_time ? this.formatDate(job.postqc_start_time) : 'N/A';

        // Calculate individual durations
        let alignmentDuration = 0;
        if (job.alignment_start_time && job.alignment_end_time) {
            const start = new Date(job.alignment_start_time);
            const end = new Date(job.alignment_end_time);
            alignmentDuration = Math.round((end - start) / (1000 * 60));
        }

        let postqcDuration = 0;
        if (job.postqc_start_time && job.postqc_end_time) {
            const start = new Date(job.postqc_start_time);
            const end = new Date(job.postqc_end_time);
            postqcDuration = Math.round((end - start) / (1000 * 60));
        }

        const totalDuration = alignmentDuration + postqcDuration;

        content.innerHTML = `
            <div class="row">
                <div class="col-12 mb-3">
                    <div class="card h-100">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="bi bi-file-earmark-text me-2"></i>General Information</h6>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-md-6">
                                    <strong>FASTQ Name:</strong> <span class="text-monospace">${job.fastq_name}</span>
                                </div>
                                <div class="col-md-6">
                                    <strong>Workflow:</strong> 
                                    <span class="badge ${job.workflow === 'MTX' ? 'badge-mtx' : 'bg-primary'}">${job.workflow || 'RTX'}</span>
                                </div>
                                <div class="col-md-6 mt-2">
                                    <strong>Organism:</strong> ${job.organism_common_name || 'Unknown'}
                                </div>
                                <div class="col-md-6 mt-2">
                                    <strong>Batch:</strong> ${job.batch_name_from_vendor || 'Unknown'}
                                </div>
                                <div class="col-12 mt-2">
                                    <strong>Total Duration:</strong> ${this.formatDuration(totalDuration)}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row">
                <div class="col-md-6 mb-3">
                    <div class="card h-100">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="bi bi-cpu me-2"></i>Alignment Job</h6>
                        </div>
                        <div class="card-body">
                            <div class="mb-2">
                                <strong>Status:</strong> 
                                ${job.alignment_status === 'COMPLETED' || job.alignment_status === 'Completed' ?
                '<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Completed</span>' :
                job.alignment_status === 'FAILED' ?
                    '<span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>Failed</span>' :
                    job.alignment_status === 'ABORTED' ?
                        '<span class="badge bg-secondary"><i class="bi bi-stop-circle-fill me-1"></i>Aborted</span>' :
                        job.alignment_status && job.alignment_status !== 'Not Started' ?
                            `<span class="badge bg-warning text-dark"><i class="bi bi-clock-fill me-1"></i>${job.alignment_status}</span>` :
                            '<span class="badge bg-light text-muted"><i class="bi bi-circle me-1"></i>Not Started</span>'
            }
                            </div>
                            ${job.alignment_demand_id ? `
                                <div class="mb-2">
                                    <strong>Demand ID:</strong> 
                                    <span class="text-monospace small">${job.alignment_demand_id}</span>
                                </div>
                            ` : ''}
                            <div class="mb-2">
                                <strong>Start Time:</strong> ${alignmentStartTime}
                            </div>
                            <div class="mb-2">
                                <strong>End Time:</strong> ${alignmentEndTime}
                            </div>
                            <div class="mb-2">
                                <strong>Duration:</strong> ${this.formatDuration(alignmentDuration)}
                            </div>
                            <div class="mb-2">
                                <strong>Attempts:</strong> ${job.alignment_attempts || 0}
                            </div>
                            ${job.alignment_command ? `
                                <div class="mt-3">
                                    <strong>Command:</strong>
                                    <div class="bg-light p-2 rounded mt-1">
                                        <code class="small text-wrap">${job.alignment_command}</code>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>

                <div class="col-md-6 mb-3">
                    <div class="card h-100">
                        <div class="card-header">
                            <h6 class="mb-0"><i class="bi bi-clipboard-check me-2"></i>Post-QC Job</h6>
                        </div>
                        <div class="card-body">
                            <div class="mb-2">
                                <strong>Status:</strong> 
                                ${job.postqc_status === 'COMPLETED' || job.postqc_status === 'Completed' ?
                '<span class="badge bg-success"><i class="bi bi-check-circle-fill me-1"></i>Completed</span>' :
                job.postqc_status === 'FAILED' ?
                    '<span class="badge bg-danger"><i class="bi bi-x-circle-fill me-1"></i>Failed</span>' :
                    job.postqc_status === 'ABORTED' ?
                        '<span class="badge bg-secondary"><i class="bi bi-stop-circle-fill me-1"></i>Aborted</span>' :
                        job.postqc_status && job.postqc_status !== 'Not Started' ?
                            `<span class="badge bg-warning text-dark"><i class="bi bi-clock-fill me-1"></i>${job.postqc_status}</span>` :
                            '<span class="badge bg-light text-muted"><i class="bi bi-circle me-1"></i>Not Started</span>'
            }
                            </div>
                            ${job.postqc_demand_id ? `
                                <div class="mb-2">
                                    <strong>Demand ID:</strong> 
                                    <span class="text-monospace small">${job.postqc_demand_id}</span>
                                </div>
                            ` : ''}
                            <div class="mb-2">
                                <strong>Start Time:</strong> ${postqcStartTime}
                            </div>
                            <div class="mb-2">
                                <strong>End Time:</strong> ${postqcEndTime}
                            </div>
                            <div class="mb-2">
                                <strong>Duration:</strong> ${this.formatDuration(postqcDuration)}
                            </div>
                            <div class="mb-2">
                                <strong>Attempts:</strong> ${job.postqc_attempts || 0}
                            </div>
                            ${job.postqc_command ? `
                                <div class="mt-3">
                                    <strong>Command:</strong>
                                    <div class="bg-light p-2 rounded mt-1">
                                        <code class="small text-wrap">${job.postqc_command}</code>
                                    </div>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Show the modal
        const modal = new bootstrap.Modal(detailsModal);
        modal.show();
    }

    /**
     * Extract job data from HTML table row and show job details
     * @param {HTMLElement} row - Table row element
     * @param {string} fastqName - FASTQ name
     * @param {string} alignmentDemandId - Alignment demand ID
     * @param {string} postqcDemandId - Post-QC demand ID
     */
    extractAndShowJobDetails(row, fastqName, alignmentDemandId, postqcDemandId) {
        console.log('Extracting job details from row for:', fastqName);

        // Extract workflow from badge
        let workflow = 'RTX'; // default
        const workflowBadge = row.querySelector('.workflow-badge');
        if (workflowBadge) {
            workflow = workflowBadge.textContent.trim();
        }

        // Extract status information from badges
        let alignmentStatus = 'Not Started';
        const alignmentStatusBadge = row.querySelector('.alignment-status-cell .badge');
        if (alignmentStatusBadge) {
            const badgeText = alignmentStatusBadge.textContent.trim();
            if (badgeText.includes('Completed')) {
                alignmentStatus = 'COMPLETED';
            } else if (badgeText.includes('Failed')) {
                alignmentStatus = 'FAILED';
            } else if (badgeText.includes('Aborted')) {
                alignmentStatus = 'ABORTED';
            } else if (!badgeText.includes('Not Started')) {
                alignmentStatus = badgeText;
            }
        }

        let postqcStatus = 'Not Started';
        const postqcStatusBadge = row.querySelector('.postqc-status-cell .badge');
        if (postqcStatusBadge) {
            const badgeText = postqcStatusBadge.textContent.trim();
            if (badgeText.includes('Completed')) {
                postqcStatus = 'COMPLETED';
            } else if (badgeText.includes('Failed')) {
                postqcStatus = 'FAILED';
            } else if (badgeText.includes('Aborted')) {
                postqcStatus = 'ABORTED';
            } else if (!badgeText.includes('Not Started')) {
                postqcStatus = badgeText;
            }
        }

        // Create job object with available data
        const job = {
            fastq_name: fastqName,
            workflow: workflow,
            alignment_demand_id: alignmentDemandId || null,
            postqc_demand_id: postqcDemandId || null,
            alignment_status: alignmentStatus,
            postqc_status: postqcStatus,
            // For server-rendered rows, we don't have all the detailed timing info
            // The modal will show what's available
            alignment_start_time: null,
            alignment_end_time: null,
            postqc_start_time: null,
            postqc_end_time: null,
            alignment_attempts: 0,
            postqc_attempts: 0,
            alignment_command: null,
            postqc_command: null,
            organism_common_name: 'Unknown',
            batch_name_from_vendor: 'Unknown',
            total_duration: 0
        };

        this.showJobDetails(job);
    }

    /**
     * Update data source indicator
     * @param {boolean} fromCache - Whether data came from cache
     * @param {boolean} isInitial - Whether this is the initial data load
     */
    updateDataSourceIndicator(fromCache, isInitial) {
        const indicatorText = document.getElementById('dataSourceText');
        const indicator = document.getElementById('dataSourceIndicator');

        if (indicatorText && indicator) {
            const now = new Date().toLocaleTimeString();

            if (fromCache) {
                indicatorText.textContent = `Cached data (${now}) - 1min cache`;
                indicator.className = 'text-warning ms-2';
                indicator.querySelector('i').className = 'bi bi-hdd-stack';
                indicator.title = 'Data from cache (up to 1 minute old)';
            } else {
                indicatorText.textContent = `Fresh data (${now}) - Live from DB`;
                indicator.className = 'text-success ms-2';
                indicator.querySelector('i').className = 'bi bi-database-check';
                indicator.title = 'Fresh data from database';
            }

            // Add visual pulse effect for fresh data
            if (!fromCache) {
                indicator.style.animation = 'pulse 1s ease-in-out';
                setTimeout(() => {
                    indicator.style.animation = '';
                }, 1000);
            }
        }
    }
}

// Initialize and export
const jobMonitor = new JobMonitor();
window.jobMonitor = jobMonitor; 