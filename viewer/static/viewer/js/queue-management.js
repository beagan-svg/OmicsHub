/**
 * queue-management.js
 * Handles functionality for the Pipeline Queue Management page
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

class QueueManager {
    constructor() {
        console.log('Initializing Queue Manager...');
        this.initializeEventListeners();

        // Initialize automatic data fetching
        this.autoRefreshInterval = null;
        this.autoRefreshTime = 30000; // 30 seconds

        // Initialize queue data management
        this.queue = [];

        // Fetch queue data on load
        this.fetchQueueData();
    }

    initializeEventListeners() {
        document.addEventListener('DOMContentLoaded', () => {
            // Set up refresh queue data button
            const refreshQueueBtn = document.getElementById('refresh-queue-btn');
            if (refreshQueueBtn) {
                refreshQueueBtn.addEventListener('click', () => this.fetchQueueData());
            }

            const refreshQueueDataBtn = document.getElementById('refresh-queue-data');
            if (refreshQueueDataBtn) {
                refreshQueueDataBtn.addEventListener('click', () => {
                    refreshQueueDataBtn.classList.add('pulse-animation');
                    this.fetchQueueData();
                    setTimeout(() => {
                        refreshQueueDataBtn.classList.remove('pulse-animation');
                    }, 2000);
                });
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

            // Set up clear queue button
            const clearQueueBtn = document.getElementById('clear-queue-btn');
            if (clearQueueBtn) {
                clearQueueBtn.addEventListener('click', () => {
                    // Show confirmation modal
                    const confirmModal = new bootstrap.Modal(document.getElementById('confirmClearModal'));
                    confirmModal.show();
                });
            }

            // Set up confirm clear button
            const confirmClearBtn = document.getElementById('confirmClearBtn');
            if (confirmClearBtn) {
                confirmClearBtn.addEventListener('click', () => this.clearQueue());
            }

            // Set up process queue button
            const processQueueBtn = document.getElementById('process-queue-btn');
            if (processQueueBtn) {
                processQueueBtn.addEventListener('click', () => this.processQueue());
            }

            // Set up select all checkboxes
            const selectAll = document.getElementById('selectAll');
            if (selectAll) {
                selectAll.addEventListener('change', (e) => {
                    const isChecked = e.target.checked;
                    document.querySelectorAll('#queue-table tbody input[type="checkbox"]').forEach(checkbox => {
                        checkbox.checked = isChecked;
                    });
                });
            }

            // Set up remove selected button
            const removeSelectedBtn = document.getElementById('remove-selected-btn');
            if (removeSelectedBtn) {
                removeSelectedBtn.addEventListener('click', () => this.removeSelectedItems());
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
     * Start auto-refresh interval
     */
    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshInterval = setInterval(() => {
            this.fetchQueueData();
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
     * Fetches queue data from the database
     */
    async fetchQueueData() {
        try {
            // Show loading state in the refresh button
            const refreshBtn = document.getElementById('refresh-queue-btn');
            if (refreshBtn) {
                refreshBtn.disabled = true;
                if (refreshBtn.querySelector('.refresh-icon')) {
                    refreshBtn.querySelector('.refresh-icon').classList.add('d-none');
                    refreshBtn.querySelector('.refresh-spinner').classList.remove('d-none');
                } else {
                    refreshBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
                }
            }

            // Show loading state in the table
            const queueBody = document.getElementById('queue-body');
            if (queueBody) {
                queueBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </td>
                    </tr>
                `;
            }

            console.log('Starting fetchQueueData...');
            const response = await fetch('/api/queue/get_data/?nocache=' + new Date().getTime(), {
                method: 'GET',
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            });
            console.log('Response received:', response);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Error response details:', {
                    status: response.status,
                    statusText: response.statusText,
                    headers: Object.fromEntries(response.headers.entries()),
                    body: errorText
                });
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            console.log('Queue data received:', {
                status: data.status,
                totalEntries: data.total_entries
            });

            if (data.status === 'error') {
                console.error('Server returned error:', data.message);
                throw new Error(data.message);
            }

            // Store queue data
            this.queue = data.unified_queue || [];

            // Update count badge
            const countBadge = document.getElementById('queue-count');
            if (countBadge) countBadge.textContent = this.queue.length;

            // Render the queue table
            this.renderQueueTable(this.queue, 'queue-body');

            return data;
        } catch (error) {
            console.error('Error in fetchQueueData:', {
                name: error.name,
                message: error.message,
                stack: error.stack
            });

            // Show error in the table
            const queueBody = document.getElementById('queue-body');
            if (queueBody) {
                queueBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center text-danger">
                            <i class="bi bi-exclamation-triangle-fill"></i>
                            Error loading queue data
                        </td>
                    </tr>
                `;
            }

            throw error;
        } finally {
            // Reset refresh button state
            const refreshBtn = document.getElementById('refresh-queue-btn');
            if (refreshBtn) {
                refreshBtn.disabled = false;
                if (refreshBtn.querySelector('.refresh-icon')) {
                    refreshBtn.querySelector('.refresh-icon').classList.remove('d-none');
                    refreshBtn.querySelector('.refresh-spinner').classList.add('d-none');
                } else {
                    refreshBtn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Refresh';
                }
            }
        }
    }

    /**
     * Renders queue table with data
     */
    renderQueueTable(queueItems, tableBodyId) {
        const tableBody = document.getElementById(tableBodyId);
        if (!tableBody) {
            console.error(`Table body not found: ${tableBodyId}`);
            return;
        }

        if (!queueItems || queueItems.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="5" class="text-center">No items in queue</td></tr>';
            return;
        }

        // Clear table first
        tableBody.innerHTML = '';

        // Add rows for each queue item
        queueItems.forEach((item, index) => {
            console.log(`Processing item ${index}:`, item);
            const row = document.createElement('tr');
            row.dataset.queueId = item.fastq_name;

            // Format timestamp
            const time = new Date(item.time).toLocaleString();

            // Determine which command to show
            let commandDisplay = '';
            if (item.command) {
                commandDisplay = item.command;
            } else {
                commandDisplay = 'N/A';
            }

            // Determine status badge style (no mapping, just color for three statuses)
            let statusBadgeClass = 'bg-secondary';
            switch (item.status) {
                case 'Ready':
                    statusBadgeClass = 'bg-info';
                    break;
                case 'Pending':
                    statusBadgeClass = 'bg-warning';
                    break;
                case 'Failed':
                    statusBadgeClass = 'bg-danger';
                    break;
                default:
                    statusBadgeClass = 'bg-secondary';
            }

            row.innerHTML = `
                <td>
                    <div class="form-check">
                        <input class="form-check-input queue-item-checkbox" type="checkbox" 
                            value="${item.fastq_name}" 
                            data-fastq="${item.fastq_name}">
                    </div>
                </td>
                <td>${item.fastq_name}</td>
                <td class="command-cell" style="white-space: pre-wrap; word-wrap: break-word;">${commandDisplay}</td>
                <td><span class="badge ${statusBadgeClass}">${item.status}</span></td>
                <td>${time}</td>
            `;

            tableBody.appendChild(row);
        });
    }

    /**
     * Shows modal with command details
     */
    showCommandModal(fastqName, alignmentCommand, postqcCommand) {
        console.log('Showing command modal for:', fastqName);

        // Set modal content
        const fastqNameElement = document.getElementById('modal-fastq-name');
        const alignmentCommandElement = document.getElementById('modal-alignment-command');
        const postqcCommandElement = document.getElementById('modal-postqc-command');

        if (fastqNameElement) {
            fastqNameElement.textContent = fastqName;
        }

        if (alignmentCommandElement) {
            alignmentCommandElement.textContent = alignmentCommand || 'N/A';
        }

        if (postqcCommandElement) {
            postqcCommandElement.textContent = postqcCommand || 'N/A';
        }

        // Show the modal
        const modal = new bootstrap.Modal(document.getElementById('command-detail-modal'));
        modal.show();
    }

    /**
     * Remove a single queue item
     */
    removeQueueItem(id, fastqName) {
        if (!id || !fastqName) return;

        this.showToastNotification(`Removing ${fastqName} from queue...`, 'info');

        fetch('/api/queue/remove/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ id: id })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    this.showToastNotification(`Successfully removed ${fastqName} from queue`, 'success');
                    this.fetchQueueData(); // Refresh the data
                } else {
                    this.showToastNotification(`Error: ${data.message || 'Failed to remove item'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error removing queue item:', error);
                this.showToastNotification(`Error removing item: ${error.message}`, 'danger');
            });
    }

    /**
     * Show confirmation for removing selected items
     */
    showRemoveSelectedConfirmation() {
        // Get selected items
        const selectedItems = document.querySelectorAll('#queue-table tbody input[type="checkbox"]:checked');

        if (selectedItems.length === 0) {
            this.showToastNotification('Please select items to remove', 'warning');
            return;
        }

        // Show selected items summary
        const summaryElement = document.getElementById('selected-items-summary');
        if (summaryElement) {
            summaryElement.innerHTML = `
                <p class="mb-2"><strong>${selectedItems.length} items selected for removal:</strong></p>
                <ul class="mb-0">
                    ${Array.from(selectedItems).map(item => `<li>${item.getAttribute('data-fastq')}</li>`).join('')}
                </ul>
            `;
        }

        // Show confirmation modal
        const confirmModal = new bootstrap.Modal(document.getElementById('confirmRemoveSelectedModal'));
        confirmModal.show();
    }

    /**
     * Remove selected items from queue
     */
    removeSelectedItems() {
        // Get selected items
        const selectedItems = document.querySelectorAll('#queue-table tbody input[type="checkbox"]:checked');

        if (selectedItems.length === 0) {
            this.showToastNotification('No items selected', 'warning');
            return;
        }

        // Extract item IDs
        const itemIds = Array.from(selectedItems).map(item => item.value);

        this.showToastNotification(`Removing ${itemIds.length} items from queue...`, 'info');

        fetch('/api/queue/remove_multiple/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ ids: itemIds })
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    this.showToastNotification(`Successfully removed ${data.removed_count || itemIds.length} samples from queue`, 'success');

                    // Uncheck the select all checkbox
                    const selectAllCheckbox = document.getElementById('selectAll');
                    if (selectAllCheckbox) {
                        selectAllCheckbox.checked = false;
                    }

                    this.fetchQueueData(); // Refresh the data
                } else {
                    this.showToastNotification(`Error: ${data.message || 'Failed to remove items'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error removing queue items:', error);
                this.showToastNotification(`Error removing items: ${error.message}`, 'danger');
            });
    }

    /**
     * Clear all items from the queue
     */
    clearQueue() {
        this.showToastNotification('Clearing all items from queue...', 'warning');

        fetch('/api/queue/clear/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    this.showToastNotification('Successfully cleared queue', 'success');

                    // Hide the modal
                    const confirmModal = bootstrap.Modal.getInstance(document.getElementById('confirmClearModal'));
                    if (confirmModal) {
                        confirmModal.hide();
                    }

                    this.fetchQueueData(); // Refresh the data
                } else {
                    this.showToastNotification(`Error: ${data.message || 'Failed to clear queue'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error clearing queue:', error);
                this.showToastNotification(`Error clearing queue: ${error.message}`, 'danger');
            });
    }

    /**
     * Process next items in the queue
     */
    processQueue() {
        this.showToastNotification('Processing queue...', 'info');

        fetch('/api/queue/process/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    this.showToastNotification(`Successfully processed ${data.processed_count || 0} items from queue`, 'success');
                    this.fetchQueueData(); // Refresh the data
                } else {
                    this.showToastNotification(`Error: ${data.message || 'Failed to process queue'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error processing queue:', error);
                this.showToastNotification(`Error processing queue: ${error.message}`, 'danger');
            });
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
const queueManager = new QueueManager();
window.queueManager = queueManager;