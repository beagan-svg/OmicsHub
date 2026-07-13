/**
 * Queue management page.
 *
 * The shared queue is displayed here, but jobs are submitted by the BACKEND
 * processor (the `process_queue` management command), not the browser. This
 * script only:
 *   - shows the shared queue (with an Owner column) and the next job,
 *   - lets a user remove their own jobs (superusers may remove any),
 *   - gives superusers the master controls (process now / pause / resume /
 *     stop / reset / clear / reorder), all enforced again on the backend.
 */

const REFRESH_INTERVAL_MS = 15000;

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        for (const raw of document.cookie.split(';')) {
            const cookie = raw.trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function statusBadgeClass(status) {
    const map = {
        ready: 'status-ready',
        pending: 'status-pending',
        running: 'status-running',
        processing: 'status-running',
        paused: 'status-paused',
        stopped: 'status-stopped',
        completed: 'status-completed',
        failed: 'status-failed',
    };
    return map[(status || '').toLowerCase()] || 'status-pending';
}

function escapeHtml(value) {
    const div = document.createElement('div');
    div.textContent = value == null ? '' : String(value);
    return div.innerHTML;
}

class QueueManager {
    constructor() {
        const root = document.querySelector('[data-is-superuser]');
        this.isSuperuser = root ? root.dataset.isSuperuser === 'true' : false;

        this.queue = [];          // unified queue rows from the backend
        this.queueState = 'running';
        this.intervalMinutes = 3;
        this.countdownSeconds = null;  // seconds until the next backend submit
        this.currentPage = 1;
        this.rowsPerPage = 10;

        this.csrfToken = getCookie('csrftoken');

        this.bindEvents();
        this.fetchQueueData();
        setInterval(() => this.fetchQueueData(), REFRESH_INTERVAL_MS);
        // Visual countdown; the backend remains authoritative (resynced each fetch).
        setInterval(() => this.tickCountdown(), 1000);
    }

    // ----- networking ------------------------------------------------------

    async postJson(url, body) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken,
            },
            body: JSON.stringify(body || {}),
        });
        let data = {};
        try {
            data = await response.json();
        } catch (e) {
            data = { status: 'error', message: `HTTP ${response.status}` };
        }
        return { ok: response.ok, status: response.status, data };
    }

    async fetchQueueData() {
        try {
            const response = await fetch('/api/queue/data/', {
                headers: { 'Cache-Control': 'no-cache' },
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            this.queue = data.queue || [];
            this.queueState = data.queue_state || 'running';
            this.intervalMinutes = data.interval_minutes || this.intervalMinutes;
            this.countdownSeconds = (typeof data.next_process_in_seconds === 'number')
                ? data.next_process_in_seconds : null;
            // Trust the server's view of privileges.
            if (typeof data.is_superuser === 'boolean') this.isSuperuser = data.is_superuser;

            const intervalInput = document.getElementById('interval-input');
            if (intervalInput && document.activeElement !== intervalInput) {
                intervalInput.value = this.intervalMinutes;
            }
            this.render();
        } catch (error) {
            console.error('[QUEUE] Failed to load queue data:', error);
            const body = document.getElementById('queue-body');
            if (body) {
                body.innerHTML =
                    '<tr><td colspan="7" class="text-center text-danger">Failed to load queue data.</td></tr>';
            }
        }
    }

    // ----- rendering -------------------------------------------------------

    render() {
        this.renderCountdown();
        this.renderNextJob();
        this.renderTable();
    }

    hasReadyJobs() {
        return this.queue.some(j => ['ready', 'pending'].includes((j.status || '').toLowerCase()));
    }

    tickCountdown() {
        if (typeof this.countdownSeconds === 'number' && this.countdownSeconds > 0) {
            this.countdownSeconds -= 1;
        }
        this.renderCountdown();
    }

    renderCountdown() {
        const el = document.getElementById('auto-process-countdown');
        if (!el) return;
        if (this.queueState !== 'running') {
            el.textContent = this.queueState === 'paused' ? 'Paused' : 'Stopped';
        } else if (!this.hasReadyJobs()) {
            // Nothing to submit — the timer is irrelevant.
            el.textContent = '—';
        } else if (this.countdownSeconds === null) {
            el.textContent = '--:--';
        } else {
            const remaining = Math.max(0, this.countdownSeconds);
            const m = Math.floor(remaining / 60);
            const s = remaining % 60;
            el.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        }
    }

    renderNextJob() {
        const next = this.queue.find(job => (job.status || '').toLowerCase() === 'ready')
            || this.queue.find(job => (job.status || '').toLowerCase() === 'pending');

        const nameEl = document.getElementById('next-job-name');
        const cmdEl = document.getElementById('next-job-command');
        const badgeEl = document.getElementById('next-job-badge');
        const typeEl = document.getElementById('next-job-type');
        if (!nameEl) return;

        if (!next) {
            nameEl.textContent = 'No jobs ready';
            cmdEl.textContent = 'The queue is empty.';
            badgeEl.style.display = 'none';
            typeEl.style.display = 'none';
            return;
        }

        badgeEl.style.display = '';
        typeEl.style.display = '';
        nameEl.textContent = next.fastq_name;
        cmdEl.textContent = next.command || '';
        badgeEl.className = 'status-badge ' + statusBadgeClass(next.status);
        badgeEl.textContent = next.status;
        typeEl.textContent = next.command_source === 'postqc_command' ? 'Post-QC' : 'Alignment';
    }

    get totalPages() {
        return Math.max(1, Math.ceil(this.queue.length / this.rowsPerPage));
    }

    renderTable() {
        const body = document.getElementById('queue-body');
        if (!body) return;

        document.getElementById('queue-count').textContent = this.queue.length;

        if (this.currentPage > this.totalPages) this.currentPage = this.totalPages;
        const start = (this.currentPage - 1) * this.rowsPerPage;
        const pageRows = this.queue.slice(start, start + this.rowsPerPage);

        if (pageRows.length === 0) {
            body.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No jobs in the queue.</td></tr>';
        } else {
            body.innerHTML = pageRows.map(job => this.rowHtml(job)).join('');
        }

        this.renderPagination(start, pageRows.length);
        this.attachRowHandlers();

        const selectAll = document.getElementById('selectAll');
        if (selectAll) selectAll.checked = false;
    }

    rowHtml(job) {
        const canRemove = this.isSuperuser || job.is_owner;
        const canMove = this.isSuperuser
            && ['ready', 'pending'].includes((job.status || '').toLowerCase());

        const owner = job.owner ? escapeHtml(job.owner) : '<span class="text-muted">—</span>';
        const queuedAt = job.queued_at ? new Date(job.queued_at).toLocaleString() : '';

        const checkbox = canRemove
            ? `<div class="form-check"><input class="form-check-input queue-checkbox" type="checkbox"
                   data-fastq="${escapeHtml(job.fastq_name)}"></div>`
            : '';

        let actions = '';
        if (canMove) {
            actions += `<button class="btn btn-outline-secondary move-up-btn" data-fastq="${escapeHtml(job.fastq_name)}"
                            title="Move up"><i class="bi bi-arrow-up"></i></button>`;
            actions += `<button class="btn btn-outline-secondary move-down-btn" data-fastq="${escapeHtml(job.fastq_name)}"
                            title="Move down"><i class="bi bi-arrow-down"></i></button>`;
        }
        if (canRemove) {
            actions += `<button class="btn btn-outline-danger remove-job-btn" data-fastq="${escapeHtml(job.fastq_name)}"
                            title="Remove"><i class="bi bi-trash"></i></button>`;
        }

        return `
            <tr>
                <td>${checkbox}</td>
                <td class="fastq-name-cell">${escapeHtml(job.fastq_name)}</td>
                <td class="owner-cell">${owner}</td>
                <td><span class="command-text">${escapeHtml(job.command)}</span></td>
                <td><span class="status-badge ${statusBadgeClass(job.status)}">${escapeHtml(job.status)}</span></td>
                <td>${escapeHtml(queuedAt)}</td>
                <td><div class="actions-container">${actions || '<span class="text-muted">—</span>'}</div></td>
            </tr>`;
    }

    renderPagination(start, pageCount) {
        const total = this.queue.length;
        document.getElementById('current-page').textContent = this.currentPage;
        document.getElementById('total-pages').textContent = this.totalPages;
        const info = document.getElementById('pagination-info');
        if (info) {
            const from = total === 0 ? 0 : start + 1;
            info.textContent = `Results ${from}-${start + pageCount} of ${total}`;
        }
        const goto = document.getElementById('gotoPage');
        if (goto) goto.max = this.totalPages;
    }

    attachRowHandlers() {
        document.querySelectorAll('.remove-job-btn').forEach(btn => {
            btn.addEventListener('click', () => this.removeJob(btn.dataset.fastq));
        });
        document.querySelectorAll('.move-up-btn').forEach(btn => {
            btn.addEventListener('click', () => this.moveJob(btn.dataset.fastq, 'up'));
        });
        document.querySelectorAll('.move-down-btn').forEach(btn => {
            btn.addEventListener('click', () => this.moveJob(btn.dataset.fastq, 'down'));
        });
    }

    // ----- actions available to everyone -----------------------------------

    async removeJob(fastqName) {
        const { ok, data } = await this.postJson('/api/queue/remove/', { id: fastqName });
        if (ok && data.status === 'success') {
            this.toast(`Removed ${fastqName}`, 'success');
            this.fetchQueueData();
        } else {
            this.toast(data.message || 'Failed to remove job', 'danger');
        }
    }

    selectedFastqNames() {
        return [...document.querySelectorAll('.queue-checkbox:checked')].map(cb => cb.dataset.fastq);
    }

    async removeSelected() {
        const ids = [...new Set(this.selectedFastqNames())];
        if (ids.length === 0) {
            this.toast('No jobs selected', 'info');
            return;
        }
        const { ok, data } = await this.postJson('/api/queue/remove-multiple/', { ids });
        if (ok && data.status === 'success') {
            this.toast(`Removed ${data.removed_count} job(s)`, 'success');
            this.fetchQueueData();
        } else {
            this.toast(data.message || 'Failed to remove selected jobs', 'danger');
        }
    }

    // ----- superuser-only actions ------------------------------------------

    async processNow() {
        const { data } = await this.postJson('/api/queue/process/', {});
        if (data.status === 'success') {
            this.toast(data.message || 'Processing next job', 'success');
        } else if (data.status === 'idle') {
            this.toast(data.message || 'Nothing to process', 'info');
        } else {
            this.toast(data.message || 'Processing failed', 'danger');
        }
        this.fetchQueueData();
    }

    async control(action) {
        const { ok, data } = await this.postJson('/api/queue/control/', { action });
        if (ok && data.status === 'success') {
            this.queueState = data.state;
            this.renderCountdown();
            this.toast(`Queue ${data.state}`, 'success');
            this.fetchQueueData();
        } else {
            this.toast(data.message || 'Action failed', 'danger');
        }
    }

    async clearQueue() {
        const { ok, data } = await this.postJson('/api/queue/clear/', {});
        if (ok && data.status === 'success') {
            this.toast(data.message || 'Queue cleared', 'success');
            this.fetchQueueData();
        } else {
            this.toast(data.message || 'Failed to clear queue', 'danger');
        }
    }

    async saveInterval(minutes) {
        const { ok, data } = await this.postJson('/api/queue/control/',
            { action: 'set_interval', minutes });
        if (ok && data.status === 'success') {
            this.intervalMinutes = data.interval_minutes;
            this.toast(`Auto-submit interval set to ${data.interval_minutes} min`, 'success');
            this.fetchQueueData();
        } else {
            this.toast(data.message || 'Failed to set interval', 'danger');
        }
    }

    async moveJob(fastqName, direction) {
        const { ok, data } = await this.postJson('/api/queue/move/', { fastq_name: fastqName, direction });
        if (ok && data.status === 'success') {
            this.fetchQueueData();
        } else {
            this.toast(data.message || 'Failed to move job', data.status === 'warning' ? 'info' : 'danger');
        }
    }

    // ----- events ----------------------------------------------------------

    bindEvents() {
        const on = (id, event, handler) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener(event, handler);
        };

        on('refresh-queue-btn', 'click', () => this.fetchQueueData());

        on('remove-selected-btn', 'click', () => {
            const modalEl = document.getElementById('confirmRemoveSelectedModal');
            const ids = [...new Set(this.selectedFastqNames())];
            const summary = document.getElementById('selected-items-summary');
            if (summary) {
                summary.innerHTML = ids.length
                    ? `<strong>${ids.length}</strong> job(s) selected.`
                    : 'No jobs selected.';
            }
            if (modalEl && window.bootstrap) {
                bootstrap.Modal.getOrCreateInstance(modalEl).show();
            }
        });
        on('confirmRemoveSelectedBtn', 'click', () => {
            this.hideModal('confirmRemoveSelectedModal');
            this.removeSelected();
        });

        on('selectAll', 'change', (e) => {
            document.querySelectorAll('.queue-checkbox').forEach(cb => { cb.checked = e.target.checked; });
        });

        // Pagination
        on('first-page-btn', 'click', (e) => { e.preventDefault(); this.goToPage(1); });
        on('prev-page-btn', 'click', (e) => { e.preventDefault(); this.goToPage(this.currentPage - 1); });
        on('next-page-btn', 'click', (e) => { e.preventDefault(); this.goToPage(this.currentPage + 1); });
        on('last-page-btn', 'click', (e) => { e.preventDefault(); this.goToPage(this.totalPages); });
        on('gotoPageForm', 'submit', (e) => {
            e.preventDefault();
            const value = parseInt(document.getElementById('gotoPage').value, 10);
            if (!Number.isNaN(value)) this.goToPage(value);
        });
        document.querySelectorAll('#rowsPerPageDropdown + .dropdown-menu .dropdown-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.rowsPerPage = parseInt(item.dataset.value, 10) || 10;
                document.getElementById('rowsPerPageDropdown').textContent = this.rowsPerPage;
                document.querySelectorAll('#rowsPerPageDropdown + .dropdown-menu .dropdown-item')
                    .forEach(i => i.classList.remove('active'));
                item.classList.add('active');
                this.currentPage = 1;
                this.renderTable();
            });
        });

        // Superuser controls (present only when rendered for superusers)
        on('process-queue-btn', 'click', () => this.processNow());
        on('pause-queue-btn', 'click', () => this.control('pause'));
        on('resume-queue-btn', 'click', () => this.control('resume'));
        on('stop-queue-btn', 'click', () => this.control('stop'));
        on('reset-queue-btn', 'click', () => this.control('reset'));
        on('clear-queue-btn', 'click', () => {
            const modalEl = document.getElementById('confirmClearModal');
            if (modalEl && window.bootstrap) bootstrap.Modal.getOrCreateInstance(modalEl).show();
        });
        on('confirmClearBtn', 'click', () => {
            this.hideModal('confirmClearModal');
            this.clearQueue();
        });
        on('save-interval-btn', 'click', () => {
            const value = parseInt(document.getElementById('interval-input').value, 10);
            if (Number.isNaN(value) || value < 1 || value > 60) {
                this.toast('Interval must be between 1 and 60 minutes', 'danger');
                return;
            }
            this.saveInterval(value);
        });
    }

    goToPage(page) {
        const clamped = Math.min(Math.max(1, page), this.totalPages);
        if (clamped !== this.currentPage) {
            this.currentPage = clamped;
            this.renderTable();
        }
    }

    hideModal(id) {
        const modalEl = document.getElementById(id);
        if (modalEl && window.bootstrap) {
            const instance = bootstrap.Modal.getInstance(modalEl);
            if (instance) instance.hide();
        }
    }

    // ----- toast -----------------------------------------------------------

    toast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        const el = document.createElement('div');
        el.className = `toast align-items-center text-bg-${type} border-0 show`;
        el.setAttribute('role', 'alert');
        el.innerHTML = `<div class="toast-body">${escapeHtml(message)}</div>`;
        container.appendChild(el);
        setTimeout(() => el.remove(), 4000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.queueManager = new QueueManager();
});
