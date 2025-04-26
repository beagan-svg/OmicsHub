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
    }

    initializeEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            // Set up refresh jobs button
            const refreshJobsBtn = document.getElementById('refreshJobsBtn');
            if (refreshJobsBtn) {
                refreshJobsBtn.addEventListener('click', () => this.refreshJobs());
            }

            // Set up view queue button
            const viewQueueBtn = document.getElementById('view-queue-btn');
            if (viewQueueBtn) {
                viewQueueBtn.addEventListener('click', () => this.showQueueModal());
            }

            // Set up refresh queue button
            const refreshQueueBtn = document.getElementById('refresh-queue');
            if (refreshQueueBtn) {
                refreshQueueBtn.addEventListener('click', () => this.fetchQueueData());
            }

            // Set up auto-refresh toggle
            const autoRefreshToggle = document.getElementById('autoRefreshToggle');
            if (autoRefreshToggle) {
                let refreshInterval;
                autoRefreshToggle.addEventListener('change', function () {
                    if (this.checked) {
                        refreshInterval = setInterval(() => jobMonitor.refreshJobs(), 30000);
                    } else {
                        clearInterval(refreshInterval);
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
        });
    }

    /**
     * Refreshes all job statuses
     */
    refreshJobs() {
        const refreshBtn = document.getElementById('refreshJobsBtn');
        if (refreshBtn) {
            // Disable button and show spinner while refreshing
            refreshBtn.disabled = true;
            refreshBtn.querySelector('.refresh-icon').classList.add('d-none');
            refreshBtn.querySelector('.refresh-spinner').classList.remove('d-none');
        }

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
                    this.showToastNotification('Jobs refreshed successfully', 'success');

                    // Reload page to show updated job statuses
                    setTimeout(() => {
                        window.location.reload();
                    }, 1000);
                } else {
                    this.showToastNotification(`Error: ${data.message || 'Failed to refresh jobs'}`, 'danger');

                    // Re-enable button on error
                    if (refreshBtn) {
                        refreshBtn.disabled = false;
                        refreshBtn.querySelector('.refresh-icon').classList.remove('d-none');
                        refreshBtn.querySelector('.refresh-spinner').classList.add('d-none');
                    }
                }
            })
            .catch(error => {
                console.error('Error updating jobs:', error);
                this.showToastNotification('Network error while refreshing jobs', 'danger');

                // Re-enable button on error
                if (refreshBtn) {
                    refreshBtn.disabled = false;
                    refreshBtn.querySelector('.refresh-icon').classList.remove('d-none');
                    refreshBtn.querySelector('.refresh-spinner').classList.add('d-none');
                }
            });
    }

    /**
     * Shows the queue modal and populates it with data
     */
    showQueueModal() {
        // Fetch and display queue data
        this.fetchQueueData();

        // Show the modal
        const queueModal = new bootstrap.Modal(document.getElementById('queue-modal'));
        queueModal.show();
    }

    /**
     * Fetches queue data from the API
     */
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

    /**
     * Displays queue data in the specified table body
     */
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
                                data-fastq="${item.fastq_name}" data-demand-id="${item.demand_id || ''}" data-bs-toggle="tooltip" title="Refresh Status">
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

    /**
     * Shows sample details in a modal
     */
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
                                        <th>Library Prep Method:</th>
                                        <td>${metadata.library_prep_method || 'Unknown'}</td>
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

    /**
     * Refreshes the status of a specific sample
     */
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

    /**
     * Determines workflow type based on batch name
     */
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