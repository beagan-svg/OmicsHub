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

        // Initialize auto processing
        this.autoProcessInterval = null;
        this.autoProcessTime = 180000; // 3 minutes
        this.queuePaused = false; // Queue processing status

        // Initialize countdown timer
        this.countdownInterval = null;
        this.nextProcessTime = null;
        this.pausedTimeRemaining = null; // Store remaining time when paused

        // Initialize queue data management
        this.queue = [];

        // For tracking last auto-processing time
        this.lastAutoProcessTime = null;

        // Load settings from localStorage if available
        this.loadSettings();

        // Fetch queue data on load
        this.fetchQueueData();

        // Start auto-processing of Ready queue items every 3 minutes
        this.startAutoProcessing();

        // Start countdown timer
        this.initializeCountdown();

        // Log status to verify initialization
        console.log('Queue Manager initialized - Auto-processing setup complete');
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

            // Set up auto-refresh time slider
            const autoRefreshTimeSlider = document.getElementById('autoRefreshTime');
            if (autoRefreshTimeSlider) {
                autoRefreshTimeSlider.addEventListener('input', (e) => {
                    const seconds = parseInt(e.target.value);
                    const autoRefreshTimeLabel = document.getElementById('autoRefreshTimeLabel');
                    if (autoRefreshTimeLabel) {
                        autoRefreshTimeLabel.textContent = `${seconds} seconds`;
                    }
                });

                autoRefreshTimeSlider.addEventListener('change', (e) => {
                    const seconds = parseInt(e.target.value);
                    this.autoRefreshTime = seconds * 1000;

                    // Restart auto-refresh with new time if it's active
                    if (this.autoRefreshInterval) {
                        this.stopAutoRefresh();
                        this.startAutoRefresh();
                    }

                    // Save settings
                    this.saveSettings();

                    this.showToastNotification(`Auto-refresh interval set to ${seconds} seconds`, 'info');
                    console.log(`Auto-refresh interval updated to ${seconds} seconds (${this.autoRefreshTime}ms)`);
                });
            }

            // Set up auto-process time slider
            const autoProcessTimeSlider = document.getElementById('autoProcessTime');
            if (autoProcessTimeSlider) {
                autoProcessTimeSlider.addEventListener('input', (e) => {
                    const minutes = parseInt(e.target.value);
                    const autoProcessTimeLabel = document.getElementById('autoProcessTimeLabel');
                    if (autoProcessTimeLabel) {
                        autoProcessTimeLabel.textContent = `${minutes} minutes`;
                    }
                });

                autoProcessTimeSlider.addEventListener('change', (e) => {
                    const minutes = parseInt(e.target.value);
                    this.autoProcessTime = minutes * 60000;

                    // Update next process time based on new interval
                    if (this.lastAutoProcessTime) {
                        this.nextProcessTime = new Date(this.lastAutoProcessTime.getTime() + this.autoProcessTime);
                        this.updateCountdown();
                    }

                    // Restart auto-processing with new time
                    if (this.autoProcessInterval) {
                        this.stopAutoProcessing();
                        this.startAutoProcessing();
                    }

                    // Save settings
                    this.saveSettings();

                    this.showToastNotification(`Auto-processing interval set to ${minutes} minutes`, 'info');
                    console.log(`Auto-processing interval updated to ${minutes} minutes (${this.autoProcessTime}ms)`);
                });
            }

            // Set up pause/resume queue button
            const pauseQueueBtn = document.getElementById('pause-queue-btn');
            if (pauseQueueBtn) {
                pauseQueueBtn.addEventListener('click', () => this.toggleQueuePause());
            }

            // Set up reset countdown button
            const refreshCountdownBtn = document.getElementById('refresh-countdown-btn');
            if (refreshCountdownBtn) {
                refreshCountdownBtn.addEventListener('click', () => {
                    this.resetCountdown();
                    refreshCountdownBtn.classList.add('pulse-animation');
                    setTimeout(() => {
                        refreshCountdownBtn.classList.remove('pulse-animation');
                    }, 2000);
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
                processQueueBtn.addEventListener('click', () => {
                    this.processQueue();
                    // Timer will be reset in processQueue() if jobs are processed
                });
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
     * Load settings from localStorage
     */
    loadSettings() {
        // Load auto-refresh time
        const savedAutoRefreshTime = localStorage.getItem('queueAutoRefreshTime');
        if (savedAutoRefreshTime) {
            const seconds = parseInt(savedAutoRefreshTime);
            if (!isNaN(seconds) && seconds >= 5 && seconds <= 60) {
                this.autoRefreshTime = seconds * 1000;
                console.log(`Loaded auto-refresh time from localStorage: ${seconds} seconds`);

                // Update slider value
                const autoRefreshSlider = document.getElementById('autoRefreshTime');
                if (autoRefreshSlider) {
                    autoRefreshSlider.value = seconds;
                }

                // Update label
                const autoRefreshLabel = document.getElementById('autoRefreshTimeLabel');
                if (autoRefreshLabel) {
                    autoRefreshLabel.textContent = `${seconds} seconds`;
                }
            }
        }

        // Load auto-process time
        const savedAutoProcessTime = localStorage.getItem('queueAutoProcessTime');
        if (savedAutoProcessTime) {
            const minutes = parseInt(savedAutoProcessTime);
            if (!isNaN(minutes) && minutes >= 1 && minutes <= 10) {
                this.autoProcessTime = minutes * 60000;
                console.log(`Loaded auto-process time from localStorage: ${minutes} minutes`);

                // Update slider value
                const autoProcessSlider = document.getElementById('autoProcessTime');
                if (autoProcessSlider) {
                    autoProcessSlider.value = minutes;
                }

                // Update label
                const autoProcessLabel = document.getElementById('autoProcessTimeLabel');
                if (autoProcessLabel) {
                    autoProcessLabel.textContent = `${minutes} minutes`;
                }
            }
        }
    }

    /**
     * Save settings to localStorage
     */
    saveSettings() {
        // Save auto-refresh time (in seconds)
        const autoRefreshSeconds = this.autoRefreshTime / 1000;
        localStorage.setItem('queueAutoRefreshTime', autoRefreshSeconds.toString());

        // Save auto-process time (in minutes)
        const autoProcessMinutes = this.autoProcessTime / 60000;
        localStorage.setItem('queueAutoProcessTime', autoProcessMinutes.toString());

        console.log(`Settings saved: Auto-refresh: ${autoRefreshSeconds}s, Auto-process: ${autoProcessMinutes}m`);
    }

    /**
     * Toggle queue pause/resume state
     */
    toggleQueuePause() {
        this.queuePaused = !this.queuePaused;
        const pauseQueueBtn = document.getElementById('pause-queue-btn');
        const queueStatusBadge = document.getElementById('queue-status-badge');

        if (this.queuePaused) {
            // Queue is now paused
            if (pauseQueueBtn) {
                pauseQueueBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i> Resume Queue';
                pauseQueueBtn.classList.remove('btn-warning');
                pauseQueueBtn.classList.add('btn-success');
            }

            if (queueStatusBadge) {
                queueStatusBadge.textContent = 'Paused';
                queueStatusBadge.className = 'badge bg-warning';
            }

            this.showToastNotification('Queue processing paused', 'warning');
            console.log('Queue processing paused - Auto-processing disabled');

            // Stop the auto-processing interval
            if (this.autoProcessInterval) {
                clearInterval(this.autoProcessInterval);
                this.autoProcessInterval = null;
            }

            // Save remaining time when paused
            const now = new Date();
            this.pausedTimeRemaining = this.nextProcessTime - now;
            console.log(`Paused with ${Math.floor(this.pausedTimeRemaining / 1000)} seconds remaining`);

            // Stop countdown
            if (this.countdownInterval) {
                clearInterval(this.countdownInterval);
                this.countdownInterval = null;
            }
        } else {
            // Queue is now resumed
            if (pauseQueueBtn) {
                pauseQueueBtn.innerHTML = '<i class="bi bi-pause-fill me-1"></i> Pause Queue';
                pauseQueueBtn.classList.remove('btn-success');
                pauseQueueBtn.classList.add('btn-warning');
            }

            // Update status badge based on queue content
            this.updateQueueStatusBadge();

            this.showToastNotification('Queue processing resumed', 'success');
            console.log('Queue processing resumed - Auto-processing enabled');

            // Restore the countdown from where it was paused
            if (this.pausedTimeRemaining) {
                const now = new Date();
                this.nextProcessTime = new Date(now.getTime() + this.pausedTimeRemaining);
                console.log(`Resumed with timer set to ${Math.floor(this.pausedTimeRemaining / 1000)} seconds`);
                this.pausedTimeRemaining = null;
            }

            // Start the countdown and auto-processing
            this.startCountdown();
            this.startAutoProcessing();
        }
    }

    /**
     * Update queue status badge based on current queue state
     */
    updateQueueStatusBadge() {
        const queueStatusBadge = document.getElementById('queue-status-badge');
        if (!queueStatusBadge) return;

        if (this.queuePaused) {
            queueStatusBadge.textContent = 'Paused';
            queueStatusBadge.className = 'badge bg-warning';
            return;
        }

        if (this.queue.filter(item => item.status === 'Ready').length > 0) {
            queueStatusBadge.textContent = 'Ready to Process';
            queueStatusBadge.className = 'badge bg-success';
        } else if (this.queue.length === 0) {
            queueStatusBadge.textContent = 'Empty';
            queueStatusBadge.className = 'badge bg-secondary';
        } else {
            queueStatusBadge.textContent = 'Pending';
            queueStatusBadge.className = 'badge bg-info';
        }
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
     * Initialize countdown timer for next auto-processing
     */
    initializeCountdown() {
        // Initialize nextProcessTime
        if (!this.lastAutoProcessTime) {
            this.lastAutoProcessTime = new Date();
        }
        this.nextProcessTime = new Date(this.lastAutoProcessTime.getTime() + this.autoProcessTime);

        // Start the countdown
        this.startCountdown();

        // Update the next job info
        this.updateNextJobInfo();
    }

    /**
     * Start the countdown timer
     */
    startCountdown() {
        // Clear existing interval
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
        }

        // Update countdown immediately
        this.updateCountdown();

        // Set interval to update countdown every second
        this.countdownInterval = setInterval(() => {
            this.updateCountdown();
        }, 1000);
    }

    /**
     * Update the countdown display
     */
    updateCountdown() {
        const now = new Date();
        const timeRemaining = this.nextProcessTime - now;

        if (timeRemaining <= 0) {
            // Reset the countdown if time has expired
            this.resetCountdown();
            return;
        }

        // Calculate minutes and seconds
        const minutes = Math.floor(timeRemaining / (1000 * 60));
        const seconds = Math.floor((timeRemaining % (1000 * 60)) / 1000);

        // Update the UI
        const minutesElem = document.getElementById('countdown-minutes');
        const secondsElem = document.getElementById('countdown-seconds');

        if (minutesElem && secondsElem) {
            // Show paused status
            if (this.queuePaused) {
                // If paused, show the paused time remaining instead of dashes
                if (this.pausedTimeRemaining) {
                    const pausedMinutes = Math.floor(this.pausedTimeRemaining / (1000 * 60));
                    const pausedSeconds = Math.floor((this.pausedTimeRemaining % (1000 * 60)) / 1000);

                    minutesElem.textContent = pausedMinutes.toString().padStart(2, '0');
                    secondsElem.textContent = pausedSeconds.toString().padStart(2, '0');
                    minutesElem.style.color = '#6c757d'; // Gray out when paused
                    secondsElem.style.color = '#6c757d';
                } else {
                    minutesElem.textContent = '--';
                    secondsElem.textContent = '--';
                    minutesElem.style.color = '#6c757d';
                    secondsElem.style.color = '#6c757d';
                }
                return;
            }

            minutesElem.textContent = minutes.toString().padStart(2, '0');
            secondsElem.textContent = seconds.toString().padStart(2, '0');

            // Change color when getting close to processing
            if (minutes === 0 && seconds <= 30) {
                minutesElem.style.color = '#dc3545'; // Red for urgency
                secondsElem.style.color = '#dc3545';
            } else if (minutes === 0) {
                minutesElem.style.color = '#fd7e14'; // Orange for approaching
                secondsElem.style.color = '#fd7e14';
            } else {
                minutesElem.style.color = '#1e88e5'; // Default blue
                secondsElem.style.color = '#1e88e5';
            }
        }

        // Update queue status badge
        this.updateQueueStatusBadge();
    }

    /**
     * Reset the countdown timer
     */
    resetCountdown() {
        this.lastAutoProcessTime = new Date();
        this.nextProcessTime = new Date(this.lastAutoProcessTime.getTime() + this.autoProcessTime);
        // Clear any saved paused time
        this.pausedTimeRemaining = null;
        this.updateCountdown();
        // Start the countdown interval if it's not running
        if (!this.countdownInterval) {
            this.startCountdown();
        }

        const minutes = this.autoProcessTime / 60000;
        console.log(`Countdown reset. Next processing at ${this.nextProcessTime.toLocaleTimeString()} (in ${minutes} minute${minutes !== 1 ? 's' : ''})`);
    }

    /**
     * Update the next job information
     */
    updateNextJobInfo() {
        // Find the next job to be processed (first Ready status job)
        const nextJob = this.queue.find(item => item.status === 'Ready');

        // Get elements
        const nextJobName = document.getElementById('next-job-name');
        const nextJobCommand = document.getElementById('next-job-command');
        const nextJobBadge = document.getElementById('next-job-badge');
        const nextJobType = document.getElementById('next-job-type');
        const nextJobContainer = document.getElementById('next-job-container');
        const queueTotalJobs = document.getElementById('queue-total-jobs');

        // Update total jobs count
        if (queueTotalJobs) {
            queueTotalJobs.textContent = this.queue.length;
        }

        if (!nextJob) {
            // No Ready jobs in queue
            if (nextJobContainer) {
                // Always show "No Ready jobs" message when there are no Ready jobs
                nextJobName.textContent = 'No Ready jobs';
                nextJobCommand.textContent = 'Waiting for jobs with Ready status';
                nextJobBadge.textContent = 'None';
                nextJobBadge.className = 'badge bg-secondary mb-2';
                nextJobType.textContent = 'N/A';
                nextJobType.className = 'badge bg-secondary mb-2';

                // Add context about the current queue state
                if (this.queue.length === 0) {
                    nextJobCommand.textContent = 'Queue is empty. Add jobs to process.';
                } else if (this.queue.some(item => item.status === 'PENDING')) {
                    const pendingCount = this.queue.filter(item => item.status === 'PENDING').length;
                    nextJobCommand.textContent = `${pendingCount} pending job(s) waiting for alignment to complete`;
                } else if (this.queue.some(item => item.status === 'FAILED')) {
                    const failedCount = this.queue.filter(item => item.status === 'FAILED').length;
                    nextJobCommand.textContent = `${failedCount} failed job(s) need to be reset to Ready status`;
                } else if (this.queuePaused) {
                    nextJobCommand.textContent = 'Queue is paused. Resume to process jobs.';
                }
            }
            return;
        }

        // Update UI with next job information
        if (nextJobName && nextJobCommand && nextJobBadge && nextJobType) {
            nextJobName.textContent = nextJob.fastq_name;
            nextJobCommand.textContent = nextJob.command || 'N/A';
            nextJobBadge.textContent = nextJob.status;
            nextJobBadge.className = 'badge bg-info mb-2';

            // Use command_source field to determine job type
            const isAlignment = nextJob.command_source === 'alignment_command';
            nextJobType.textContent = isAlignment ? 'Alignment' : 'Post-QC';
            nextJobType.className = `badge ${isAlignment ? 'bg-primary' : 'bg-success'} mb-2`;

            console.log(`Next job type determined as ${isAlignment ? 'Alignment' : 'Post-QC'} based on command_source: ${nextJob.command_source}`);
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

            console.log('===== QUEUE MANAGEMENT: FETCHING QUEUE DATA =====');
            console.debug('[QueueDebug] Fetching queue data from server');

            // Add logging to track pending jobs before fetch
            console.log('[QueueDebug][Auto-Proceed] Checking for PENDING jobs before fetch');
            const pendingJobs = this.queue.filter(item => item.status === 'PENDING');
            if (pendingJobs.length > 0) {
                console.log(`[QueueDebug][Auto-Proceed] Found ${pendingJobs.length} PENDING jobs before fetch:`);
                pendingJobs.forEach(job => {
                    console.log(`[QueueDebug][Auto-Proceed] PENDING Job: ${job.fastq_name}`);
                });
            } else {
                console.log('[QueueDebug][Auto-Proceed] No PENDING jobs found before fetch');
            }

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
            console.debug('[QueueDebug] Queue data response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('[QueueDebug] Error response details:', {
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

            // Log a more detailed breakdown of the unified queue
            if (data.unified_queue && data.unified_queue.length > 0) {
                console.log('===== QUEUE MANAGEMENT: UNIFIED QUEUE ANALYSIS =====');
                console.log(`Total queue entries: ${data.unified_queue.length}`);

                // Count entries by status
                const statusCounts = {};
                data.unified_queue.forEach(item => {
                    const status = item.status || 'Unknown';
                    statusCounts[status] = (statusCounts[status] || 0) + 1;
                });
                console.log('Status counts:', statusCounts);

                // Show a few sample entries
                console.log('Sample queue entries:');
                const sampleEntries = data.unified_queue.slice(0, Math.min(5, data.unified_queue.length));
                sampleEntries.forEach((entry, index) => {
                    console.log(`Entry ${index + 1}:`);
                    console.log(`  Fastq Name: ${entry.fastq_name}`);
                    console.log(`  Command: ${(entry.command || '').substring(0, 50)}...`);
                    console.log(`  Status: ${entry.status}`);
                    console.log(`  Time: ${entry.time}`);
                });

                console.log('===== QUEUE MANAGEMENT: DISPLAY PREVIEW =====');
                console.log('How entries will appear in the table:');
                sampleEntries.forEach((entry, index) => {
                    let statusBadgeClass = 'bg-secondary';
                    switch (entry.status) {
                        case 'Ready':
                            statusBadgeClass = 'bg-info';
                            break;
                        case 'PENDING':
                            statusBadgeClass = 'bg-warning';
                            break;
                        case 'Submitted':
                            statusBadgeClass = 'bg-primary';
                            break;
                        case 'IN_PROGRESS':
                            statusBadgeClass = 'bg-warning';
                            break;
                        case 'COMPLETED':
                            statusBadgeClass = 'bg-success';
                            break;
                        case 'FAILED':
                            statusBadgeClass = 'bg-danger';
                            break;
                        default:
                            statusBadgeClass = 'bg-secondary';
                    }

                    console.log(`Entry ${index + 1}:`);
                    console.log(`  Fastq: ${entry.fastq_name}`);
                    console.log(`  Command: ${(entry.command || '').substring(0, 30)}...`);
                    console.log(`  Status Badge: <span class="badge ${statusBadgeClass}">${entry.status}</span>`);
                });
            }

            console.debug('[QueueDebug] Queue items by status:', this.countQueueItemsByStatus(data.unified_queue || []));

            if (data.status === 'error') {
                console.error('[QueueDebug] Server returned error:', data.message);
                throw new Error(data.message);
            }

            // Check for auto-proceed status changes
            if (pendingJobs.length > 0) {
                console.log('===== AUTO-PROCEED STATUS CHANGE DETECTION =====');
                console.log('[QueueDebug][Auto-Proceed] Step 1: Checking for status changes after fetch');
                const afterPendingJobs = data.unified_queue.filter(item => item.status === 'PENDING');

                console.log(`[QueueDebug][Auto-Proceed] Step 2: Found ${pendingJobs.length} PENDING jobs before fetch`);
                console.log(`[QueueDebug][Auto-Proceed] Step 3: Found ${afterPendingJobs.length} PENDING jobs after fetch`);

                // Find jobs that changed from PENDING to another status (should be Ready)
                const nowReadyJobs = pendingJobs.filter(
                    beforeJob => !afterPendingJobs.some(afterJob =>
                        afterJob.fastq_name === beforeJob.fastq_name && afterJob.status === 'PENDING'
                    )
                );

                if (nowReadyJobs.length > 0) {
                    console.log(`[QueueDebug][Auto-Proceed] Step 4: Found ${nowReadyJobs.length} jobs that changed from PENDING to Ready:`);
                    nowReadyJobs.forEach(job => {
                        // Find the current status of this job in the updated queue
                        const updatedJob = data.unified_queue.find(item => item.fastq_name === job.fastq_name);
                        const newStatus = updatedJob ? updatedJob.status : 'Unknown';

                        console.log(`[QueueDebug][Auto-Proceed] Step 5: Job ${job.fastq_name} status changed: PENDING → ${newStatus}`);
                        console.log(`[QueueDebug][Auto-Proceed] Step 6: Command: ${job.command?.substring(0, 100) || 'N/A'}`);

                        // Show a notification for each job that was auto-proceeded
                        this.showToastNotification(
                            `Auto-proceed activated: ${job.fastq_name} is now Ready for processing`,
                            'info',
                            3000
                        );
                    });

                    console.log('[QueueDebug][Auto-Proceed] Step 7: These Ready jobs will be picked up by the next auto-processing cycle');

                    // Log when the next auto-processing will occur
                    if (this.lastAutoProcessTime) {
                        const nextProcessTime = new Date(this.lastAutoProcessTime.getTime() + this.autoProcessTime);
                        console.log(`[QueueDebug][Auto-Proceed] Step 8: Next auto-processing cycle at ${nextProcessTime.toLocaleTimeString()}`);
                    }
                } else {
                    console.log('[QueueDebug][Auto-Proceed] No PENDING jobs changed status during this refresh');
                }

                console.log('===== END AUTO-PROCEED STATUS DETECTION =====');
            }

            // Store queue data
            this.queue = data.unified_queue || [];

            // Update count badge
            const countBadge = document.getElementById('queue-count');
            if (countBadge) countBadge.textContent = this.queue.length;

            // Render the queue table
            this.renderQueueTable(this.queue, 'queue-body');

            // Update next job info
            this.updateNextJobInfo();

            return data;
        } catch (error) {
            console.error('[QueueDebug] Error in fetchQueueData:', {
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
            const row = document.createElement('tr');
            row.dataset.queueId = item.fastq_name;

            // Format timestamp
            const time = new Date(item.time).toLocaleString();

            // Determine which command to show
            let commandDisplay = '';
            if (item.command) {
                commandDisplay = item.command;

                // Store command source for type detection
                if (!item.command_source) {
                    // Add command_source field if it doesn't exist
                    if (item.alignment_command && item.command === item.alignment_command) {
                        item.command_source = 'alignment_command';
                    } else if (item.postqc_command && item.command === item.postqc_command) {
                        item.command_source = 'postqc_command';
                    } else {
                        // Determine based on command content as fallback
                        item.command_source = item.command.includes('post-align') ? 'postqc_command' : 'alignment_command';
                    }
                    console.log(`Added command_source: ${item.command_source} for ${item.fastq_name}`);
                }
            } else {
                commandDisplay = 'N/A';
            }

            // Determine status badge style based on status
            let statusBadgeClass = 'bg-secondary';
            switch (item.status) {
                case 'Ready':
                    statusBadgeClass = 'bg-info';
                    break;
                case 'PENDING':
                    statusBadgeClass = 'bg-warning';
                    break;
                case 'Submitted':
                    statusBadgeClass = 'bg-primary';
                    break;
                case 'IN_PROGRESS':
                    statusBadgeClass = 'bg-warning';
                    break;
                case 'COMPLETED':
                    statusBadgeClass = 'bg-success';
                    break;
                case 'FAILED':
                    statusBadgeClass = 'bg-danger';
                    break;
                case 'ABORTED':
                    statusBadgeClass = 'bg-secondary';
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
                <td class="command-cell" contenteditable="true" data-fastq="${item.fastq_name}">${commandDisplay}</td>
                <td>
                    <span class="badge ${statusBadgeClass} status-badge" 
                          data-fastq="${item.fastq_name}" 
                          data-status="${item.status}"
                          data-id="${item.id || ''}"
                          data-command-source="${item.command_source || ''}"
                          role="button">
                        ${item.status}
                    </span>
                </td>
                <td>${time}</td>
            `;

            tableBody.appendChild(row);
        });

        // Add event listeners for status badges and command editing
        this.addTableEventListeners();
    }

    /**
     * Add event listeners to the table elements
     */
    addTableEventListeners() {
        // Add click event for status badges (only FAILED ones are editable)
        document.querySelectorAll('.status-badge').forEach(badge => {
            badge.addEventListener('click', (e) => {
                const fastqName = e.target.dataset.fastq;
                const currentStatus = e.target.dataset.status;
                // Get the job ID from the data attribute
                const jobId = e.target.dataset.id;

                // Only allow changing FAILED status back to Ready
                if (currentStatus === 'FAILED') {
                    if (confirm(`Change status of ${fastqName} back to Ready?`)) {
                        this.updateQueueItemStatus(fastqName, 'Ready', jobId);
                    }
                }
            });
        });

        // Add blur event for command cells to save on edit
        document.querySelectorAll('.command-cell').forEach(cell => {
            // Store original content to avoid unnecessary updates
            cell.dataset.originalContent = cell.textContent;

            cell.addEventListener('blur', (e) => {
                const fastqName = e.target.dataset.fastq;
                const newCommand = e.target.textContent;
                const originalContent = e.target.dataset.originalContent || '';

                // Get the job ID from the closest status badge
                const row = e.target.closest('tr');
                const statusBadge = row ? row.querySelector('.status-badge') : null;
                const jobId = statusBadge ? statusBadge.dataset.id : null;

                // Only update if content has changed to avoid unnecessary API calls
                if (newCommand !== originalContent) {
                    console.log(`[QueueDebug] Command changed for ${fastqName}, updating in database`);
                    // Update command in database with job ID
                    this.updateQueueItemCommand(fastqName, newCommand, jobId);
                    // Update original content
                    e.target.dataset.originalContent = newCommand;
                } else {
                    console.log(`[QueueDebug] Command unchanged for ${fastqName}, skipping update`);
                }
            });

            // Prevent Enter key from adding newlines (commit changes instead)
            cell.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    e.target.blur();
                }
            });
        });
    }

    /**
     * Update queue item status
     */
    updateQueueItemStatus(fastqName, newStatus, jobId) {
        this.showToastNotification(`Updating status for ${fastqName}...`, 'info');

        console.log(`[QueueDebug] Attempting to update status for job ID ${jobId} (${fastqName}) to ${newStatus}`);

        // Log the request being sent
        const requestBody = JSON.stringify({
            fastq_name: fastqName,
            status: newStatus,
            job_id: jobId // Include the job ID to identify the specific job
        });
        console.debug(`[QueueDebug] Request body: ${requestBody}`);

        fetch('/api/queue/update_status/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: requestBody
        })
            .then(response => {
                console.debug(`[QueueDebug] Update status response code: ${response.status}`);
                if (!response.ok) {
                    // If response is not OK, capture the error message
                    return response.text().then(text => {
                        console.error(`[QueueDebug] Update status error response: ${text}`);
                        throw new Error(`HTTP error! status: ${response.status}, message: ${text}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.debug(`[QueueDebug] Update status response data:`, data);
                if (data.status === 'success') {
                    this.showToastNotification(`Status updated to ${newStatus}`, 'success');

                    // If we're changing to Ready status, show an additional message
                    if (newStatus === 'Ready') {
                        this.showToastNotification(`Job resubmitted and will be processed in next cycle`, 'info', 4000);
                    }

                    this.fetchQueueData(); // Refresh the data
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('[QueueDebug] Error updating status:', error);

                // Provide a more helpful error message
                let errorMessage = error.message;
                if (error.message.includes('400')) {
                    errorMessage = 'Invalid status update. Check the server logs for details.';
                } else if (error.message.includes('404')) {
                    errorMessage = `Queue item "${fastqName}" not found. It may have been deleted.`;
                } else if (error.message.includes('500')) {
                    errorMessage = 'Server error. Please try again or contact an administrator.';
                }

                this.showToastNotification(`Error updating status: ${errorMessage}`, 'danger');
            });
    }

    /**
     * Update queue item command
     */
    updateQueueItemCommand(fastqName, newCommand, jobId) {
        this.showToastNotification(`Updating command for ${fastqName}...`, 'info');

        console.log(`[QueueDebug] Attempting to update command for ${fastqName}`);
        console.log(`[QueueDebug] New command (truncated): ${newCommand.substring(0, 100)}...`);

        // Get the job ID from the closest status badge if not provided
        if (!jobId) {
            const statusBadge = document.querySelector(`.status-badge[data-fastq="${fastqName}"]`);
            if (statusBadge) {
                jobId = statusBadge.dataset.id;
                console.log(`[QueueDebug] Found job ID from DOM: ${jobId}`);
            }
        }

        // Log the request being sent
        const requestBody = JSON.stringify({
            fastq_name: fastqName,
            command: newCommand,
            job_id: jobId || '' // Include job ID if available
        });
        console.debug(`[QueueDebug] Request body (truncated): 
            fastq_name: ${fastqName}, 
            command length: ${newCommand.length},
            job_id: ${jobId || 'not provided'}`);

        fetch('/api/queue/update_command/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            },
            body: requestBody
        })
            .then(response => {
                console.debug(`[QueueDebug] Update command response code: ${response.status}`);
                if (!response.ok) {
                    // If response is not OK, capture the error message
                    return response.text().then(text => {
                        console.error(`[QueueDebug] Update command error response: ${text}`);
                        throw new Error(`HTTP error! status: ${response.status}, message: ${text}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                console.debug(`[QueueDebug] Update command response data:`, data);
                if (data.status === 'success') {
                    this.showToastNotification('Command updated successfully', 'success');

                    // Only refresh the data if specifically requested - command updates don't need immediate refresh
                    // this.fetchQueueData();
                } else {
                    this.showToastNotification(`Error: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('[QueueDebug] Error updating command:', error);

                // Provide a more helpful error message
                let errorMessage = error.message;
                if (error.message.includes('400')) {
                    errorMessage = 'Invalid command update. Check the server logs for details.';
                } else if (error.message.includes('404')) {
                    errorMessage = `Queue item "${fastqName}" not found. It may have been deleted.`;
                } else if (error.message.includes('500')) {
                    errorMessage = 'Server error. Please try again or contact an administrator.';
                }

                this.showToastNotification(`Error updating command: ${errorMessage}`, 'danger');
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
        // Check if queue is paused
        if (this.queuePaused) {
            this.showToastNotification('Queue is paused. Resume queue to process items.', 'warning');
            console.log('Process queue requested while queue is paused - operation cancelled');
            return;
        }

        this.showToastNotification('Processing queue...', 'info');
        console.debug('[QueueDebug] Manual queue processing initiated');
        console.log('===== QUEUE MANAGEMENT: PROCESS QUEUE STARTED =====');

        fetch('/api/queue/process/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json'
            }
        })
            .then(response => {
                if (!response.ok) {
                    console.error('[QueueDebug] Manual queue processing HTTP error:', response.status, response.statusText);
                    console.error('[QueueCommand] Process queue request failed with status:', response.status);
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    console.debug(`[QueueDebug] Manual queue processing results: ${data.processed_count} submitted, ${data.failed_count} failed`);
                    console.log('===== QUEUE MANAGEMENT: PROCESS RESULTS =====');
                    console.log(`Processed: ${data.processed_count} items, Failed: ${data.failed_count} items`);

                    // Log processed jobs
                    if (data.processed_jobs && data.processed_jobs.length > 0) {
                        console.log('===== QUEUE MANAGEMENT: SUCCESSFULLY PROCESSED JOBS =====');
                        data.processed_jobs.forEach((job, index) => {
                            console.log(`Job ${index + 1}: ${job.fastq_name} (${job.command_type}) - Demand ID: ${job.demand_id}`);
                        });
                    }

                    // Log failed jobs
                    if (data.failed_jobs && data.failed_jobs.length > 0) {
                        console.log('===== QUEUE MANAGEMENT: FAILED JOBS =====');
                        data.failed_jobs.forEach((job, index) => {
                            console.log(`Job ${index + 1}: ${job.fastq_name} - Reason: ${job.reason}`);
                        });
                    }

                    this.showToastNotification(`Successfully processed ${data.processed_count || 0} items from queue`, 'success');
                    this.fetchQueueData(); // Refresh the data

                    // If jobs were actually processed (count > 0), reset the countdown timer
                    if (data.processed_count > 0) {
                        console.log('Jobs were processed, resetting the countdown timer');
                        this.resetCountdown();
                    } else {
                        // Otherwise just ensure the countdown is running
                        if (!this.countdownInterval) {
                            this.startCountdown();
                        }
                    }
                } else {
                    console.error('[QueueDebug] Manual queue processing error:', data.message);
                    console.error('[QueueCommand] Process queue failed:', data.message);
                    this.showToastNotification(`Error: ${data.message || 'Failed to process queue'}`, 'danger');
                }
            })
            .catch(error => {
                console.error('[QueueDebug] Error in manual queue processing:', error);
                console.error('[QueueCommand] Process queue exception:', error.message);
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

    /**
     * Start auto-processing of Ready queue items
     */
    startAutoProcessing() {
        if (this.autoProcessInterval) {
            clearInterval(this.autoProcessInterval);
            this.autoProcessInterval = null;
            console.log('Cleared existing auto-processing interval');
        }

        this.autoProcessInterval = setInterval(() => {
            if (this.queuePaused) {
                console.log(`[QueueDebug] Auto-processing cycle skipped because queue is paused`);
                return;
            }

            const now = new Date();
            console.log(`[QueueDebug] Auto-processing cycle triggered at ${now.toLocaleTimeString()}`);
            this.lastAutoProcessTime = now;
            this.processReadyItems();
            // Reset nextProcessTime for the next auto-processing cycle
            this.nextProcessTime = new Date(now.getTime() + this.autoProcessTime);
            // Update the countdown display without restarting the timer
            this.updateCountdown();
        }, this.autoProcessTime); // Run every 3 minutes

        console.log(`Queue auto-processing ${this.queuePaused ? 'initialized but paused' : 'started'} - configured for every 3 minutes (${this.autoProcessTime}ms)`);

        // Immediately run first processing to avoid waiting for the first interval
        if (!this.queuePaused) {
            console.log('[QueueDebug] Running initial queue processing');
            this.processReadyItems();
        } else {
            console.log('[QueueDebug] Initial queue processing skipped - queue is paused');

            // Update UI to show paused status
            const pauseQueueBtn = document.getElementById('pause-queue-btn');
            if (pauseQueueBtn) {
                pauseQueueBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i> Resume Queue';
                pauseQueueBtn.classList.remove('btn-warning');
                pauseQueueBtn.classList.add('btn-success');
            }

            const queueStatusBadge = document.getElementById('queue-status-badge');
            if (queueStatusBadge) {
                queueStatusBadge.textContent = 'Paused';
                queueStatusBadge.className = 'badge bg-warning';
            }
        }
    }

    /**
     * Stop auto-processing
     */
    stopAutoProcessing() {
        if (this.autoProcessInterval) {
            clearInterval(this.autoProcessInterval);
            this.autoProcessInterval = null;
            console.log('Auto-processing stopped');
        }
    }

    /**
     * Process only Ready queue items
     */
    processReadyItems() {
        // Skip processing if queue is paused
        if (this.queuePaused) {
            console.log(`Auto-processing cycle skipped: Queue is currently paused`);
            return;
        }

        const currentTime = new Date().toLocaleTimeString();
        console.log(`Auto-processing Ready items in queue at ${currentTime}...`);
        console.debug('[QueueDebug] Beginning queue processing cycle');

        // Add visual indicator that processing is happening
        const processQueueBtn = document.getElementById('process-queue-btn');
        if (processQueueBtn) {
            processQueueBtn.classList.add('pulse-animation');
            setTimeout(() => {
                processQueueBtn.classList.remove('pulse-animation');
            }, 2000);
        }

        // Log any pending jobs before processing starts
        const pendingJobs = this.queue.filter(item => item.status === 'PENDING');
        if (pendingJobs.length > 0) {
            console.log(`[QueueDebug][Auto-Proceed] Found ${pendingJobs.length} PENDING jobs waiting for alignment completion:`);
            pendingJobs.forEach(job => {
                console.log(`[QueueDebug][Auto-Proceed] PENDING Job: ${job.fastq_name} - Command: ${job.command?.substring(0, 30)}...`);
            });
        }

        fetch('/api/queue/process/?auto=true', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            },
            body: JSON.stringify({
                auto_process: true
            })
        })
            .then(response => {
                if (!response.ok) {
                    console.error('[QueueDebug] Queue processing HTTP error:', response.status, response.statusText);
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    console.debug(`[QueueDebug] Queue processing results: ${data.processed_count} submitted, ${data.failed_count} failed`);

                    // Only update UI and show notifications if there were actually items processed
                    if (data.processed_count > 0 || data.failed_count > 0) {
                        console.log(`Auto-processed: ${data.processed_count} submitted, ${data.failed_count} failed`);

                        // Show toast notification for visibility
                        this.showToastNotification(`Auto-processed ${data.processed_count} jobs (${data.failed_count} failed)`, 'info', 2000);

                        // Check if any processed jobs were previously PENDING (auto-proceed)
                        if (data.processed_jobs && data.processed_jobs.length > 0) {
                            const autoProcessedJobs = data.processed_jobs.filter(job =>
                                pendingJobs.some(pending => pending.fastq_name === job.fastq_name)
                            );

                            if (autoProcessedJobs.length > 0) {
                                console.log('===== AUTO-PROCEED JOB PROCESSING =====');
                                console.log(`[QueueDebug][Auto-Proceed] Step 1: Found ${autoProcessedJobs.length} auto-proceed jobs that were successfully processed`);

                                autoProcessedJobs.forEach((job, index) => {
                                    console.log(`[QueueDebug][Auto-Proceed] Step 2.${index + 1}: Job ${job.fastq_name} was submitted for processing`);
                                    console.log(`[QueueDebug][Auto-Proceed]   - Command type: ${job.command_type}`);
                                    console.log(`[QueueDebug][Auto-Proceed]   - Demand ID: ${job.demand_id}`);

                                    // Find the original job that was auto-proceeded
                                    const originalJob = pendingJobs.find(pending => pending.fastq_name === job.fastq_name);
                                    if (originalJob) {
                                        console.log(`[QueueDebug][Auto-Proceed]   - Original status: PENDING (auto-proceeded to Ready)`);
                                    }

                                    this.showToastNotification(
                                        `Auto-proceed job ${job.fastq_name} successfully submitted!`,
                                        'success',
                                        4000
                                    );
                                });

                                console.log(`[QueueDebug][Auto-Proceed] Step 3: All auto-proceed jobs have been submitted to OCS`);
                                console.log(`[QueueDebug][Auto-Proceed] Step 4: These jobs will now show in running jobs table`);
                                console.log('===== END AUTO-PROCEED JOB PROCESSING =====');
                            }
                        }

                        // Refresh the data
                        this.fetchQueueData();

                        // Add a more detailed log for the jobs that were processed
                        if (data.processed_jobs && data.processed_jobs.length > 0) {
                            console.debug('[QueueDebug] Successfully processed jobs:', data.processed_jobs);
                        }

                        // Log failed job details if available
                        if (data.failed_jobs && data.failed_jobs.length > 0) {
                            console.warn('[QueueDebug] Failed jobs:', data.failed_jobs);
                        }
                    } else {
                        console.debug('[QueueDebug] No jobs were processed in this cycle');
                    }
                } else {
                    console.error('[QueueDebug] Queue processing error:', data.message);
                    this.showToastNotification(`Auto-processing error: ${data.message}`, 'error', 3000);
                }
            })
            .catch(error => {
                console.error('[QueueDebug] Error in auto-processing:', error);
                // Show a notification for errors so they're more visible
                this.showToastNotification(`Auto-processing error: ${error.message}`, 'error', 3000);
            })
            .finally(() => {
                // Skip scheduling next processing if paused
                if (this.queuePaused) {
                    console.log('[QueueDebug] Queue is paused - not scheduling next auto-processing');
                    return;
                }

                // Log the next scheduled processing time
                const nextTime = new Date(Date.now() + this.autoProcessTime);
                console.debug(`[QueueDebug] Next auto-processing scheduled for ${nextTime.toLocaleTimeString()}`);

                // Update last auto-processing time
                this.lastAutoProcessTime = new Date();

                // Verify the interval is still active
                if (!this.autoProcessInterval) {
                    console.warn('[QueueDebug] Auto-processing interval is no longer active! Restarting...');
                    this.startAutoProcessing();
                }
            });
    }

    /**
     * Helper method to count queue items by status for debugging
     * @param {Array} queueItems - The queue items to count
     * @returns {Object} Object with counts by status
     */
    countQueueItemsByStatus(queueItems) {
        const counts = {};
        queueItems.forEach(item => {
            const status = item.status || 'Unknown';
            counts[status] = (counts[status] || 0) + 1;
        });
        return counts;
    }
}

// Initialize and export
const queueManager = new QueueManager();
window.queueManager = queueManager;
