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
            const refreshJobsBtn = document.getElementById('refreshJobsBtn');
            if (refreshJobsBtn) {
                refreshJobsBtn.addEventListener('click', () => this.refreshJobs());
            }

            // Set up update all jobs button
            const updateAllJobsBtn = document.getElementById('updateAllJobsBtn');
            if (updateAllJobsBtn) {
                updateAllJobsBtn.addEventListener('click', () => this.refreshJobs(true));
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
                this.refreshJobs(false);
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
        this.autoRefreshInterval = setInterval(() => {
            this.refreshJobs(false);
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
     * Refreshes all job statuses
     * @param {boolean} showSuccessToast - Whether to show the success toast notification
     */
    async refreshJobs(showSuccessToast = false) {
        if (this.updateJobsInProgress) return;
        this.updateJobsInProgress = true;

        const refreshBtn = document.getElementById('updateAllJobsBtn');
        const icon = refreshBtn.querySelector('.refresh-icon');
        const spinner = refreshBtn.querySelector('.refresh-spinner');

        icon.classList.add('d-none');
        spinner.classList.remove('d-none');

        try {
            console.log('Fetching fresh job data...');
            const response = await fetch('/api/pipeline/get-job-data/', {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                }
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            console.log('Received job data from server:', data);

            if (data.running_jobs) {
                console.log(`Found ${data.running_jobs.length} running jobs`);
                this.updateRunningJobsTable(data.running_jobs);
            } else {
                console.warn('No running_jobs data in response:', data);
            }

            if (data.job_counts) {
                console.log('Updating job counts:', data.job_counts);
                this.updateJobStatistics(data.job_counts);
            }

            // Only show success toast if explicitly requested
            if (showSuccessToast) {
                this.showToastNotification('Jobs updated successfully', 'success');
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
        const tableBody = document.querySelector('#running-jobs-table tbody');
        if (!tableBody) {
            console.error('Could not find running jobs table body');
            return;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        if (!jobs || jobs.length === 0) {
            console.log('No running jobs to display');
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
            console.log('Processing job:', job);

            // The data already has the selected command and demand_id
            const command = job.command;
            const attempts = job.attempts;
            const demandId = job.demand_id;

            console.log('Using values:', {
                command: command,
                attempts: attempts,
                demandId: demandId
            });

            if (!command) {
                console.warn('Job has no command:', job);
                return;
            }

            const row = document.createElement('tr');
            row.className = 'running-job';
            row.dataset.demandId = demandId;

            row.innerHTML = `
                <td>${job.fastq_name}</td>
                <td>
                    <div class="text-wrap" style="max-width: 500px;">
                        <code class="small">${command}</code>
                    </div>
                </td>
                <td class="demand-id-cell">
                    <span class="text-monospace">${demandId}</span>
                </td>
                <td>${attempts}</td>
                <td>${this.formatDate(job.time)}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary check-status-btn" data-demand-id="${demandId}">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger stop-job-btn" data-demand-id="${demandId}">
                        <i class="bi bi-stop-fill"></i>
                    </button>
                </td>
            `;

            // Add event listeners for the new row's buttons
            const checkStatusBtn = row.querySelector('.check-status-btn');
            if (checkStatusBtn) {
                checkStatusBtn.addEventListener('click', () => this.checkJobStatus(demandId));
            }

            const stopJobBtn = row.querySelector('.stop-job-btn');
            if (stopJobBtn) {
                stopJobBtn.addEventListener('click', () => this.showStopJobConfirmation(demandId));
            }

            tableBody.appendChild(row);
        });

        // Reinitialize copy-to-clipboard functionality after updating table
        this.initializeCopyToClipboard();

        console.log('Finished updating running jobs table');
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

        try {
            const jobRow = document.querySelector(`tr[data-demand-id="${demandId}"]`);
            if (!jobRow) {
                console.warn(`No job row found for demand ID: ${demandId}`);
                // Continue anyway as the job might exist in the database but not in the UI
            } else {
                console.log(`Found job row for demand ID: ${demandId}`, jobRow);
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

            // Reset button state
            if (statusButton) {
                const icon = statusButton.querySelector('i');
                if (icon) {
                    icon.className = 'bi bi-arrow-clockwise';
                }
                statusButton.disabled = false;
            }

            if (data.status === 'success') {
                const status = data.job_status || 'UNKNOWN';
                const demandType = data.demand_type || 'align';
                console.log(`Job status: ${status}, type: ${demandType}`);

                // Show a different message based on job status
                if (status === 'COMPLETED') {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job completed successfully`, 'success');
                } else if (status === 'FAILED') {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job failed`, 'error');
                } else if (status === 'ABORTED') {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job was aborted`, 'warning');
                } else {
                    this.showToastNotification(`${demandType === 'align' ? 'Alignment' : 'Post-QC'} job status: ${status}`, 'info');
                }

                // If job is complete, refresh to update the tables
                if (['COMPLETED', 'FAILED', 'ABORTED'].includes(status)) {
                    console.log('Job is complete, refreshing job lists');
                    await this.refreshJobs();
                }
            } else {
                console.error('Error in job status check:', data.message);
                this.showToastNotification(`Error checking job status: ${data.message}`, 'error');
            }

        } catch (error) {
            console.error('Error checking job status:', error);
            this.showToastNotification(`Error checking job status: ${error.message}`, 'error');

            // Reset any loading buttons
            const statusButton = document.querySelector(`.check-status-btn[data-demand-id="${demandId}"]`);
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
                await this.refreshJobs();
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
        // Create toast container if it doesn't exist
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'position-fixed bottom-0 start-50 translate-middle-x mb-4';
            toastContainer.style.zIndex = '1100';
            toastContainer.style.left = '50%';
            toastContainer.style.transform = 'translateX(-50%)';
            toastContainer.style.width = 'auto';
            toastContainer.style.textAlign = 'center';
            document.body.appendChild(toastContainer);
        }

        const toast = document.createElement('div');
        toast.className = `toast align-items-center border-0 ${type === 'error' ? 'bg-danger' : type === 'success' ? 'bg-success' : 'bg-info'} text-white`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        toast.style.minWidth = '250px';
        toast.style.margin = '0 auto';

        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast, { delay: duration });
        bsToast.show();

        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }
}

// Initialize and export
const jobMonitor = new JobMonitor();
window.jobMonitor = jobMonitor; 