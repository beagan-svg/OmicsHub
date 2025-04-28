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
        this.initializeEventListeners();

        // Initialize automatic data fetching
        this.autoRefreshInterval = null;
        this.autoRefreshTime = 30000; // 30 seconds

        // Set progress bar width dynamically
        this.setProgressBarWidth();
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
            // Set up refresh jobs button
            const refreshJobsBtn = document.getElementById('refreshJobsBtn');
            if (refreshJobsBtn) {
                refreshJobsBtn.addEventListener('click', () => this.refreshJobs());
            }

            // Set up update all jobs button
            const updateAllJobsBtn = document.getElementById('updateAllJobsBtn');
            if (updateAllJobsBtn) {
                updateAllJobsBtn.addEventListener('click', () => this.refreshJobs());
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
                confirmStopBtn.addEventListener('click', () => {
                    const demandId = confirmStopBtn.getAttribute('data-demand-id');
                    if (demandId) {
                        this.stopJob(demandId);
                    }
                });
            }

            // Set up check status buttons
            document.addEventListener('click', (e) => {
                // Check status button click
                if (e.target.closest('.check-status-btn')) {
                    const button = e.target.closest('.check-status-btn');
                    const demandId = button.getAttribute('data-demand-id');
                    if (demandId) {
                        this.checkJobStatus(demandId);
                    }
                }

                // Stop job button click
                if (e.target.closest('.stop-job-btn')) {
                    const button = e.target.closest('.stop-job-btn');
                    const demandId = button.getAttribute('data-demand-id');
                    if (demandId) {
                        this.showStopJobConfirmation(demandId);
                    }
                }
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
        });
    }

    /**
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshInterval = setInterval(() => {
            this.refreshJobs();
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
        // Update alignment jobs count
        const alignCountElement = document.querySelector('.text-center h2:first-of-type');
        if (alignCountElement) {
            alignCountElement.textContent = jobCounts.align_count;
        }

        // Update post-QC jobs count
        const postAlignCountElement = document.querySelector('.text-center h2:last-of-type');
        if (postAlignCountElement) {
            postAlignCountElement.textContent = jobCounts.post_align_count;
        }

        // Update total jobs count
        const totalCountElement = document.querySelector('.text-center h3');
        if (totalCountElement) {
            totalCountElement.textContent = jobCounts.total;
        }

        // Update progress bar
        const progressBar = document.querySelector('.job-count-progress');
        if (progressBar) {
            progressBar.style.width = `${jobCounts.total}%`;
            progressBar.setAttribute('aria-valuenow', jobCounts.total);
            progressBar.textContent = `${jobCounts.total}%`;
        }
    }

    /**
     * Refreshes all job statuses
     */
    refreshJobs() {
        const refreshBtn = document.getElementById('refreshJobsBtn');
        const updateAllBtn = document.getElementById('updateAllJobsBtn');

        // Disable both buttons and show spinners while refreshing
        if (refreshBtn) {
            refreshBtn.disabled = true;
            refreshBtn.querySelector('.refresh-icon').classList.add('d-none');
            refreshBtn.querySelector('.refresh-spinner').classList.remove('d-none');
        }

        if (updateAllBtn) {
            updateAllBtn.disabled = true;
            updateAllBtn.querySelector('.refresh-icon').classList.add('d-none');
            updateAllBtn.querySelector('.refresh-spinner').classList.remove('d-none');
        }

        // Show toast notification that update is in progress
        this.showToastNotification('Updating job statuses...', 'info', 2000);

        // First update all jobs
        fetch('/api/pipeline/update_all_jobs/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Update job statistics with the new counts
                    if (data.job_counts) {
                        this.updateJobStatistics(data.job_counts);
                    }

                    // Now fetch the updated job data
                    return fetch('/api/pipeline/get-job-data/', {
                        method: 'GET',
                        headers: {
                            'Content-Type': 'application/json'
                        }
                    });
                } else {
                    throw new Error(data.message || 'Failed to update jobs');
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    // Update the running jobs table
                    this.updateRunningJobsTable(data.running_jobs);
                    // Update the completed jobs table
                    this.updateCompletedJobsTable(data.completed_jobs);

                    this.showToastNotification('Jobs refreshed successfully', 'success');
                } else {
                    throw new Error(data.message || 'Failed to fetch updated job data');
                }
            })
            .catch(error => {
                console.error('Error updating jobs:', error);
                this.showToastNotification('Error refreshing jobs: ' + error.message, 'danger');
            })
            .finally(() => {
                // Reset button states
                this.resetButtonStates(refreshBtn, updateAllBtn);
            });
    }

    /**
     * Update the running jobs table
     */
    updateRunningJobsTable(runningJobs) {
        const tableBody = document.querySelector('#running-jobs-table tbody');
        if (!tableBody) return;

        if (runningJobs.length === 0) {
            // Show no jobs message
            const container = document.querySelector('#running-jobs-table').parentElement.parentElement;
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle-fill me-2"></i>
                    No jobs are currently running.
                </div>
            `;
            return;
        }

        // Update running jobs count badge
        const runningJobsBadge = document.querySelector('.card-header .badge');
        if (runningJobsBadge) {
            runningJobsBadge.textContent = runningJobs.length;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        // Add new rows
        runningJobs.forEach(job => {
            const row = document.createElement('tr');
            row.className = 'running-job';
            row.setAttribute('data-demand-id', job.demand_id);

            row.innerHTML = `
                <td>${job.fastq_name}</td>
                <td><span class="text-monospace">${job.demand_id}</span></td>
                <td>
                    <span class="badge workflow-badge ${job.workflow === 'MTX' ? 'badge-mtx' : 'bg-primary'}">
                        ${job.workflow}
                    </span>
                </td>
                <td>${job.organism}</td>
                <td>${job.batch}</td>
                <td>${new Date(job.start_time).toLocaleString()}</td>
                <td class="job-status">
                    ${this.getStatusBadgeHTML(job.status)}
                </td>
                <td>
                    <button class="btn btn-sm btn-outline-primary check-status-btn" data-demand-id="${job.demand_id}">
                        <i class="bi bi-arrow-clockwise"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger stop-job-btn" data-demand-id="${job.demand_id}">
                        <i class="bi bi-stop-fill"></i>
                    </button>
                </td>
            `;

            tableBody.appendChild(row);
        });

        // Reattach event listeners
        this.attachJobActionListeners();
    }

    /**
     * Update the completed jobs table
     */
    updateCompletedJobsTable(completedJobs) {
        const tableBody = document.querySelector('#completed-jobs-table tbody');
        if (!tableBody) return;

        if (completedJobs.length === 0) {
            // Show no jobs message
            const container = document.querySelector('#completed-jobs-table').parentElement.parentElement;
            container.innerHTML = `
                <div class="alert alert-info">
                    <i class="bi bi-info-circle-fill me-2"></i>
                    No jobs have been submitted and processed through this application yet. Once you submit jobs,
                    they will appear here after completion.
                </div>
            `;
            return;
        }

        // Update completed jobs count badge
        const completedJobsBadge = document.querySelector('.card-header .badge');
        if (completedJobsBadge) {
            completedJobsBadge.textContent = completedJobs.length;
        }

        // Clear existing rows
        tableBody.innerHTML = '';

        // Add new rows
        completedJobs.forEach(job => {
            const row = document.createElement('tr');
            row.setAttribute('data-demand-id', job.demand_id);
            row.className = job.status === 'FAILED' ? 'table-danger' :
                job.status === 'ABORTED' ? 'table-secondary' : '';

            row.innerHTML = `
                <td>${job.fastq_name}</td>
                <td><span class="text-monospace">${job.demand_id}</span></td>
                <td>
                    <span class="badge workflow-badge ${job.workflow === 'MTX' ? 'badge-mtx' : 'bg-primary'}">
                        ${job.workflow}
                    </span>
                </td>
                <td>${new Date(job.start_time).toLocaleString()}</td>
                <td>${job.end_time ? new Date(job.end_time).toLocaleString() : ''}</td>
                <td>${job.duration}</td>
                <td class="job-status">
                    ${this.getStatusBadgeHTML(job.status)}
                </td>
            `;

            tableBody.appendChild(row);
        });
    }

    /**
     * Helper method to reset button states
     */
    resetButtonStates(refreshBtn, updateAllBtn) {
        if (refreshBtn) {
            refreshBtn.disabled = false;
            refreshBtn.querySelector('.refresh-icon').classList.remove('d-none');
            refreshBtn.querySelector('.refresh-spinner').classList.add('d-none');
        }

        if (updateAllBtn) {
            updateAllBtn.disabled = false;
            updateAllBtn.querySelector('.refresh-icon').classList.remove('d-none');
            updateAllBtn.querySelector('.refresh-spinner').classList.add('d-none');
        }
    }

    /**
     * Helper method to get status badge HTML
     */
    getStatusBadgeHTML(status) {
        const statusMap = {
            'SUBMITTED': ['info', 'Submitted'],
            'IN_PROGRESS': ['primary', 'Running'],
            'COMPLETED': ['success', 'Completed'],
            'FAILED': ['danger', 'Failed'],
            'ABORTED': ['secondary', 'Aborted']
        };

        const [type, label] = statusMap[status] || ['secondary', status];
        return `<span class="badge bg-${type} status-badge">${label}</span>`;
    }

    /**
     * Reattach event listeners for job action buttons
     */
    attachJobActionListeners() {
        // Attach check status button listeners
        document.querySelectorAll('.check-status-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const demandId = btn.getAttribute('data-demand-id');
                if (demandId) {
                    this.checkJobStatus(demandId);
                }
            });
        });

        // Attach stop job button listeners
        document.querySelectorAll('.stop-job-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const demandId = btn.getAttribute('data-demand-id');
                if (demandId) {
                    this.showStopJobConfirmation(demandId);
                }
            });
        });
    }

    /**
     * Check status of a specific job
     */
    checkJobStatus(demandId) {
        this.showToastNotification(`Checking status for demand ID: ${demandId}`, 'info');

        fetch(`/api/pipeline/check-alignment-status/?demand_id=${demandId}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Show status in the status update modal
                    const modalBody = document.querySelector('#statusUpdateModal .job-status-details');
                    if (modalBody) {
                        modalBody.innerHTML = `
                            <div class="alert alert-${this.getAlertClass(data.job_status)} mb-3">
                                <strong>Current Status:</strong> ${data.job_status}
                            </div>
                            <table class="table table-sm">
                                <tr>
                                    <th>FASTQ Name:</th>
                                    <td>${data.fastq_name || 'N/A'}</td>
                                </tr>
                                <tr>
                                    <th>Demand ID:</th>
                                    <td>${demandId}</td>
                                </tr>
                                <tr>
                                    <th>Start Time:</th>
                                    <td>${data.start_time || 'N/A'}</td>
                                </tr>
                                <tr>
                                    <th>End Time:</th>
                                    <td>${data.end_time || 'N/A'}</td>
                                </tr>
                                <tr>
                                    <th>Duration:</th>
                                    <td>${data.duration || 'N/A'}</td>
                                </tr>
                            </table>
                        `;

                        // Show the modal
                        const statusModal = new bootstrap.Modal(document.getElementById('statusUpdateModal'));
                        statusModal.show();
                    }

                    // Update job status in the table
                    const statusCell = document.querySelector(`tr[data-demand-id="${demandId}"] .job-status`);
                    if (statusCell) {
                        statusCell.innerHTML = this.getStatusBadgeHTML(data.job_status);
                    }

                    this.showToastNotification(`Status updated: ${data.job_status}`, 'success');
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error checking job status:', error);
                this.showToastNotification('Network error while checking job status', 'danger');
            });
    }

    /**
     * Show stop job confirmation modal
     */
    showStopJobConfirmation(demandId) {
        const jobRow = document.querySelector(`tr[data-demand-id="${demandId}"]`);
        if (jobRow) {
            const fastqName = jobRow.cells[0].textContent.trim();
            const workflow = jobRow.cells[2].textContent.trim();

            const jobInfo = document.querySelector('#confirmStopModal .job-info');
            if (jobInfo) {
                jobInfo.innerHTML = `
                    <div class="alert alert-secondary">
                        <strong>FASTQ Name:</strong> ${fastqName}<br>
                        <strong>Workflow:</strong> ${workflow}<br>
                        <strong>Demand ID:</strong> ${demandId}
                    </div>
                `;
            }

            // Set demand ID on confirm button
            const confirmBtn = document.getElementById('confirmStopBtn');
            if (confirmBtn) {
                confirmBtn.setAttribute('data-demand-id', demandId);
            }

            // Show the modal
            const confirmModal = new bootstrap.Modal(document.getElementById('confirmStopModal'));
            confirmModal.show();
        } else {
            this.showToastNotification('Could not find job information', 'danger');
        }
    }

    /**
     * Stop a running job
     */
    stopJob(demandId) {
        this.showToastNotification(`Stopping job with demand ID: ${demandId}`, 'warning');

        fetch('/api/pipeline/stop-alignment/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ demand_id: demandId })
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    this.showToastNotification('Job stopped successfully', 'success');

                    // Update job status in the table
                    const statusCell = document.querySelector(`tr[data-demand-id="${demandId}"] .job-status`);
                    if (statusCell) {
                        statusCell.innerHTML = '<span class="badge bg-secondary status-badge">Aborted</span>';
                    }

                    // Hide the modal
                    const confirmModal = bootstrap.Modal.getInstance(document.getElementById('confirmStopModal'));
                    if (confirmModal) {
                        confirmModal.hide();
                    }

                    // Reload page after a short delay
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error stopping job:', error);
                this.showToastNotification('Network error while stopping job', 'danger');
            });
    }

    /**
     * Get alert class for status
     */
    getAlertClass(status) {
        switch (status.toUpperCase()) {
            case 'COMPLETED':
                return 'success';
            case 'RUNNING':
            case 'IN_PROGRESS':
                return 'primary';
            case 'SUBMITTED':
                return 'info';
            case 'FAILED':
                return 'danger';
            case 'ABORTED':
                return 'secondary';
            default:
                return 'secondary';
        }
    }

    /**
     * Shows a toast notification
     */
    showToastNotification(message, type = 'success', duration = 3000) {
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
            toastContainer.className = 'position-fixed bottom-0 end-0 p-3';
            toastContainer.style.zIndex = '11'; // Above most content
            document.body.appendChild(toastContainer);
        }

        // Set background color based on type
        let bgColor;
        let icon;
        switch (type) {
            case 'success':
                bgColor = '#28a745';
                icon = 'bi-check-circle-fill';
                break;
            case 'warning':
                bgColor = '#ffc107';
                icon = 'bi-exclamation-triangle-fill';
                break;
            case 'danger':
                bgColor = '#dc3545';
                icon = 'bi-x-circle-fill';
                break;
            case 'info':
            default:
                bgColor = '#17a2b8';
                icon = 'bi-info-circle-fill';
                break;
        }

        // Create the toast element
        const toastDiv = document.createElement('div');
        toastDiv.className = 'toast align-items-center text-white border-0';
        toastDiv.style.backgroundColor = bgColor;
        toastDiv.setAttribute('role', 'alert');
        toastDiv.setAttribute('aria-live', 'assertive');
        toastDiv.setAttribute('aria-atomic', 'true');

        // Set inner HTML for toast
        toastDiv.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="bi ${icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;

        // Add to container
        toastContainer.appendChild(toastDiv);

        // Initialize and show toast
        const bsToast = new bootstrap.Toast(toastDiv, {
            delay: duration,
            animation: true
        });
        bsToast.show();

        // Remove after hiding
        toastDiv.addEventListener('hidden.bs.toast', () => {
            if (toastDiv.parentNode) {
                toastDiv.parentNode.removeChild(toastDiv);
            }
        });
    }
}

// Initialize and export
const jobMonitor = new JobMonitor();
window.jobMonitor = jobMonitor; 