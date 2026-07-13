/**
 * Browser AJAX - Dynamic OCS Browser Implementation
 * Connects browser.html to prod_ocs database via AJAX
 */

// Browser AJAX Script loaded

// Production Configuration
const PRODUCTION_CONFIG = {
    debug: false,
    apiBaseUrl: '/',
    defaultPerPage: 25,
    maxRetries: 3,
    requestTimeout: 30000,
    debounceDelay: 300,
    cacheTimeout: 300000, // 5 minutes
    storageKey: 'pipelineSelectedSamples',
    pipelineUrl: '/pipeline/'
};

// UI Constants
const UI_CONSTANTS = {
    // Filter UI
    MAX_FILTER_TAG_LENGTH: 50,
    FILTER_ANIMATION_DURATION: 300,
    FILTER_UPDATE_DELAY: 300,

    // Table UI
    LOADING_OPACITY: 0.6,
    NORMAL_OPACITY: 1,
    TOAST_DURATION: 3000,

    // Data Limits
    CLIENT_SIDE_MAX_RECORDS: 50000,

    // Icons
    ICONS: {
        NOT_COMPLETED: 'bi-circle',
        ERROR: 'bi-x-circle-fill',
        IN_PROGRESS: 'bi-arrow-clockwise',
        PENDING: 'bi-clock-fill',
        COMPLETED: 'bi-check-circle-fill'
    }
};

// Field Mappings
const FIELD_MAPPINGS = {
    DISPLAY_NAMES: {
        'batch_rtx': 'RTX Batches',
        'batch_mtx': 'MTX Batches',
        'batch_atx': 'ATX Batches',
        'study_set': 'Study Set',
        'organism_common_name': 'Organism Common Name',
        'library_prep_method': 'Library Prep Method',
        'ingest_status': 'Ingest Status',
        'alignment_status': 'Alignment Status',
        'postqc_status': 'PostQC Status'
    },

    FILTERABLE_FIELDS: [
        'batch_rtx', 'batch_mtx', 'batch_atx', 'study_set',
        'organism_common_name', 'library_prep_method',
        'ingest_status', 'alignment_status', 'postqc_status'
    ]
};

// Browser state and configuration
const BrowserAJAX = {
    state: {
        currentPage: 1,
        totalPages: 1,
        perPage: 25,
        totalItems: 0,
        searchTerm: '',
        activeFilters: {},
        selectedSamples: [],
        isLoading: false,
        columnSettings: {},
        sortField: null,
        sortDirection: 'asc'
    }
};

// Consolidated utility functions
const Utils = {
    // Debounce function
    debounce(func, wait, immediate = false) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                timeout = null;
                if (!immediate) func(...args);
            };
            const callNow = immediate && !timeout;
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
            if (callNow) func(...args);
        };
    },

    // Throttle function for scroll events
    throttle(func, limit) {
        let inThrottle;
        return function (...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    },

    // Escape HTML to prevent XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // Format date efficiently
    formatDate(dateString) {
        if (!dateString) return '—';
        try {
            return new Date(dateString).toLocaleString();
        } catch {
            return dateString;
        }
    },

    // Log debug messages when debug mode is enabled
    logDebug(message, data) {
        if (PRODUCTION_CONFIG.debug) {
            console.log(`[Browser] ${message}`, data !== undefined ? data : '');
        }
    },

    // Unified loading state management
    setLoadingState(element, isLoading) {
        if (!element) return;
        element.style.opacity = isLoading ? UI_CONSTANTS.LOADING_OPACITY : UI_CONSTANTS.NORMAL_OPACITY;
        element.style.pointerEvents = isLoading ? 'none' : 'auto';
    },

    // Show feedback message
    showMessage(message, type = 'info', duration = UI_CONSTANTS.TOAST_DURATION) {
        const toast = DOMUtils.createElement('div', {
            className: 'material-toast show',
            innerHTML: `
                <div class="material-toast-icon">
                    <i class="bi bi-${type === 'error' ? 'exclamation-triangle' : 'check-circle'}"></i>
                </div>
                <div class="material-toast-message">${this.escapeHtml(message)}</div>
            `
        });

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), UI_CONSTANTS.FILTER_ANIMATION_DURATION);
        }, duration);
    },

    // Get CSRF token for Django AJAX requests
    getCSRFToken() {
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            return metaToken.getAttribute('content');
        }

        const inputToken = document.querySelector('[name=csrfmiddlewaretoken]');
        return inputToken ? inputToken.value : '';
    },

    // Unified error handling
    handleError(error, context = '', showToUser = true) {
        const errorMessage = error?.message || error || 'An unexpected error occurred';
        this.logDebug(`Error in ${context}: ${errorMessage}`, error);

        if (showToUser) {
            this.showMessage(`${context ? context + ': ' : ''}${errorMessage}`, 'error');
        }

        return errorMessage;
    }
};

// DOM Utilities Module
const DOMUtils = {
    /**
     * Create element with attributes and properties
     * @param {string} tagName - Element tag name
     * @param {Object} attributes - Element attributes and properties
     * @returns {HTMLElement} Created element
     */
    createElement(tagName, attributes = {}) {
        const element = document.createElement(tagName);

        Object.entries(attributes).forEach(([key, value]) => {
            if (key === 'innerHTML') {
                element.innerHTML = value;
            } else if (key === 'textContent') {
                element.textContent = value;
            } else if (key === 'className') {
                element.className = value;
            } else if (key.startsWith('data-')) {
                element.setAttribute(key, value);
            } else {
                element[key] = value;
            }
        });

        return element;
    },

    /**
     * Safely select element with error handling
     * @param {string} selector - CSS selector
     * @param {boolean} required - Whether element is required
     * @returns {HTMLElement|null} Selected element or null
     */
    safeSelect(selector, required = false) {
        try {
            const element = document.querySelector(selector);
            if (required && !element) {
                throw new Error(`Required element not found: ${selector}`);
            }
            return element;
        } catch (error) {
            Utils.logDebug(`DOM selection failed: ${selector}`, error);
            return null;
        }
    },

    /**
     * Batch DOM operations to minimize reflows
     * @param {HTMLElement} container - Container element
     * @param {Function} operations - Function containing DOM operations
     */
    batchOperations(container, operations) {
        const fragment = document.createDocumentFragment();
        const originalParent = container.parentNode;

        // Remove from DOM to prevent reflows
        if (originalParent) {
            originalParent.removeChild(container);
        }

        // Perform operations
        operations(fragment);

        // Re-add to DOM
        if (originalParent) {
            originalParent.appendChild(container);
        }
    }
};

// Unified State Manager
const StateManager = {
    // Save any state to localStorage with error handling
    save(key, data) {
        try {
            localStorage.setItem(key, JSON.stringify(data));
            return true;
        } catch (error) {
            Utils.handleError(error, 'Saving state', false);
            return false;
        }
    },

    // Load any state from localStorage with error handling
    load(key, defaultValue = null) {
        try {
            const data = localStorage.getItem(key);
            return data ? JSON.parse(data) : defaultValue;
        } catch (error) {
            Utils.handleError(error, 'Loading state', false);
            return defaultValue;
        }
    },

    // Remove state from localStorage
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (error) {
            Utils.handleError(error, 'Removing state', false);
            return false;
        }
    },

    // Save browser state
    saveBrowserState() {
        const state = {
            searchTerm: BrowserAJAX.state.searchTerm,
            activeFilters: BrowserAJAX.state.activeFilters,
            currentPage: BrowserAJAX.state.currentPage,
            sortField: BrowserAJAX.state.sortField,
            sortDirection: BrowserAJAX.state.sortDirection
        };
        return this.save('browserState', state);
    },

    // Load browser state
    loadBrowserState() {
        const defaultState = {
            searchTerm: '',
            activeFilters: {},
            currentPage: 1,
            sortField: null,
            sortDirection: 'asc'
        };
        return this.load('browserState', defaultState);
    }
};

/**
 * PreferenceSync - persists the user's view (columns + filters) to the server
 * so it follows them across devices. On load the server value wins: it is
 * written into the same localStorage keys the managers already read, so the
 * normal load path applies it once (no second apply). Saves are debounced.
 */
const PreferenceSync = {
    endpoint: '/api/preferences/',
    saveTimer: null,

    async load() {
        try {
            const res = await fetch(this.endpoint, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'same-origin'
            });
            if (!res.ok) return;
            const { filter_preferences } = await res.json();

            // Columns are server-rendered per user (see ocs/columns.py + the view),
            // so they are NOT seeded here. This only mirrors saved filter state into
            // the localStorage keys the filter managers read. "No saved filters"
            // clears them so a different user on a shared browser starts clean.
            if (filter_preferences && filter_preferences.activeFilters) {
                localStorage.setItem('browserFilterState', JSON.stringify({
                    searchTerm: filter_preferences.searchTerm || '',
                    activeFilters: filter_preferences.activeFilters,
                    currentPage: 1
                }));
                if (filter_preferences.filterMode) {
                    localStorage.setItem('filterMode', filter_preferences.filterMode);
                } else {
                    localStorage.removeItem('filterMode');
                }
            } else {
                localStorage.removeItem('browserFilterState');
                localStorage.removeItem('filterMode');
            }
        } catch (error) {
            console.warn('[PreferenceSync] Could not load preferences:', error);
        }
    },

    save() {
        clearTimeout(this.saveTimer);
        this.saveTimer = setTimeout(() => {
            fetch(this.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': Utils.getCSRFToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    column_settings: BrowserAJAX.state.columnSettings,
                    filter_preferences: {
                        searchTerm: BrowserAJAX.state.searchTerm,
                        activeFilters: BrowserAJAX.state.activeFilters,
                        filterMode: FilterDataManager.state.filterMode
                    }
                })
            }).catch(error => console.warn('[PreferenceSync] Could not save preferences:', error));
        }, 800);
    }
};

// Simplified API Manager
const APIManager = {
    cache: new Map(),

    async makeRequest(url, options = {}) {
        Utils.logDebug('makeRequest() called', { url, options });

        const cacheKey = `${url}_${JSON.stringify(options)}`;

        // Check cache first
        if (this.cache.has(cacheKey)) {
            const cached = this.cache.get(cacheKey);
            if (Date.now() - cached.timestamp < PRODUCTION_CONFIG.cacheTimeout) {
                Utils.logDebug('Returning cached response');
                return cached.data;
            }
            this.cache.delete(cacheKey);
        }

        const defaultOptions = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': Utils.getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            signal: AbortSignal.timeout(PRODUCTION_CONFIG.requestTimeout)
        };

        const finalOptions = { ...defaultOptions, ...options };

        try {
            Utils.logDebug(`Making fetch request to: ${url}`);
            const response = await fetch(url, finalOptions);
            Utils.logDebug(`Response received - Status: ${response.status}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentType = response.headers.get('content-type');
            let result;

            if (contentType && contentType.includes('application/json')) {
                result = await response.json();
                Utils.logDebug('JSON response parsed successfully');
            } else {
                result = await response.text();
                Utils.logDebug('Text response received');
            }

            // Cache successful responses
            this.cache.set(cacheKey, {
                data: result,
                timestamp: Date.now()
            });

            return result;

        } catch (error) {
            Utils.logDebug('Request failed:', error);
            throw error;
        }
    },

    // Clear cache
    clearCache() {
        this.cache.clear();
        Utils.logDebug('Cache cleared');
    },

    // Fetch samples data with filters and pagination
    async fetchSamples(params = {}) {

        const queryParams = new URLSearchParams({
            page: BrowserAJAX.state.currentPage,
            per_page: BrowserAJAX.state.perPage,
            search: BrowserAJAX.state.searchTerm,
            ...BrowserAJAX.state.activeFilters,
            ...params
        });

        // Add sorting parameters if present
        if (BrowserAJAX.state.sortField) {
            queryParams.set('sort_by', BrowserAJAX.state.sortField);
            queryParams.set('sort_direction', BrowserAJAX.state.sortDirection);
        }

        // Remove empty parameters
        for (const [key, value] of [...queryParams.entries()]) {
            if (!value || value === '') {
                queryParams.delete(key);
            }
        }

        const url = `${PRODUCTION_CONFIG.apiBaseUrl}?${queryParams.toString()}`;

        const result = await this.makeRequest(url, {
            headers: {
                'Accept': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });

        return result;
    }
};

// Simplified table manager
const TableManager = {
    currentData: [],

    init() {
        // TableManager is ready - no complex initialization needed
    },

    renderTable(data) {
        const startTime = PRODUCTION_CONFIG.debug ? performance.now() : null;

        const tbody = document.querySelector('table tbody');
        if (!tbody) {
            Utils.logDebug('Table tbody not found');
            return;
        }

        this.currentData = data.samples || [];
        this.renderStandardTable(data);
        this.updatePaginationInfo(data.pagination);
        this.updateSampleCount(data.pagination);

        if (PRODUCTION_CONFIG.debug && startTime) {
            const duration = performance.now() - startTime;
            Utils.logDebug(`renderTable completed in ${duration.toFixed(2)}ms`);
        }
    },

    renderStandardTable(data) {
        const tbody = document.querySelector('table tbody');
        const fragment = document.createDocumentFragment();

        if (!data.samples || data.samples.length === 0) {
            const emptyRow = this.createEmptyRow();
            fragment.appendChild(emptyRow);
        } else {
            data.samples.forEach(sample => {
                const row = this.createSampleRow(sample);
                fragment.appendChild(row);
            });
        }

        tbody.innerHTML = '';
        tbody.appendChild(fragment);

        // Reinitialize functionality after DOM update
        if (typeof SelectionManager !== 'undefined' && SelectionManager.initializeCheckboxes) {
            SelectionManager.initializeCheckboxes();
        }
        if (typeof ColumnManager !== 'undefined' && ColumnManager.applyColumnSettings) {
            ColumnManager.applyColumnSettings();
        }
        if (typeof SortingManager !== 'undefined' && SortingManager.updateSortIndicators) {
            SortingManager.updateSortIndicators();
        }
    },

    createSampleRow(sample) {
        const row = document.createElement('tr');

        // Set data attributes
        row.dataset.fastqId = sample.fastq_name || '';
        row.dataset.fastqName = sample.fastq_name || '';
        row.dataset.batchNameFromVendor = sample.batch_name_from_vendor || '';
        row.dataset.organism = sample.organism || '';
        row.dataset.organismCommonName = sample.organism_common_name || '';
        row.dataset.libraryPrepMethod = sample.library_prep_method || '';
        row.dataset.studySet = sample.study_set || '';
        row.dataset.loadName = sample.load_name || '';
        row.dataset.ingestStatus = sample.ingest_status || '';
        row.dataset.alignmentStatus = sample.alignment_status || '';
        row.dataset.postqcStatus = sample.postqc_status || '';

        // Create cells efficiently using consolidated method
        const cells = [
            this.createCell('selection'),
            this.createCell('text', sample.fastq_name, 'field-fastq_name'),
            this.createCell('text', sample.study_set, 'field-study_set'),
            this.createCell('text', sample.load_name, 'field-load_name'),
            this.createCell('text', sample.library_prep_method, 'field-library_prep_method'),
            this.createCell('text', sample.organism, 'field-organism'),
            this.createCell('text', sample.organism_common_name, 'field-organism_common_name'),
            this.createCell('text', sample.batch_name_from_vendor, 'field-batch_name_from_vendor'),
            this.createCell('text', sample.cell_capture, 'field-cell_capture'),
            this.createCell('text', sample.sample_id, 'field-sample_id'),
            this.createCell('text', sample.amplification_name, 'field-amplification_name'),
            this.createCell('text', sample.amplification_id, 'field-amplification_id'),
            this.createCell('text', sample.cell_prep_type, 'field-cell_prep_type'),
            this.createCell('text', sample.sequencing_vendor, 'field-sequencing_vendor'),
            this.createCell('text', sample.alignment_method, 'field-alignment_method'),
            this.createCell('text', sample.library_prep_method_id, 'field-library_prep_method_id'),
            this.createCell('text', sample.library_prep_name, 'field-library_prep_name'),
            this.createCell('status', sample.ingest_status, 'field-ingest_status'),
            this.createCell('fid', sample.ingest_fid, 'field-ingest_fid'),
            this.createCell('text', Utils.formatDate(sample.ingest_start_time), 'field-ingest_start_time'),
            this.createCell('text', Utils.formatDate(sample.ingest_end_time), 'field-ingest_end_time'),
            this.createCell('status', sample.alignment_status, 'field-alignment_status'),
            this.createCell('fid', sample.alignment_fid, 'field-alignment_fid'),
            this.createCell('text', Utils.formatDate(sample.alignment_start_time), 'field-alignment_start_time'),
            this.createCell('text', Utils.formatDate(sample.alignment_end_time), 'field-alignment_end_time'),
            this.createCell('status', sample.postqc_status, 'field-postqc_status'),
            this.createCell('fid', sample.postqc_fid, 'field-postqc_fid'),
            this.createCell('text', Utils.formatDate(sample.postqc_start_time), 'field-postqc_start_time'),
            this.createCell('text', Utils.formatDate(sample.postqc_end_time), 'field-postqc_end_time')
        ];

        cells.forEach(cell => row.appendChild(cell));
        return row;
    },

    // Simplified cell creation method
    createCell(type, content = '', className = '') {
        const cell = document.createElement('td');

        switch (type) {
            case 'selection':
                cell.className = 'selection-column';
                cell.innerHTML = '<input type="checkbox" class="sample-select">';
                break;

            case 'status':
                cell.className = className;
                cell.appendChild(this.createStatusBadge(content));
                break;

            case 'fid':
                cell.className = `${className} fid-column`;
                cell.title = 'Click to copy FID';
                cell.textContent = content || '—';
                break;

            case 'text':
            default:
                cell.className = className;
                cell.textContent = content || '—';
                break;
        }

        return cell;
    },

    createStatusBadge(status) {
        // Shared status badge (icon + label) matching status_badge.html and the
        // other pages — green Completed, blue In Progress, grey otherwise.
        // Case-insensitive; anything that isn't a real status reads "Not Completed".
        const badge = document.createElement('span');
        badge.className = 'status-badge';
        const s = (status || '').toLowerCase().trim();

        let icon, label;
        if (s === 'completed' || s === 'complete') {
            badge.classList.add('status-completed'); icon = 'bi-check-circle-fill'; label = 'Completed';
        } else if (s.includes('in progress') || s === 'running') {
            badge.classList.add('status-in-progress'); icon = 'bi-arrow-clockwise'; label = 'In Progress';
        } else if (s.includes('fail') || s.includes('error') || s.includes('killed')) {
            badge.classList.add('status-failed'); icon = 'bi-x-circle-fill'; label = status;
        } else if (s.includes('pending') || s === 'submitted' || s === 'queued') {
            badge.classList.add('status-pending'); icon = 'bi-clock-fill'; label = status;
        } else {
            badge.classList.add('status-not-completed'); icon = 'bi-circle';
            label = (s && s !== 'not started' && s !== 'not completed') ? status : 'Not Completed';
        }

        const i = document.createElement('i');
        i.className = 'bi ' + icon;
        const text = document.createElement('span');
        text.className = 'status-text';
        text.textContent = label;
        badge.append(i, text);
        return badge;
    },

    createEmptyRow() {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 30;
        cell.className = 'text-center py-4';
        cell.innerHTML = '<div class="text-muted"><i class="bi bi-inbox me-2"></i>No samples found matching your criteria</div>';
        row.appendChild(cell);
        return row;
    },

    updatePaginationInfo(pagination) {
        if (!pagination) return;

        BrowserAJAX.state.currentPage = pagination.current_page || 1;
        BrowserAJAX.state.totalPages = pagination.total_pages || 1;
        BrowserAJAX.state.totalItems = pagination.total_items || 0;
        BrowserAJAX.state.perPage = pagination.per_page || 25;

        PaginationManager.updateControls(pagination);
    },

    updateSampleCount(pagination) {
        const countBadge = document.querySelector('.card-header .badge');
        if (countBadge && pagination) {
            const start = ((pagination.current_page - 1) * pagination.per_page) + 1;
            const end = Math.min(pagination.current_page * pagination.per_page, pagination.total_items);
            countBadge.textContent = `${end} of ${pagination.total_items} samples`;
        }
    },

    // Simplified data loading
    async loadData(showLoader = true) {
        if (BrowserAJAX.state.isLoading) {
            Utils.logDebug('Already loading, skipping...');
            return;
        }

        const startTime = PRODUCTION_CONFIG.debug ? performance.now() : null;
        BrowserAJAX.state.isLoading = true;

        const tableContainer = document.querySelector('.table-responsive');
        if (showLoader && tableContainer) {
            Utils.setLoadingState(tableContainer, true);
        }

        try {
            Utils.logDebug('Loading data with current state');
            const data = await APIManager.fetchSamples();
            Utils.logDebug('Received data from API');

            const samples = data.samples || data.results || (Array.isArray(data) ? data : []);
            const pagination = data.pagination || {
                current_page: BrowserAJAX.state.currentPage,
                total_pages: data.total_pages || 1,
                per_page: BrowserAJAX.state.perPage,
                total_items: data.total_items || data.count || samples.length,
                has_next: data.has_next || false,
                has_previous: data.has_previous || false
            };

            Utils.logDebug(`Processing ${samples.length} samples`);
            this.renderTable({ samples, pagination });

            if (FilterManager.state.filterMode === 'server-side') {
                FilterManager.updateActiveFiltersDisplay();
            }

        } catch (error) {
            Utils.handleError(error, 'Loading data');

            this.renderTable({
                samples: [],
                pagination: {
                    current_page: 1,
                    total_pages: 1,
                    per_page: BrowserAJAX.state.perPage,
                    total_items: 0
                }
            });

        } finally {
            BrowserAJAX.state.isLoading = false;
            if (showLoader && tableContainer) {
                Utils.setLoadingState(tableContainer, false);
            }
            if (PRODUCTION_CONFIG.debug && startTime) {
                const duration = performance.now() - startTime;
                Utils.logDebug(`loadData completed in ${duration.toFixed(2)}ms`);
            }
            Utils.logDebug('TableManager.loadData() completed');
        }
    }
};

/**
 * Enhanced Filter System - Modular filtering functionality
 * 
 * ARCHITECTURE:
 * - FilterDataManager: Data loading, caching, and options extraction
 * - FilterUIManager: UI components, DOM manipulation, and visual updates
 * - FilterLogicManager: Core filtering logic and application
 * - FilterStateManager: State persistence, restoration, and URL management
 * - FilterExtrasManager: Export/import, statistics, and additional features
 * - FilterManager: Main coordinator that delegates to sub-managers
 */

/**
 * FilterDataManager - Handles data loading, caching, and filter options
 */
const FilterDataManager = {
    state: {
        allData: [],           // Complete dataset for client-side filtering
        filteredData: [],      // Currently filtered dataset
        filterOptions: {},     // Available options for each filter
        filterMode: 'realtime' // 'realtime', 'manual', or 'server-side'
    },

    /**
     * Load complete dataset for client-side filtering
     */
    async loadCompleteDataset() {

        try {
            // First, try to get total count
            let totalRecords = 0;
            let allSamples = [];

            // Initial request to get total count
            const initialResponse = await APIManager.fetchSamples({
                page: 1,
                per_page: 1,
                count_only: true
            });

            // Extract total count from response
            totalRecords = initialResponse.pagination?.total_items ||
                initialResponse.total_items ||
                initialResponse.count || 0;


            // If we have a reasonable number of records, load them all client-side
            // For larger datasets, we'll fall back to server-side filtering
            if (totalRecords > 0 && totalRecords <= UI_CONSTANTS.CLIENT_SIDE_MAX_RECORDS) {

                // Fetch all data without pagination limit for client-side filtering
                const response = await APIManager.fetchSamples({
                    page: 1,
                    per_page: totalRecords, // Use actual total count
                    no_pagination: true
                });

                allSamples = response.samples || [];
                if (allSamples.length < totalRecords) {
                    console.warn(`[FilterDataManager] Loaded ${allSamples.length} of ${totalRecords} records.`);
                }

            } else if (totalRecords > UI_CONSTANTS.CLIENT_SIDE_MAX_RECORDS) {
                this.state.filterMode = 'server-side';
                Utils.showMessage(`Dataset contains ${totalRecords.toLocaleString()} records. Using server-side filtering for performance.`, 'info', 5000);
                throw new Error('Dataset too large for client-side filtering');

            } else {
                allSamples = [];
            }

            this.state.allData = allSamples;
            this.state.filteredData = [...this.state.allData];


            // Extract unique filter options from actual data
            this.extractFilterOptions();

        } catch (error) {
            console.error('[FilterDataManager] Error loading dataset:', error);
            // Fallback to server-side filtering if client-side fails
            this.state.filterMode = 'server-side';
            Utils.showMessage('Unable to load complete dataset. Using server-side filtering.', 'warning', 4000);
            throw error;
        }
    },

    /**
     * Extract unique filter options from actual data (Excel-like)
     */
    extractFilterOptions() {

        const options = {
            batch_rtx: new Set(),
            batch_mtx: new Set(),
            batch_atx: new Set(),
            study_sets: new Set(),
            organism_common_names: new Set(),
            library_prep_methods: new Set(),
            ingest_status_options: new Set(),
            alignment_status_options: new Set(),
            postqc_status_options: new Set()
        };

        // Extract unique values from actual data
        this.state.allData.forEach(sample => {
            // Categorize batch names by prefix
            if (sample.batch_name_from_vendor) {
                const batchName = sample.batch_name_from_vendor;
                if (batchName.startsWith('RTX')) {
                    options.batch_rtx.add(batchName);
                } else if (batchName.startsWith('MTX')) {
                    options.batch_mtx.add(batchName);
                } else if (batchName.startsWith('ATX')) {
                    options.batch_atx.add(batchName);
                }
            }

            if (sample.study_set) options.study_sets.add(sample.study_set);
            if (sample.organism_common_name) options.organism_common_names.add(sample.organism_common_name);
            if (sample.library_prep_method) options.library_prep_methods.add(sample.library_prep_method);
            if (sample.ingest_status) options.ingest_status_options.add(sample.ingest_status);
            if (sample.alignment_status) options.alignment_status_options.add(sample.alignment_status);
            if (sample.postqc_status) options.postqc_status_options.add(sample.postqc_status);
        });

        // Convert Sets to sorted Arrays with custom sorting for batch types
        this.state.filterOptions = Object.fromEntries(
            Object.entries(options).map(([key, valueSet]) => {
                const values = Array.from(valueSet).filter(Boolean);

                // Special sorting for batch types (by numeric value, descending)
                if (key === 'batch_rtx' || key === 'batch_mtx' || key === 'batch_atx') {
                    return [key, values.sort((a, b) => {
                        // Extract numeric part from batch names (e.g., "RTX-1501" -> 1501)
                        const getNumericPart = (batchName) => {
                            const match = batchName.match(/-(\d+)/);
                            return match ? parseInt(match[1]) : 0;
                        };

                        const numA = getNumericPart(a);
                        const numB = getNumericPart(b);

                        // Sort in descending order (largest number first)
                        return numB - numA;
                    })];
                } else {
                    // Regular alphabetical sorting for other filters
                    return [key, values.sort()];
                }
            })
        );

    },

    /**
     * Get filter options for a specific field with record counts
     */
    getFilterOptionsWithCounts(fieldName) {
        const options = this.state.filterOptions[fieldName] || [];
        return options.map(option => {
            const count = this.state.allData.filter(sample => {
                const sampleValue = sample[fieldName];
                return sampleValue === option;
            }).length;
            return { value: option, count };
        });
    }
};

/**
 * FilterLogicManager - Handles core filtering logic and application
 */
const FilterLogicManager = {
    /**
     * Apply all filters client-side (Excel-like performance)
     */
    applyAllFilters() {
        const startTime = PRODUCTION_CONFIG.debug ? performance.now() : null;

        // Start with all data
        let filtered = [...FilterDataManager.state.allData];

        // Apply search filter
        if (BrowserAJAX.state.searchTerm) {
            const searchTerm = BrowserAJAX.state.searchTerm.toLowerCase();
            filtered = filtered.filter(sample => {
                return Object.values(sample).some(value =>
                    value && value.toString().toLowerCase().includes(searchTerm)
                );
            });
        }

        // Apply dropdown filters (AND logic - Excel-like)
        Object.entries(BrowserAJAX.state.activeFilters).forEach(([filterName, selectedValues]) => {
            if (selectedValues && selectedValues.length > 0) {
                filtered = filtered.filter(sample => {
                    // Handle batch type filters specially
                    if (filterName === 'batch_rtx' || filterName === 'batch_mtx' || filterName === 'batch_atx') {
                        const sampleBatchName = sample.batch_name_from_vendor;
                        return selectedValues.includes(sampleBatchName);
                    } else {
                        // Filter names match the sample field names directly.
                        return selectedValues.includes(sample[filterName]);
                    }
                });
            }
        });

        // Update filtered data
        FilterDataManager.state.filteredData = filtered;

        // Apply sorting if a sort field is set
        if (BrowserAJAX.state.sortField && typeof SortingManager !== 'undefined') {
            SortingManager.applySortToFilteredData();
        }

        // Apply pagination to filtered data
        const startIndex = (BrowserAJAX.state.currentPage - 1) * BrowserAJAX.state.perPage;
        const endIndex = startIndex + BrowserAJAX.state.perPage;
        const paginatedData = FilterDataManager.state.filteredData.slice(startIndex, endIndex);

        // Create pagination info
        const pagination = {
            current_page: BrowserAJAX.state.currentPage,
            per_page: BrowserAJAX.state.perPage,
            total_items: FilterDataManager.state.filteredData.length,
            total_pages: Math.ceil(FilterDataManager.state.filteredData.length / BrowserAJAX.state.perPage),
            has_next: endIndex < FilterDataManager.state.filteredData.length,
            has_previous: BrowserAJAX.state.currentPage > 1
        };

        // Update table with filtered data
        TableManager.renderTable({
            samples: paginatedData,
            pagination: pagination
        });

        if (PRODUCTION_CONFIG.debug && startTime) {
            const duration = performance.now() - startTime;
        }

        // Update filter statistics
        FilterManager.updateFilterStatistics();
    },

    /**
     * Handle filter change events
     */
    handleFilterChange(selectElement) {
        const filterName = selectElement.name;
        const selectedValues = $(selectElement).val() || [];


        // Update filter state
        if (selectedValues.length > 0) {
            BrowserAJAX.state.activeFilters[filterName] = selectedValues;
        } else {
            delete BrowserAJAX.state.activeFilters[filterName];
        }

        // Real-time mode applies immediately; manual mode waits for "Apply Filters".
        if (FilterDataManager.state.filterMode === 'realtime') {
            this.applyAllFilters();
        }

        // Update UI
        FilterManager.updateActiveFiltersDisplay();
        FilterManager.updateFilterState();
        FilterManager.updateFilterStatistics();
    },

    /**
     * Clear all active filters
     */
    clearAllFilters() {
        // Clear search input
        const searchInput = document.getElementById('search-input');
        if (searchInput) {
            searchInput.value = '';
        }

        // Clear all filter dropdowns
        $('.filter-select').val(null).trigger('change');

        // Reset state
        BrowserAJAX.state.searchTerm = '';
        BrowserAJAX.state.activeFilters = {};
        BrowserAJAX.state.currentPage = 1;

        // Apply filters
        if (FilterDataManager.state.filterMode === 'realtime') {
            this.applyAllFilters();
        } else {
            TableManager.loadData();
        }

        // Update UI
        FilterManager.updateActiveFiltersDisplay();
        FilterManager.updateFilterState();

        Utils.showMessage('All filters cleared', 'success');
    }
};

/**
 * FilterUIManager - Handles UI components, DOM manipulation, and visual updates
 */
const FilterUIManager = {
    /**
     * Initialize search input with enhanced debouncing
     */
    async initializeSearchInput() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        // Enhanced debounced search with loading indicator
        const debouncedSearch = Utils.debounce((searchTerm) => {
            BrowserAJAX.state.searchTerm = searchTerm;

            if (FilterDataManager.state.filterMode === 'realtime') {
                FilterManager.applyAllFilters();
            } else {
                BrowserAJAX.state.currentPage = 1;
                TableManager.loadData();
            }

            FilterManager.updateFilterState();
        }, PRODUCTION_CONFIG.debounceDelay);

        // Enhanced search input with clear button
        searchInput.addEventListener('input', (e) => {
            const value = e.target.value;

            // Show/hide clear button
            const clearButton = searchInput.parentElement.querySelector('.search-clear');
            if (clearButton) {
                clearButton.style.display = value ? 'block' : 'none';
            }

            debouncedSearch(value);
        });

        // Add clear search functionality
        const clearButton = searchInput.parentElement.querySelector('.search-clear');
        if (clearButton) {
            clearButton.addEventListener('click', () => {
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
                searchInput.focus();
            });
        }

        // Handle form submission
        const searchForm = document.getElementById('filter-form');
        if (searchForm) {
            searchForm.addEventListener('submit', (e) => {
                e.preventDefault();
                BrowserAJAX.state.searchTerm = searchInput.value;

                if (FilterDataManager.state.filterMode === 'realtime') {
                    FilterManager.applyAllFilters();
                } else {
                    BrowserAJAX.state.currentPage = 1;
                    TableManager.loadData();
                }

                FilterManager.updateFilterState();
            });
        }
    },

    /**
     * Initialize enhanced filter dropdowns with Excel-like functionality
     */
    async initializeFilterDropdowns() {

        try {
            // Populate dropdowns with actual data options
            this.populateFilterDropdown('batch_rtx', FilterDataManager.state.filterOptions.batch_rtx);
            this.populateFilterDropdown('batch_mtx', FilterDataManager.state.filterOptions.batch_mtx);
            this.populateFilterDropdown('batch_atx', FilterDataManager.state.filterOptions.batch_atx);
            this.populateFilterDropdown('study_set', FilterDataManager.state.filterOptions.study_sets);
            this.populateFilterDropdown('organism_common_name', FilterDataManager.state.filterOptions.organism_common_names);
            this.populateFilterDropdown('library_prep_method', FilterDataManager.state.filterOptions.library_prep_methods);
            this.populateFilterDropdown('ingest_status', FilterDataManager.state.filterOptions.ingest_status_options);
            this.populateFilterDropdown('alignment_status', FilterDataManager.state.filterOptions.alignment_status_options);
            this.populateFilterDropdown('postqc_status', FilterDataManager.state.filterOptions.postqc_status_options);

            // Initialize Select2 with enhanced configuration
            $('.filter-select').select2({
                theme: 'bootstrap4',
                width: '100%',
                placeholder: function () {
                    const selectName = this.element[0].name;
                    const count = this.element[0].options.length;
                    return `Select from ${count} options`;
                },
                allowClear: true,
                closeOnSelect: false,
                templateResult: this.formatFilterOption,
                templateSelection: this.formatFilterSelection
            });

            // Enhanced filter change handler with real-time updates
            $('.filter-select').on('change', (e) => {
                FilterManager.handleFilterChange(e.target);
            });

            // Add "Select All" / "Clear All" functionality
            this.addSelectAllFunctionality();

        } catch (error) {
            console.error('[FilterUIManager] Error initializing dropdowns:', error);
            Utils.showMessage('Failed to initialize filter dropdowns', 'error');
        }
    },

    /**
     * Enhanced dropdown population with statistics
     */
    populateFilterDropdown(selectId, options) {
        const select = document.getElementById(selectId);
        if (!select) {
            console.warn(`[FilterUIManager] Select element with ID "${selectId}" not found`);
            return;
        }

        if (!options || options.length === 0) {
            console.warn(`[FilterUIManager] No options provided for "${selectId}"`);
            return;
        }


        // Clear existing options
        select.innerHTML = '';

        // Count records more efficiently by doing it once for all options
        const allData = FilterDataManager.state.allData;

        // Create count map for all options at once
        const countMap = {};
        options.forEach(option => countMap[option] = 0);

        // Count occurrences of each option in the data
        allData.forEach(sample => {
            // Handle batch type filters specially
            if (selectId === 'batch_rtx' || selectId === 'batch_mtx' || selectId === 'batch_atx') {
                const sampleBatchName = sample.batch_name_from_vendor;
                if (sampleBatchName && countMap.hasOwnProperty(sampleBatchName)) {
                    countMap[sampleBatchName]++;
                }
            } else {
                // Regular field counting
                const sampleValue = sample[selectId];
                if (sampleValue && countMap.hasOwnProperty(sampleValue)) {
                    countMap[sampleValue]++;
                }
            }
        });


        // Add options with counts
        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option;
            const count = countMap[option] || 0;

            optionElement.textContent = `${option} (${count})`;
            optionElement.dataset.count = count;
            select.appendChild(optionElement);
        });

    },

    /**
     * Enhanced active filters display with statistics
     */
    updateActiveFiltersDisplay() {
        const container = document.querySelector('.active-filters-container');
        if (!container) {
            console.warn('[FilterUIManager] Active filters container not found');
            return;
        }

        // Clear existing content
        container.innerHTML = '';
        let hasActiveFilters = false;


        // Add search term
        if (BrowserAJAX.state.searchTerm) {
            hasActiveFilters = true;
            this.createFilterTag(container, 'search', BrowserAJAX.state.searchTerm,
                `Search: "${BrowserAJAX.state.searchTerm}"`);
        }

        // Add filter selections with counts
        Object.entries(BrowserAJAX.state.activeFilters).forEach(([filterName, values]) => {
            if (Array.isArray(values) && values.length > 0) {
                hasActiveFilters = true;
                values.forEach(value => {
                    const displayText = `${this.getFilterDisplayName(filterName)}: ${value}`;
                    this.createFilterTag(container, filterName, value, displayText);
                });
            }
        });

        // Add summary and show/hide container
        if (hasActiveFilters || FilterDataManager.state.filteredData.length !== FilterDataManager.state.allData.length) {
            // Create filter summary header
            const summary = document.createElement('div');
            summary.className = 'filter-summary';
            summary.innerHTML = `
                <i class="bi bi-funnel-fill"></i>
                <span class="filter-count">
                    Active Filters: Showing ${FilterDataManager.state.filteredData.length.toLocaleString()} of ${FilterDataManager.state.allData.length.toLocaleString()} records
                </span>
            `;
            container.prepend(summary);

            // Show container with proper display
            container.style.display = 'flex';
            container.style.visibility = 'visible';
            container.style.opacity = '1';

        } else {
            // Hide container when no filters
            container.style.display = 'none';
            container.style.visibility = 'hidden';
            container.style.opacity = '0';
        }
    },

    /**
     * Enhanced filter tag creation with better UX
     */
    createFilterTag(container, filterName, value, displayText) {
        const tag = document.createElement('div');
        tag.className = 'filter-tag';
        tag.setAttribute('data-filter', filterName);
        tag.setAttribute('data-value', value);
        tag.setAttribute('title', displayText);

        // Truncate display text if too long
        const maxLength = UI_CONSTANTS.MAX_FILTER_TAG_LENGTH;
        const truncatedText = displayText.length > maxLength
            ? displayText.substring(0, maxLength) + '...'
            : displayText;

        tag.innerHTML = `
            <span class="tag-value" title="${Utils.escapeHtml(displayText)}">${Utils.escapeHtml(truncatedText)}</span>
            <button type="button" class="tag-remove" aria-label="Remove filter: ${Utils.escapeHtml(displayText)}" title="Remove this filter">
                <i class="bi bi-x"></i>
            </button>
        `;

        // Enhanced remove functionality
        const removeButton = tag.querySelector('.tag-remove');
        removeButton.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();

            this.removeFilterTag(filterName, value);
        });

        // Add hover effects
        tag.addEventListener('mouseenter', () => {
            const rect = container.getBoundingClientRect();
            const tagRect = tag.getBoundingClientRect();

            if (tagRect.top > rect.top + 5) {
                tag.style.transform = 'translateY(-2px) scale(1.02)';
            } else {
                tag.style.transform = 'scale(1.02)';
            }
        });

        tag.addEventListener('mouseleave', () => {
            tag.style.transform = 'scale(1)';
        });

        container.appendChild(tag);
        return tag;
    },

    /**
     * Enhanced filter tag removal with real-time updates
     */
    removeFilterTag(filterName, value) {

        if (filterName === 'search') {
            const searchInput = document.getElementById('search-input');
            if (searchInput) {
                searchInput.value = '';
                searchInput.dispatchEvent(new Event('input'));
            }
            BrowserAJAX.state.searchTerm = '';
        } else {
            const select = document.getElementById(filterName);
            if (select) {
                const currentValues = $(select).val() || [];
                const newValues = currentValues.filter(v => v !== value);
                $(select).val(newValues).trigger('change');
                return; // The change event will handle the rest
            }
        }

        // Apply filters and update UI
        if (FilterDataManager.state.filterMode === 'realtime') {
            FilterManager.applyAllFilters();
        } else {
            BrowserAJAX.state.currentPage = 1;
            TableManager.loadData();
        }

        this.updateActiveFiltersDisplay();
        FilterManager.updateFilterState();
    },

    /**
     * Helper methods for dropdowns
     */
    formatFilterOption(option) {
        return option.text || option.id;
    },

    formatFilterSelection(option) {
        return option.text || option.id;
    },

    addSelectAllFunctionality() {
        $('.filter-select').each(function () {
            const $select = $(this);

            // Add select all option
            $select.prepend('<option value="__SELECT_ALL__">Select All</option>');

            // Handle select all
            $select.on('change', function () {
                const values = $select.val() || [];

                if (values.includes('__SELECT_ALL__')) {
                    // Select all options except the select all option
                    const allOptions = Array.from(this.options)
                        .filter(opt => opt.value !== '__SELECT_ALL__')
                        .map(opt => opt.value);

                    $select.val(allOptions).trigger('change.select2');
                }
            });
        });
    },

    /**
     * Get display name for filter with enhanced formatting
     */
    getFilterDisplayName(filterName) {
        return FIELD_MAPPINGS.DISPLAY_NAMES[filterName] ||
            filterName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    }
};

/**
 * FilterStateManager - Handles state persistence, restoration, and URL management
 */
const FilterStateManager = {
    /**
     * Update filter state in localStorage and URL
     */
    updateFilterState() {
        // Filter mode is persisted separately (under the 'filterMode' key) by the
        // mode toggle; keep it out of here so there is a single source per concept.
        const state = {
            searchTerm: BrowserAJAX.state.searchTerm,
            activeFilters: BrowserAJAX.state.activeFilters,
            currentPage: BrowserAJAX.state.currentPage
        };

        // Save to localStorage
        localStorage.setItem('browserFilterState', JSON.stringify(state));

        // Update URL (without page reload)
        const url = new URL(window.location);
        url.search = ''; // Clear existing params

        if (state.searchTerm) {
            url.searchParams.set('search', state.searchTerm);
        }

        if (FilterDataManager.state.filterMode !== 'realtime') {
            url.searchParams.set('filterMode', FilterDataManager.state.filterMode);
        }

        Object.entries(state.activeFilters).forEach(([key, values]) => {
            if (values && values.length > 0) {
                url.searchParams.set(key, values.join(','));
            }
        });

        if (state.currentPage > 1) {
            url.searchParams.set('page', state.currentPage);
        }

        window.history.replaceState({}, '', url);

        // Mirror the filter state to the server for cross-device sync.
        PreferenceSync.save();
    },

    /**
     * Restore filter state from URL/localStorage
     */
    async restoreFilterState() {

        // First try URL parameters
        const url = new URL(window.location);
        const hasUrlParams = url.search.length > 0;

        if (hasUrlParams) {
            // Restore from URL
            const searchParam = url.searchParams.get('search');
            if (searchParam) {
                BrowserAJAX.state.searchTerm = searchParam;
                const searchInput = document.getElementById('search-input');
                if (searchInput) searchInput.value = searchParam;
            }

            // Restore filter mode from URL if present
            const filterModeParam = url.searchParams.get('filterMode');
            if (filterModeParam && ['realtime', 'manual', 'server-side'].includes(filterModeParam)) {
                FilterDataManager.state.filterMode = filterModeParam;
            }

            // Restore filters
            ['batch_rtx', 'batch_mtx', 'batch_atx', 'study_set', 'organism_common_name', 'library_prep_method',
                'ingest_status', 'alignment_status', 'postqc_status'].forEach(filterName => {
                    const paramValue = url.searchParams.get(filterName);
                    if (paramValue) {
                        const values = paramValue.split(',');
                        BrowserAJAX.state.activeFilters[filterName] = values;

                        // Update dropdown
                        const select = document.getElementById(filterName);
                        if (select) {
                            $(select).val(values);
                            $(select).trigger('change.select2');
                        }
                    }
                });

            const pageParam = url.searchParams.get('page');
            if (pageParam) {
                BrowserAJAX.state.currentPage = parseInt(pageParam) || 1;
            }

        } else {
            // Fallback to localStorage
            const saved = localStorage.getItem('browserFilterState');
            if (saved) {
                try {
                    const state = JSON.parse(saved);

                    // Old saved states may lack some keys; default those safely.
                    // Filter mode is restored from the 'filterMode' key below.
                    BrowserAJAX.state.searchTerm = state.searchTerm || '';
                    BrowserAJAX.state.activeFilters = state.activeFilters || {};
                    BrowserAJAX.state.currentPage = state.currentPage || 1;

                    // Update UI
                    const searchInput = document.getElementById('search-input');
                    if (searchInput) searchInput.value = BrowserAJAX.state.searchTerm;

                    // Update dropdowns
                    Object.entries(BrowserAJAX.state.activeFilters).forEach(([filterName, values]) => {
                        const select = document.getElementById(filterName);
                        if (select && Array.isArray(values)) {
                            $(select).val(values);
                            $(select).trigger('change.select2');
                        }
                    });

                } catch (error) {
                    console.error('[FilterStateManager] Error restoring state:', error);
                }
            }

            // Also check localStorage for just the filter mode preference
            const savedFilterMode = localStorage.getItem('filterMode');
            if (savedFilterMode && ['realtime', 'manual', 'server-side'].includes(savedFilterMode)) {
                FilterDataManager.state.filterMode = savedFilterMode;
            }
        }

    }
};

/**
 * FilterExtrasManager - Handles export/import, statistics, and additional features
 */
const FilterExtrasManager = {
    /**
     * Update filter statistics and analytics
     */
    updateFilterStatistics() {
        const stats = {
            total: FilterDataManager.state.allData.length,
            filtered: FilterDataManager.state.filteredData.length,
            hidden: FilterDataManager.state.allData.length - FilterDataManager.state.filteredData.length,
            percentage: ((FilterDataManager.state.filteredData.length / FilterDataManager.state.allData.length) * 100).toFixed(1)
        };

        // Update filter count badge in header
        const countBadge = document.querySelector('.card-header .badge');
        if (countBadge) {
            countBadge.textContent = `${stats.filtered} of ${stats.total} samples (${stats.percentage}%)`;
        }

        // Update pagination info
        const paginationInfo = document.querySelector('.pagination-info');
        if (paginationInfo && stats.filtered > 0) {
            const start = ((BrowserAJAX.state.currentPage - 1) * BrowserAJAX.state.perPage) + 1;
            const end = Math.min(BrowserAJAX.state.currentPage * BrowserAJAX.state.perPage, stats.filtered);
            paginationInfo.textContent = `Results ${start}-${end} of ${stats.filtered} filtered (${stats.total} total)`;
        }

    },

    /**
     * Initialize export/import functionality
     */
    initializeFilterExportImport() {
        // Add export/import buttons if they don't exist
        const actionsContainer = document.querySelector('.filter-actions');
        if (actionsContainer && !document.getElementById('exportFilters')) {
            const exportImportHtml = `
                <div class="filter-export-import ms-2">
                    <button type="button" id="exportFilters" class="btn btn-sm btn-outline-secondary" title="Export current display to CSV">
                        <i class="bi bi-download"></i>
                    </button>
                    <button type="button" id="importFilters" class="btn btn-sm btn-outline-secondary ms-1" title="Import filters">
                        <i class="bi bi-upload"></i>
                    </button>
                    <input type="file" id="filterImportFile" accept=".json" style="display: none;">
                </div>
            `;
            actionsContainer.insertAdjacentHTML('beforeend', exportImportHtml);
        }

        // Export functionality (keeping the existing detailed export logic)
        const exportBtn = document.getElementById('exportFilters');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => {

                // Get currently displayed data based on filter mode
                let currentData = [];

                if (FilterDataManager.state.filterMode === 'realtime' && FilterDataManager.state.filteredData) {
                    currentData = FilterDataManager.state.filteredData;
                } else if (FilterDataManager.state.filterMode === 'manual' && FilterDataManager.state.allData) {
                    currentData = FilterDataManager.state.allData;
                } else if (BrowserAJAX.state.samples && BrowserAJAX.state.samples.length > 0) {
                    currentData = BrowserAJAX.state.samples;
                } else {
                    // Final fallback: try to get data from the table
                    const tableRows = document.querySelectorAll('table tbody tr');
                    if (tableRows.length > 0) {
                        currentData = Array.from(tableRows).map(row => {
                            const cells = row.querySelectorAll('td');
                            const sample = {};
                            if (cells[1]) sample.fastq_name = cells[1].textContent.trim();
                            if (cells[2]) sample.study_set = cells[2].textContent.trim();
                            if (cells[3]) sample.load_name = cells[3].textContent.trim();
                            if (cells[4]) sample.library_prep_method = cells[4].textContent.trim();
                            return sample;
                        });
                    }
                }

                if (!currentData || currentData.length === 0) {
                    Utils.showMessage('No data to export', 'warning');
                    return;
                }

                // Continue with existing export logic...
                this.performCSVExport(currentData);
            });
        }

        // Import functionality
        const importBtn = document.getElementById('importFilters');
        const fileInput = document.getElementById('filterImportFile');

        if (importBtn && fileInput) {
            importBtn.addEventListener('click', () => fileInput.click());

            fileInput.addEventListener('change', (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const reader = new FileReader();
                reader.onload = (e) => {
                    try {
                        const importData = JSON.parse(e.target.result);

                        // Clear existing filters
                        FilterManager.clearAllFilters();

                        // Apply imported filters
                        BrowserAJAX.state.searchTerm = importData.searchTerm || '';
                        BrowserAJAX.state.activeFilters = importData.activeFilters || {};

                        // Update UI
                        const searchInput = document.getElementById('search-input');
                        if (searchInput) searchInput.value = BrowserAJAX.state.searchTerm;

                        Object.entries(BrowserAJAX.state.activeFilters).forEach(([filterName, values]) => {
                            const select = document.getElementById(filterName);
                            if (select) {
                                $(select).val(values).trigger('change');
                            }
                        });

                        // Apply filters
                        FilterManager.applyAllFilters();

                        Utils.showMessage('Filters imported successfully', 'success');

                    } catch (error) {
                        console.error('Import error:', error);
                        Utils.showMessage('Failed to import filters', 'error');
                    }
                };
                reader.readAsText(file);
            });
        }
    },

    /**
     * Perform CSV export with column settings
     */
    performCSVExport(currentData) {
        // Simplified CSV export logic - can be expanded as needed
        const csvHeaders = ['FASTQ Name', 'Study Set', 'Load Name', 'Library Prep Method', 'Ingest Status', 'Alignment Status', 'PostQC Status'];

        const csvRows = currentData.map(sample => {
            return [
                sample.fastq_name || '',
                sample.study_set || '',
                sample.load_name || '',
                sample.library_prep_method || '',
                sample.ingest_status || '',
                sample.alignment_status || '',
                sample.postqc_status || ''
            ].map(value => {
                const cleanValue = String(value).replace(/"/g, '""');
                return cleanValue.includes(',') || cleanValue.includes('\n') || cleanValue.includes('"')
                    ? `"${cleanValue}"` : cleanValue;
            });
        });

        const csvContent = [csvHeaders.join(','), ...csvRows.map(row => row.join(','))].join('\n');

        try {
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            const dateStr = new Date().toISOString().split('T')[0];
            const recordCount = currentData.length;
            a.download = `ocs-browser-data-${dateStr}-${recordCount}records.csv`;

            a.click();
            URL.revokeObjectURL(url);

            Utils.showMessage(`Exported ${recordCount} records to CSV`, 'success');

        } catch (error) {
            console.error('Export error:', error);
            Utils.showMessage('Error creating CSV file', 'error');
        }
    }
};

/**
 * Main FilterManager - Coordinates all filter sub-managers
 * 
 * CLEAN ARCHITECTURE:
 * - FilterManager: Clean coordinator that delegates to specialized managers
 * - No duplicate implementations - each method exists only once in the appropriate manager
 * - Single responsibility principle enforced
 * - Maintainable and readable code structure
 * 
 * DELEGATES TO:
 * - FilterDataManager: Data loading, caching, and options extraction
 * - FilterLogicManager: Core filtering logic and application  
 * - FilterUIManager: UI components, DOM manipulation, and visual updates
 * - FilterStateManager: State persistence, restoration, and URL management
 * - FilterExtrasManager: Export/import, statistics, and additional features
 */
const FilterManager = {
    // Reference to sub-managers for easy access
    data: FilterDataManager,
    logic: FilterLogicManager,
    ui: FilterUIManager,
    stateManager: FilterStateManager,
    extras: FilterExtrasManager,

    // Legacy state reference for backward compatibility
    get state() {
        return FilterDataManager.state;
    },

    /**
     * Initialize the filter system by coordinating all sub-managers
     */
    async init() {

        try {
            // Step 1: Load complete dataset (delegate to FilterDataManager)
            Utils.showMessage('Loading dataset for filtering...', 'info', 2000);
            await this.data.loadCompleteDataset();

            // Step 2: Initialize UI components (delegate to FilterUIManager)
            await this.ui.initializeSearchInput();
            await this.initializeAdvancedFilters(); // Keep this method for button handling
            await this.ui.initializeFilterDropdowns();

            // Step 3: Restore previous state (delegate to FilterStateManager)
            await this.stateManager.restoreFilterState();

            // Step 4: Initialize filter actions and extras
            await this.initializeFilterActions();
            this.extras.initializeFilterExportImport();

            // Step 5: Apply initial filters (delegate to FilterLogicManager)
            this.logic.applyAllFilters();

            // Step 6: Update UI display (delegate to FilterUIManager)
            setTimeout(() => {
                this.ui.updateActiveFiltersDisplay();
            }, 300);


            // Provide user feedback about filtering mode and dataset size
            const recordCount = this.data.state.allData.length;
            if (this.data.state.filterMode === 'realtime') {
                Utils.showMessage(`Real-time filtering ready with ${recordCount.toLocaleString()} records`, 'success', 3000);
            } else if (this.data.state.filterMode === 'server-side') {
                Utils.showMessage('Server-side filtering mode active', 'info', 3000);
            } else {
                Utils.showMessage(`Manual filtering mode active with ${recordCount.toLocaleString()} records`, 'info', 3000);
            }

        } catch (error) {
            console.error('[FilterManager] Initialization error:', error);

            // Check if we fell back to server-side filtering
            if (this.data.state.filterMode === 'server-side') {

                // Initialize remaining components for server-side mode
                await this.ui.initializeSearchInput();
                await this.initializeAdvancedFilters();
                await this.stateManager.restoreFilterState();
                await this.initializeFilterActions();

                // Load data using server-side filtering
                TableManager.loadData();

                Utils.showMessage('Initialized with server-side filtering', 'success', 3000);
            } else {
                Utils.showMessage('Filter system initialization failed', 'error');
            }
        }
    },

    /**
     * Legacy method delegates - maintain backward compatibility
     */
    // Delegate to FilterLogicManager
    applyAllFilters() {
        return this.logic.applyAllFilters();
    },

    handleFilterChange(selectElement) {
        return this.logic.handleFilterChange(selectElement);
    },

    clearAllFilters() {
        return this.logic.clearAllFilters();
    },

    // Delegate to FilterUIManager
    updateActiveFiltersDisplay() {
        return this.ui.updateActiveFiltersDisplay();
    },

    // Delegate to FilterStateManager
    updateFilterState() {
        return this.stateManager.updateFilterState();
    },

    async restoreFilterState() {
        return await this.stateManager.restoreFilterState();
    },

    // Delegate to FilterExtrasManager
    updateFilterStatistics() {
        return this.extras.updateFilterStatistics();
    },

    /**
     * Initialize advanced filters panel (kept for button handling)
     */
    async initializeAdvancedFilters() {
        // Note: Advanced Filters button toggle is handled by App.initializeButtonEventIsolation()
    },

    /**
     * STEP 5A: Initialize enhanced filter actions
     */
    initializeFilterActions() {
        // Filter mode toggle
        this.initializeFilterModeToggle();

        // Apply filters button (for manual mode)
        const applyButton = document.querySelector('.filter-actions button[type="submit"]');
        if (applyButton) {
            applyButton.addEventListener('click', (e) => {
                e.preventDefault();

                if (this.state.filterMode === 'manual') {
                    this.applyAllFilters();
                    Utils.showMessage('Filters applied', 'success');
                } else {
                    Utils.showMessage('Real-time mode is active', 'info');
                }
            });
        }

        // Enhanced reset filters
        const resetButton = document.getElementById('resetFilters');
        if (resetButton) {
            resetButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.clearAllFilters();
            });
        }

        // Add export/import functionality
        this.extras.initializeFilterExportImport();
    },











    /**
     * STEP 5B: Filter mode toggle (Real-time vs Manual)
     */
    initializeFilterModeToggle() {

        // Remove any existing toggle first
        const existingToggle = document.getElementById('filterModeToggle');
        if (existingToggle) {
            const existingContainer = existingToggle.closest('.filter-mode-toggle, .filter-mode-toggle-compact');
            if (existingContainer) {
                existingContainer.remove();
            }
        }

        // Find container - prioritize the top row with search and buttons
        let container = document.querySelector('.col-lg-5.text-end.mt-3.mt-lg-0');
        if (!container) {
            container = document.querySelector('.filter-actions');
        }
        if (!container) {
            container = document.querySelector('.card-body');
        }

        if (!container) {
            console.warn('[FilterManager] No suitable container found for filter mode toggle');
            return;
        }


        // Determine current mode info
        const recordCount = this.state.allData.length;
        const modeInfo = this.state.filterMode === 'realtime'
            ? `Real-time (${recordCount.toLocaleString()})`
            : this.state.filterMode === 'server-side'
                ? 'Server-side'
                : 'Manual';

        // Create compact toggle HTML
        const toggleHtml = `
            <div class="filter-mode-toggle-compact d-inline-flex align-items-center ms-2" 
                 role="button" 
                 tabindex="0"
                 aria-label="Toggle filter mode between Manual and Real-time"
                 title="Click to toggle between Manual and Real-time filter modes">
                <span class="filter-mode-label-compact me-2">Filter:</span>
                <div class="toggle-switch toggle-switch-sm">
                    <input type="checkbox" id="filterModeToggle" 
                           ${this.state.filterMode === 'realtime' ? 'checked' : ''} 
                           ${this.state.filterMode === 'server-side' ? 'disabled' : ''}
                           aria-label="Filter mode toggle">
                    <span class="toggle-slider"></span>
                </div>
                <span class="filter-mode-status ms-2">
                    ${modeInfo}
                </span>
            </div>
        `;

        // Insert the HTML at the end of the container
        container.insertAdjacentHTML('beforeend', toggleHtml);

        // Add a small delay to ensure DOM is updated, then attach event listener
        setTimeout(() => {
            this.attachFilterModeToggleListener();
        }, 100);
    },

    /**
     * Attach event listener to filter mode toggle
     */
    attachFilterModeToggleListener() {
        const toggle = document.getElementById('filterModeToggle');
        const toggleContainer = document.querySelector('.filter-mode-toggle-compact');

        if (!toggle) {
            console.error('[FilterManager] Filter mode toggle element not found after creation');
            return;
        }

        if (!toggleContainer) {
            console.error('[FilterManager] Filter mode toggle container not found after creation');
            return;
        }

        if (toggle.disabled) {
            return;
        }


        // Remove any existing listeners to prevent duplicates
        const newToggle = toggle.cloneNode(true);
        toggle.parentNode.replaceChild(newToggle, toggle);

        // Get the updated toggle and container references
        const updatedToggle = document.getElementById('filterModeToggle');
        const updatedContainer = document.querySelector('.filter-mode-toggle-compact');

        // Handle the toggle action
        const handleToggle = (e) => {
            // Prevent event bubbling if clicked on the checkbox itself
            if (e.target === updatedToggle) {
                // Let the checkbox handle its own change event
                return;
            }

            // If clicked elsewhere in the container, prevent default and toggle manually
            e.preventDefault();
            e.stopPropagation();

            // Toggle the checkbox state
            updatedToggle.checked = !updatedToggle.checked;

            // Trigger the change event manually
            const changeEvent = new Event('change', { bubbles: true });
            updatedToggle.dispatchEvent(changeEvent);
        };

        // Handle keyboard navigation
        const handleKeyDown = (e) => {
            // Only handle Enter and Space keys
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                e.stopPropagation();

                // Toggle the checkbox state
                updatedToggle.checked = !updatedToggle.checked;

                // Trigger the change event manually
                const changeEvent = new Event('change', { bubbles: true });
                updatedToggle.dispatchEvent(changeEvent);
            }
        };

        // Attach click event listener to the entire container
        updatedContainer.addEventListener('click', handleToggle);

        // Attach keyboard event listener to the entire container
        updatedContainer.addEventListener('keydown', handleKeyDown);

        // Attach the change event listener to the checkbox
        updatedToggle.addEventListener('change', (e) => {

            const oldMode = this.state.filterMode;
            this.state.filterMode = e.target.checked ? 'realtime' : 'manual';


            // Update the label text
            const label = document.querySelector('.filter-mode-status');
            if (label) {
                const recordCount = this.state.allData.length;
                const modeInfo = this.state.filterMode === 'realtime'
                    ? `Real-time (${recordCount.toLocaleString()})`
                    : 'Manual';
                label.textContent = modeInfo;
            } else {
                console.warn('[FilterManager] Could not find .filter-mode-status label to update');
            }

            // Switching to real-time applies immediately; manual just waits for Apply.
            if (this.state.filterMode === 'realtime' && oldMode !== 'realtime') {
                this.applyAllFilters();
            }

            // Save the preference (locally + server for cross-device sync)
            localStorage.setItem('filterMode', this.state.filterMode);
            PreferenceSync.save();
            Utils.showMessage(`Filter mode set to ${this.state.filterMode}`, 'info');

        });

    },







    /**
     * Update the filter mode toggle to reflect current state
     */
    updateFilterModeToggleState() {
        const toggle = document.getElementById('filterModeToggle');
        const label = document.querySelector('.filter-mode-status');

        if (toggle) {
            toggle.checked = this.state.filterMode === 'realtime';
            toggle.disabled = this.state.filterMode === 'server-side';
        }

        if (label) {
            const recordCount = this.state.allData.length;
            const modeInfo = this.state.filterMode === 'realtime'
                ? `Real-time (${recordCount.toLocaleString()})`
                : this.state.filterMode === 'server-side'
                    ? 'Server-side'
                    : 'Manual';
            label.textContent = modeInfo;
        }
    },








};

/**
 * Simplified Pagination Manager
 */
const PaginationManager = {
    init() {
        this.setupEventHandlers();
    },

    setupEventHandlers() {
        // Unified event delegation for all pagination actions
        document.addEventListener('click', (e) => {
            const button = e.target.closest('[data-pagination-action]');
            if (!button || button.disabled) return;

            e.preventDefault();
            const action = button.dataset.paginationAction;

            if (action === 'per-page') {
                this.handlePerPageChange(button);
            } else {
                this.handlePaginationAction(action);
            }
        });

        // Go to page form
        const gotoForm = document.getElementById('gotoPageForm');
        if (gotoForm) {
            gotoForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleGotoPage();
            });
        }
    },

    handlePaginationAction(action) {
        const actionMap = {
            'first': 1,
            'prev': Math.max(1, BrowserAJAX.state.currentPage - 1),
            'next': Math.min(BrowserAJAX.state.totalPages, BrowserAJAX.state.currentPage + 1),
            'last': BrowserAJAX.state.totalPages
        };

        const targetPage = actionMap[action];
        if (targetPage && targetPage !== BrowserAJAX.state.currentPage) {
            BrowserAJAX.state.currentPage = targetPage;
            TableManager.loadData();
        }
    },

    handlePerPageChange(item) {
        const newPerPage = parseInt(item.dataset.perPage);
        if (newPerPage && newPerPage !== BrowserAJAX.state.perPage) {
            BrowserAJAX.state.perPage = newPerPage;
            BrowserAJAX.state.currentPage = 1; // Reset to first page
            TableManager.loadData();
        }
    },

    handleGotoPage() {
        const input = document.getElementById('gotoPage');
        if (!input) return;

        const targetPage = parseInt(input.value);
        if (targetPage >= 1 && targetPage <= BrowserAJAX.state.totalPages && targetPage !== BrowserAJAX.state.currentPage) {
            BrowserAJAX.state.currentPage = targetPage;
            TableManager.loadData();
        }
    },

    /**
     * Update all pagination controls in one efficient call
     */
    updateControls(pagination) {
        // Update page indicators
        const currentPageSpan = document.querySelector('.current-page');
        const totalPagesSpan = document.querySelector('.total-pages');
        if (currentPageSpan) currentPageSpan.textContent = pagination.current_page;
        if (totalPagesSpan) totalPagesSpan.textContent = pagination.total_pages;

        // Update navigation buttons state
        const isFirstPage = pagination.current_page === 1;
        const isLastPage = pagination.current_page === pagination.total_pages;

        ['first', 'prev'].forEach(action => {
            const btn = document.querySelector(`[data-pagination-action="${action}"]`);
            if (btn) {
                btn.disabled = isFirstPage;
                btn.classList.toggle('disabled', isFirstPage);
            }
        });

        ['next', 'last'].forEach(action => {
            const btn = document.querySelector(`[data-pagination-action="${action}"]`);
            if (btn) {
                btn.disabled = isLastPage;
                btn.classList.toggle('disabled', isLastPage);
            }
        });

        // Update per-page dropdown
        const dropdown = document.getElementById('rowsPerPageDropdown');
        if (dropdown) {
            dropdown.textContent = BrowserAJAX.state.perPage;
            dropdown.dataset.currentPerPage = BrowserAJAX.state.perPage;
        }

        // Update go-to-page input
        const input = document.getElementById('gotoPage');
        if (input) {
            input.value = pagination.current_page;
            input.max = pagination.total_pages;
        }

        // Update pagination info
        const info = document.querySelector('.pagination-info');
        if (info) {
            const start = ((pagination.current_page - 1) * pagination.per_page) + 1;
            const end = Math.min(pagination.current_page * pagination.per_page, pagination.total_items);
            info.textContent = `Results ${start}-${end} of ${pagination.total_items}`;
        }

        // Update data attributes
        const footer = document.querySelector('.card-footer[data-pagination-current-page]');
        if (footer) {
            footer.dataset.paginationCurrentPage = pagination.current_page;
            footer.dataset.paginationTotalPages = pagination.total_pages;
            footer.dataset.paginationPerPage = pagination.per_page;
            footer.dataset.paginationTotalItems = pagination.total_items;
        }
    },


};

/**
 * Simplified Selection Manager
 */
const SelectionManager = {
    init() {
        this.initializeSelectionPanel();
        this.initializeCheckboxes();
        this.initializeEventDelegation();
    },

    // Unified event delegation for all selection-related interactions
    initializeEventDelegation() {
        document.addEventListener('click', (e) => {
            // Handle FID copy
            const fidCell = e.target.closest('.fid-column');
            if (fidCell) {
                this.handleFidCopy(fidCell);
                return;
            }
        });

        // Scroll detection for sticky column
        const tableResponsive = document.querySelector('.table-responsive');
        if (tableResponsive) {
            const handleScroll = () => {
                tableResponsive.classList.toggle('is-scrolled', tableResponsive.scrollLeft > 0);
            };

            tableResponsive.addEventListener('scroll', handleScroll);
            window.addEventListener('resize', handleScroll);
        }
    },

    async handleFidCopy(fidCell) {
        const fidText = fidCell.textContent.trim();

        if (!fidText || fidText === '—' || fidText === '-') {
            Utils.showMessage('No FID to copy', 'warning', 2000);
            return;
        }

        try {
            // Modern clipboard API with fallback
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(fidText);
            } else {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                Object.assign(textArea.style, {
                    position: 'fixed',
                    left: '-999999px',
                    top: '-999999px'
                });
                textArea.value = fidText;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                textArea.remove();
            }

            // Visual feedback and success message
            fidCell.classList.add('copied');
            Utils.showMessage(`Copied FID: ${fidText}`, 'success', 2000);
            setTimeout(() => fidCell.classList.remove('copied'), 1000);

        } catch (error) {
            Utils.handleError(error, 'FID copy failed');
        }
    },

    /**
     * Initialize the selection panel with enhanced features
     */
    initializeSelectionPanel() {
        const clearBtn = document.getElementById('clear-selection-btn');
        const sendBtn = document.getElementById('send-to-pipeline-btn');
        const closeBtn = document.getElementById('close-selection-panel');

        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearSelection());
        }

        if (sendBtn) {
            sendBtn.addEventListener('click', () => this.sendToPipeline());
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.clearSelection());
        }

        // Add keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Only trigger if selection panel is visible
            const panel = document.getElementById('selection-panel');
            if (!panel || panel.style.display === 'none') return;

            // Escape key to clear selection
            if (e.key === 'Escape') {
                e.preventDefault();
                this.clearSelection();
            }

            // Enter key to send to pipeline (when focused on panel or buttons)
            if (e.key === 'Enter' && (
                e.target.closest('#selection-panel') ||
                document.activeElement === sendBtn
            )) {
                e.preventDefault();
                this.sendToPipeline();
            }

            // Ctrl/Cmd + Shift + P to send to pipeline
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'P') {
                e.preventDefault();
                if (BrowserAJAX.state.selectedSamples.length > 0) {
                    this.sendToPipeline();
                    Utils.showMessage('Keyboard shortcut: Sending to pipeline (Ctrl+Shift+P)', 'info', 2000);
                }
            }

            // Ctrl/Cmd + Shift + C to clear selection
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
                e.preventDefault();
                if (BrowserAJAX.state.selectedSamples.length > 0) {
                    this.clearSelection();
                    Utils.showMessage('Keyboard shortcut: Selection cleared (Ctrl+Shift+C)', 'info', 2000);
                }
            }
        });

        // Add accessibility attributes
        if (sendBtn) {
            sendBtn.setAttribute('aria-label', 'Send selected samples to pipeline for processing');
            sendBtn.setAttribute('title', 'Send to Pipeline (Ctrl+Shift+P)');
        }

        if (clearBtn) {
            clearBtn.setAttribute('aria-label', 'Clear all selected samples');
            clearBtn.setAttribute('title', 'Clear Selection (Ctrl+Shift+C or Escape)');
        }

        if (closeBtn) {
            closeBtn.setAttribute('aria-label', 'Close selection panel');
            closeBtn.setAttribute('title', 'Close Panel (Escape)');
        }
    },

    /**
     * Initialize checkboxes (called after table updates)
     */
    initializeCheckboxes() {
        // Select all checkbox
        const selectAllCheckbox = document.getElementById('select-all-samples');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', (e) => {
                this.handleSelectAll(e.target.checked);
            });
        }

        // Individual sample checkboxes - use event delegation for dynamic content
        document.querySelectorAll('.sample-select:not(#select-all-samples)').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.handleSampleSelection(e.target);
            });
        });

        this.updateSelectionPanel();
    },

    /**
     * Handle select all checkbox
     */
    handleSelectAll(checked) {
        document.querySelectorAll('.sample-select:not(#select-all-samples)').forEach(checkbox => {
            checkbox.checked = checked;
            this.handleSampleSelection(checkbox, false); // Don't update panel for each
        });
        this.updateSelectionPanel();
    },

    /**
     * Handle individual sample selection with enhanced feedback
     */
    handleSampleSelection(checkbox, updatePanel = true) {
        const row = checkbox.closest('tr');
        if (!row) return;

        const sampleData = this.extractSampleData(row);
        if (!sampleData) return;

        const wasEmpty = BrowserAJAX.state.selectedSamples.length === 0;

        if (checkbox.checked) {
            // Add to selection if not already there
            if (!BrowserAJAX.state.selectedSamples.some(s => s.fastq_name === sampleData.fastq_name)) {
                BrowserAJAX.state.selectedSamples.push(sampleData);

                // Add visual feedback for selection
                row.classList.add('sample-selected');
                setTimeout(() => row.classList.remove('sample-selected'), 300);
            }
        } else {
            // Remove from selection
            BrowserAJAX.state.selectedSamples = BrowserAJAX.state.selectedSamples.filter(
                s => s.fastq_name !== sampleData.fastq_name
            );
        }

        if (updatePanel) {
            this.updateSelectionPanel();

            // Animate the selection icon when first sample is selected
            if (wasEmpty && BrowserAJAX.state.selectedSamples.length > 0) {
                const selectionIcon = document.querySelector('.selection-icon');
                if (selectionIcon) {
                    selectionIcon.style.transform = 'scale(1.2)';
                    setTimeout(() => {
                        selectionIcon.style.transform = 'scale(1)';
                    }, 200);
                }
            }
        }
    },

    /**
     * Extract sample data from table row
     */
    extractSampleData(row) {
        return {
            fastq_name: row.dataset.fastqName || '',
            study_set: row.dataset.studySet || '',
            load_name: row.dataset.loadName || '',
            batch_name_from_vendor: row.dataset.batchNameFromVendor || '',
            organism_common_name: row.dataset.organismCommonName || '',
            library_prep_method: row.dataset.libraryPrepMethod || '',
            ingest_status: row.dataset.ingestStatus || 'Not Completed',
            alignment_status: row.dataset.alignmentStatus || 'Not Completed',
            postqc_status: row.dataset.postqcStatus || 'Not Completed'
        };
    },

    /**
     * Update selection panel visibility and count
     */
    updateSelectionPanel() {
        const panel = document.getElementById('selection-panel');
        const countSpan = document.getElementById('selected-count');

        if (!panel) return;

        const count = BrowserAJAX.state.selectedSamples.length;

        if (count > 0) {
            panel.style.display = 'block';
            if (countSpan) {
                countSpan.textContent = count;

                // Update the subtitle text based on count
                const subtitle = panel.querySelector('.selection-subtitle');
                if (subtitle) {
                    if (count === 1) {
                        subtitle.textContent = 'Ready for processing';
                    } else {
                        subtitle.textContent = 'Ready for processing';
                    }
                }
            }
        } else {
            panel.style.display = 'none';
        }

        // Update select all checkbox state
        this.updateSelectAllCheckbox();
    },

    /**
     * Update select all checkbox state
     */
    updateSelectAllCheckbox() {
        const selectAllCheckbox = document.getElementById('select-all-samples');
        if (!selectAllCheckbox) return;

        const currentPageCheckboxes = document.querySelectorAll('.sample-select:not(#select-all-samples)');
        const checkedCount = Array.from(currentPageCheckboxes).filter(cb => cb.checked).length;

        selectAllCheckbox.checked = currentPageCheckboxes.length > 0 && checkedCount === currentPageCheckboxes.length;
        selectAllCheckbox.indeterminate = checkedCount > 0 && checkedCount < currentPageCheckboxes.length;
    },

    /**
     * Clear all selections with enhanced feedback
     */
    clearSelection() {
        BrowserAJAX.state.selectedSamples = [];

        // Uncheck all checkboxes
        document.querySelectorAll('.sample-select').forEach(checkbox => {
            checkbox.checked = false;
        });

        // Hide progress indicator if showing
        const progressContainer = document.getElementById('selection-progress');
        if (progressContainer) {
            progressContainer.style.display = 'none';
        }

        // Re-enable buttons if they were disabled
        const sendButton = document.getElementById('send-to-pipeline-btn');
        const clearButton = document.getElementById('clear-selection-btn');

        if (sendButton) {
            sendButton.disabled = false;
            sendButton.style.opacity = '1';
            sendButton.style.pointerEvents = 'auto';
        }
        if (clearButton) {
            clearButton.disabled = false;
            clearButton.style.opacity = '1';
            clearButton.style.pointerEvents = 'auto';
        }

        this.updateSelectionPanel();
        Utils.showMessage('Selection cleared', 'success');
    },

    /**
     * Send selected samples to pipeline with enhanced progress feedback
     */
    async sendToPipeline() {
        if (BrowserAJAX.state.selectedSamples.length === 0) {
            Utils.showMessage('No samples selected', 'error');
            return;
        }

        const panel = document.getElementById('selection-panel');
        const progressContainer = document.getElementById('selection-progress');
        const progressText = progressContainer?.querySelector('.progress-text');
        const sendButton = document.getElementById('send-to-pipeline-btn');
        const clearButton = document.getElementById('clear-selection-btn');

        try {
            // Show progress indicator
            if (progressContainer) {
                progressContainer.style.display = 'block';
            }

            // Disable buttons during processing
            if (sendButton) {
                sendButton.disabled = true;
                sendButton.style.opacity = '0.6';
                sendButton.style.pointerEvents = 'none';
            }
            if (clearButton) {
                clearButton.disabled = true;
                clearButton.style.opacity = '0.6';
                clearButton.style.pointerEvents = 'none';
            }

            // Update progress text
            if (progressText) {
                progressText.textContent = `Preparing ${BrowserAJAX.state.selectedSamples.length} samples for pipeline...`;
            }

            // Simulate processing time for better UX
            await new Promise(resolve => setTimeout(resolve, 1000));


            // MERGE with existing data instead of replacing
            let mergedSamples = [];

            // Load existing samples from localStorage
            const existingData = localStorage.getItem(PRODUCTION_CONFIG.storageKey);
            if (existingData) {
                try {
                    const existingSamples = JSON.parse(existingData);
                    if (Array.isArray(existingSamples)) {
                        mergedSamples = [...existingSamples];
                    }
                } catch (parseError) {
                    console.error('[Browser] Error parsing existing data:', parseError);
                }
            } else {
            }

            // Create a set of existing fastq names to avoid duplicates
            const existingFastqNames = new Set(mergedSamples.map(sample => {
                return sample.fastq_name || sample.fastq || sample.fastq_id;
            }));


            // Add new samples, avoiding duplicates
            let addedCount = 0;
            let skippedCount = 0;

            BrowserAJAX.state.selectedSamples.forEach(newSample => {
                const fastqName = newSample.fastq_name || newSample.fastq || newSample.fastq_id;

                if (fastqName && !existingFastqNames.has(fastqName)) {
                    // Add timestamp to track when this sample was added
                    const sampleWithTimestamp = {
                        ...newSample,
                        timestamp: Date.now(),
                        source: 'browser'
                    };
                    mergedSamples.push(sampleWithTimestamp);
                    existingFastqNames.add(fastqName);
                    addedCount++;
                } else {
                    skippedCount++;
                    if (fastqName) {
                    } else {
                        console.warn('[Browser] Skipping sample with no fastq name:', newSample);
                    }
                }
            });


            // Store the merged samples in localStorage
            localStorage.setItem(PRODUCTION_CONFIG.storageKey, JSON.stringify(mergedSamples));

            // Update progress text
            if (progressText) {
                progressText.textContent = `Successfully merged ${addedCount} new samples! Redirecting to pipeline...`;
            }

            // Show success message
            Utils.showMessage(`${addedCount} new samples added to Pipeline Checkout (${skippedCount} duplicates skipped)`, 'success', 3000);

            // Wait a bit more for user to see the success state
            await new Promise(resolve => setTimeout(resolve, 1500));


            // Redirect to pipeline using the correct URL
            window.location.href = PRODUCTION_CONFIG.pipelineUrl;

        } catch (error) {
            console.error('[SelectionManager] Error sending to pipeline:', error);
            Utils.showMessage('Error sending samples to pipeline. Please try again.', 'error');

            // Hide progress and re-enable buttons on error
            if (progressContainer) {
                progressContainer.style.display = 'none';
            }

            if (sendButton) {
                sendButton.disabled = false;
                sendButton.style.opacity = '1';
                sendButton.style.pointerEvents = 'auto';
            }
            if (clearButton) {
                clearButton.disabled = false;
                clearButton.style.opacity = '1';
                clearButton.style.pointerEvents = 'auto';
            }
        }
    }
};

/**
 * Column Manager - Handles column visibility
 */
/**
 * Read a Django `{{ value|json_script:"id" }}` payload, or null if absent.
 */
function readJSONScript(id) {
    // The server always embeds these (see ocs/columns.py + the view). Return an
    // empty object on the should-never-happen missing/invalid case so callers
    // don't each need their own fallback — and warn loudly if it does happen.
    const el = document.getElementById(id);
    if (!el) {
        console.warn(`[ColumnManager] Expected server-embedded #${id} is missing`);
        return {};
    }
    try {
        return JSON.parse(el.textContent);
    } catch (e) {
        console.warn(`[ColumnManager] Could not parse #${id}`, e);
        return {};
    }
}

const ColumnManager = {
    // Snapshot of column states saved before "Show All", used to restore them.
    previousColumnStates: null,

    // Default column visibility, provided by the server (ocs/columns.py) via a
    // json_script tag. Used for "Reset" and the "Show All" restore fallback.
    defaults: {},

    /**
     * Initialize column management.
     */
    init() {
        this.defaults = readJSONScript('ocs-column-defaults');
        // Columns are server-driven now; drop any legacy per-browser cache so a
        // stale value can never override the server-rendered state.
        localStorage.removeItem('columnSettings');
        this.loadColumnSettings();
        this.setupEventHandlers();
    },

    loadColumnSettings() {
        // The server renders this user's effective settings (defaults merged
        // with their saved prefs) and embeds them as JSON, so the initial paint
        // already matches — no flash, and no cross-user localStorage leakage.
        // The server is the source of truth; mirror it into state and keep the
        // toggles + columns in sync with it.
        // The server renders this user's effective settings (defaults merged
        // with their saved prefs) and embeds them, so this is the single,
        // authoritative initial state — no fallback chain needed.
        BrowserAJAX.state.columnSettings = readJSONScript('ocs-column-settings');
        this.syncCheckboxes();
        this.applyColumnSettings();
    },

    saveColumnSettings() {
        // Persisted per-user on the server (no localStorage cache for columns).
        PreferenceSync.save();
    },

    /**
     * Set up column toggle event handlers
     */
    setupEventHandlers() {
        // Individual column toggles
        document.querySelectorAll('.column-toggle-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.handleColumnToggle(e.target);
            });
        });

        // Toggle all columns - rebuilt functionality
        const toggleAllCheckbox = document.getElementById('toggleAllColumns');
        if (toggleAllCheckbox) {
            toggleAllCheckbox.addEventListener('change', (e) => {
                this.handleShowAllToggle(e.target.checked);
            });
        }

        // Reset to defaults
        const resetButton = document.getElementById('resetColumnDefaults');
        if (resetButton) {
            resetButton.addEventListener('click', () => {
                this.resetToDefaults();
            });
        }
    },

    /**
     * Handle individual column toggle
     */
    handleColumnToggle(checkbox) {
        const columnName = checkbox.dataset.column;
        if (columnName) {
            BrowserAJAX.state.columnSettings[columnName] = checkbox.checked;
            this.applyColumnSettings();
            this.saveColumnSettings();

            // Update show all checkbox state after individual column change
            this.updateShowAllCheckboxState();
        }
    },

    /**
     * Handle show all toggle - rebuilt from scratch
     */
    handleShowAllToggle(showAll) {
        if (showAll) {
            // Remember the current visibility (unless everything is already shown)
            // so unchecking "Show All" can restore it.
            const allVisible = Object.values(BrowserAJAX.state.columnSettings).every(v => v);
            if (!allVisible) {
                this.previousColumnStates = { ...BrowserAJAX.state.columnSettings };
            }
            Object.keys(BrowserAJAX.state.columnSettings).forEach(columnName => {
                BrowserAJAX.state.columnSettings[columnName] = true;
            });
            Utils.showMessage('All columns shown', 'success');
        } else {
            // Restore the saved snapshot, or fall back to defaults.
            BrowserAJAX.state.columnSettings = this.previousColumnStates
                ? { ...this.previousColumnStates }
                : { ...this.defaults };
            this.previousColumnStates = null;
            Utils.showMessage('Previous column visibility restored', 'success');
        }

        this.syncCheckboxes();
        this.applyColumnSettings();
        this.saveColumnSettings();
    },

    /**
     * Sync the individual column checkboxes to the current column settings.
     */
    syncCheckboxes() {
        document.querySelectorAll('.column-toggle-checkbox').forEach(checkbox => {
            const columnName = checkbox.dataset.column;
            if (columnName && columnName in BrowserAJAX.state.columnSettings) {
                checkbox.checked = BrowserAJAX.state.columnSettings[columnName];
            }
        });
    },

    /**
     * Update show all checkbox state based on individual column states
     */
    updateShowAllCheckboxState() {
        const toggleAllCheckbox = document.getElementById('toggleAllColumns');
        if (!toggleAllCheckbox) return;

        const columnValues = Object.values(BrowserAJAX.state.columnSettings);
        const totalColumns = columnValues.length;
        const visibleColumns = columnValues.filter(visible => visible).length;


        if (visibleColumns === totalColumns) {
            // All columns visible
            toggleAllCheckbox.checked = true;
            toggleAllCheckbox.indeterminate = false;
        } else if (visibleColumns === 0) {
            // No columns visible
            toggleAllCheckbox.checked = false;
            toggleAllCheckbox.indeterminate = false;
        } else {
            // Some columns visible (indeterminate state)
            toggleAllCheckbox.checked = false;
            toggleAllCheckbox.indeterminate = true;
        }
    },

    /**
     * Reset to default column settings
     */
    resetToDefaults() {
        this.previousColumnStates = null;
        BrowserAJAX.state.columnSettings = { ...this.defaults };

        this.syncCheckboxes();
        this.applyColumnSettings();  // also refreshes the "Show All" checkbox state
        this.saveColumnSettings();
        Utils.showMessage('Column settings reset to defaults', 'success');
    },

    /**
     * Apply column settings to table
     */
    applyColumnSettings() {
        Object.entries(BrowserAJAX.state.columnSettings).forEach(([columnName, visible]) => {
            this.toggleColumn(columnName, visible);
        });

        // Update show all checkbox state after applying settings
        this.updateShowAllCheckboxState();
    },

    /**
     * Toggle column visibility
     */
    toggleColumn(columnName, visible) {
        // Toggle header
        const headerCell = document.querySelector(`.column-${columnName}`);
        if (headerCell) {
            headerCell.style.display = visible ? '' : 'none';
        }

        // Toggle data cells
        document.querySelectorAll(`.field-${columnName}`).forEach(cell => {
            cell.style.display = visible ? '' : 'none';
        });
    }
};

/**
 * Simplified Sorting Manager
 */
const SortingManager = {
    init() {
        this.setupEventHandlers();
        this.restoreSortState();
    },

    setupEventHandlers() {
        // Event delegation for sortable columns and reset button
        document.addEventListener('click', (e) => {
            // Handle sortable columns
            const sortableHeader = e.target.closest('th.sortable');
            if (sortableHeader && !e.target.closest('.sort-indicator')) {
                this.handleSort(sortableHeader);
                return;
            }

            // Handle reset button
            const resetButton = e.target.closest('#resetSort');
            if (resetButton) {
                this.clearSort();
                FilterManager.applyAllFilters();
                Utils.showMessage('Sorting cleared', 'success');
                return;
            }
        });

        // Keyboard shortcut for reset sort
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                if (BrowserAJAX.state.sortField) {
                    this.clearSort();
                    FilterManager.applyAllFilters();
                    Utils.showMessage('Sorting cleared (Ctrl+Shift+S)', 'success');
                }
            }
        });
    },

    /**
     * Handle column sort click
     */
    handleSort(headerElement) {
        const field = headerElement.dataset.sortField;
        if (!field) return;

        // Add sorting animation class
        headerElement.classList.add('sorting');

        // Determine new sort direction - now with three states
        let newDirection = 'asc';
        if (BrowserAJAX.state.sortField === field) {
            if (BrowserAJAX.state.sortDirection === 'asc') {
                newDirection = 'desc';
            } else if (BrowserAJAX.state.sortDirection === 'desc') {
                // Third click clears sort
                this.clearSort();
                FilterManager.applyAllFilters();
                Utils.showMessage('Sorting cleared', 'success');

                // Remove animation class
                setTimeout(() => {
                    headerElement.classList.remove('sorting');
                }, 300);
                return;
            }
        }

        // Update state
        BrowserAJAX.state.sortField = field;
        BrowserAJAX.state.sortDirection = newDirection;

        // Save sort state
        this.saveSortState();

        // Update UI
        this.updateSortIndicators();

        // Apply sort based on filter mode
        if (FilterManager.state.filterMode === 'realtime' || FilterManager.state.filterMode === 'manual') {
            // Client-side sorting
            FilterManager.applyAllFilters();
        } else {
            // Server-side sorting - reload data with sort params
            BrowserAJAX.state.currentPage = 1; // Reset to first page
            TableManager.loadData();
        }

        // Remove animation class after animation completes
        setTimeout(() => {
            headerElement.classList.remove('sorting');
        }, 300);
    },



    /**
     * Get sort value from sample object
     */
    getSortValue(sample, field) {
        let value = sample[field];

        // Handle special cases
        if (field.endsWith('_time') && value) {
            // Convert time strings to Date objects for proper sorting
            const dateValue = new Date(value);
            // Return timestamp if valid date, otherwise return 0
            return isNaN(dateValue.getTime()) ? 0 : dateValue.getTime();
        }

        // Handle status fields - extract text content for sorting
        if (field.endsWith('_status') && value) {
            // If it's already a string, use it; otherwise extract from HTML if needed
            if (typeof value === 'string') {
                return value.toLowerCase();
            }
        }

        // Handle numeric fields
        if (field === 'cell_capture' || field === 'sample_id' || field.endsWith('_id')) {
            const numValue = parseInt(value);
            return isNaN(numValue) ? 0 : numValue;
        }

        // Handle empty/null/undefined values
        if (value === null || value === undefined || value === '') {
            return '';
        }

        // Return the value as-is for other fields, converting to string
        return String(value);
    },

    /**
     * Update sort indicators on all columns
     */
    updateSortIndicators() {
        // Remove all active sort classes
        document.querySelectorAll('th.sortable').forEach(th => {
            th.classList.remove('sort-asc', 'sort-desc');
        });

        // Add active sort class to current column
        if (BrowserAJAX.state.sortField) {
            const activeHeader = document.querySelector(`th[data-sort-field="${BrowserAJAX.state.sortField}"]`);
            if (activeHeader) {
                activeHeader.classList.add(`sort-${BrowserAJAX.state.sortDirection}`);
            }
        }

        // Show/hide reset sort button
        const resetButton = document.getElementById('resetSort');
        if (resetButton) {
            resetButton.style.display = BrowserAJAX.state.sortField ? 'inline-flex' : 'none';
        }
    },

    saveSortState() {
        const sortState = {
            field: BrowserAJAX.state.sortField,
            direction: BrowserAJAX.state.sortDirection
        };
        StateManager.save('tableSortState', sortState);
    },

    restoreSortState() {
        const defaultState = { field: null, direction: 'asc' };
        const sortState = StateManager.load('tableSortState', defaultState);

        BrowserAJAX.state.sortField = sortState.field;
        BrowserAJAX.state.sortDirection = sortState.direction;
        this.updateSortIndicators();
    },

    clearSort() {
        BrowserAJAX.state.sortField = null;
        BrowserAJAX.state.sortDirection = 'asc';
        StateManager.remove('tableSortState');
        this.updateSortIndicators();
    },

    applySortToFilteredData() {
        if (!FilterManager.state.filteredData || FilterManager.state.filteredData.length === 0) {
            return;
        }


        try {
            FilterManager.state.filteredData.sort((a, b) => {
                const aValue = this.getSortValue(a, BrowserAJAX.state.sortField);
                const bValue = this.getSortValue(b, BrowserAJAX.state.sortField);

                // Handle null/undefined/empty values
                if (!aValue && aValue !== 0) return 1;
                if (!bValue && bValue !== 0) return -1;

                // Compare values with unified logic
                let comparison = 0;
                if (typeof aValue === 'number' && typeof bValue === 'number') {
                    comparison = aValue - bValue;
                } else {
                    // String comparison (covers most cases)
                    comparison = String(aValue).toLowerCase().localeCompare(String(bValue).toLowerCase());
                }

                return BrowserAJAX.state.sortDirection === 'asc' ? comparison : -comparison;
            });
        } catch (error) {
            Utils.handleError(error, 'Sorting data');
        }
    }
};



/**
 * Simplified Main Application
 */
const App = {
    async init() {
        Utils.logDebug('Initializing Browser AJAX application');
        const startTime = PRODUCTION_CONFIG.debug ? performance.now() : null;

        try {
            // Pull the user's saved view from the server first; it wins on login
            // and seeds the localStorage keys the managers read just below.
            await PreferenceSync.load();

            // Initialize all managers in order
            const managers = [
                TableManager, FilterManager, PaginationManager,
                SelectionManager, ColumnManager, SortingManager
            ];

            managers.forEach(manager => manager.init());

            // Initialize button event isolation
            this.initializeButtonEventIsolation();

            // Load initial data if needed
            if (FilterManager.state.filterMode === 'server-side') {
                await TableManager.loadData();
            }

            Utils.logDebug('Browser AJAX application initialized successfully');

        } catch (error) {
            Utils.handleError(error, 'Application initialization');
        } finally {
            if (PRODUCTION_CONFIG.debug && startTime) {
                const duration = performance.now() - startTime;
                Utils.logDebug(`Application initialization completed in ${duration.toFixed(2)}ms`);
            }
        }
    },

    /**
     * Initialize button event isolation to prevent click interference
     */
    initializeButtonEventIsolation() {

        // Advanced Filters button - ensure proper event handling
        const advancedFiltersBtn = document.getElementById('toggleAdvancedFilters');
        if (advancedFiltersBtn) {
            // Remove any existing event listeners to prevent duplicates
            const newBtn = advancedFiltersBtn.cloneNode(true);
            advancedFiltersBtn.parentNode.replaceChild(newBtn, advancedFiltersBtn);

            // Add proper event handling with isolation
            newBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();

                // Toggle the advanced filters panel
                const filtersPanel = document.getElementById('advancedFilters');
                if (filtersPanel) {
                    const isHidden = filtersPanel.style.display === 'none' || !filtersPanel.style.display;

                    if (isHidden) {
                        // Show the panel
                        filtersPanel.style.display = 'block';
                        filtersPanel.style.animation = 'slideDown 0.3s ease-out';

                        // Update button appearance to show active state
                        newBtn.innerHTML = '<i class="bi bi-funnel-fill me-1"></i> Hide Filters';
                        newBtn.classList.remove('btn-outline-primary');
                        newBtn.classList.add('btn-primary');

                        localStorage.setItem('advancedFiltersOpen', 'true');
                    } else {
                        // Hide the panel
                        filtersPanel.style.animation = 'slideUp 0.3s ease-out';
                        setTimeout(() => {
                            filtersPanel.style.display = 'none';
                        }, 300);

                        // Update button appearance to show inactive state
                        newBtn.innerHTML = '<i class="bi bi-funnel me-1"></i> Show Filters';
                        newBtn.classList.remove('btn-primary');
                        newBtn.classList.add('btn-outline-primary');

                        localStorage.setItem('advancedFiltersOpen', 'false');
                    }
                }
            });

            // Add visual feedback for proper button interaction
            newBtn.addEventListener('mouseenter', () => {
                if (!newBtn.classList.contains('btn-primary')) {
                    newBtn.style.transform = 'translateY(-1px)';
                }
            });

            newBtn.addEventListener('mouseleave', () => {
                newBtn.style.transform = 'translateY(0)';
            });

            // Restore previous state on page load
            const wasOpen = localStorage.getItem('advancedFiltersOpen') === 'true';
            const filtersPanel = document.getElementById('advancedFilters');

            if (wasOpen && filtersPanel) {
                // Restore open state
                filtersPanel.style.display = 'block';
                newBtn.innerHTML = '<i class="bi bi-funnel-fill me-1"></i> Hide Filters';
                newBtn.classList.remove('btn-outline-primary');
                newBtn.classList.add('btn-primary');
            } else if (filtersPanel) {
                // Default to closed state (no saved state or explicitly closed)
                filtersPanel.style.display = 'none';
                newBtn.innerHTML = '<i class="bi bi-funnel me-1"></i> Show Filters';
                newBtn.classList.remove('btn-primary');
                newBtn.classList.add('btn-outline-primary');
            }
        }

        // Column Settings button - ensure it doesn't interfere and fix z-index issues
        const columnSettingsBtn = document.getElementById('column-settings-toggle');
        if (columnSettingsBtn) {
            // Add event listener to prevent interference
            columnSettingsBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                // Bootstrap dropdown will handle the rest
            });

            // Add visual feedback
            columnSettingsBtn.addEventListener('mouseenter', () => {
                columnSettingsBtn.style.transform = 'translateY(-1px)';
            });

            columnSettingsBtn.addEventListener('mouseleave', () => {
                columnSettingsBtn.style.transform = 'translateY(0)';
            });

            // Fix z-index issues by moving dropdown to body when shown
            this.initializeColumnDropdownFix(columnSettingsBtn);
        }

    },

    /**
     * Fix column dropdown z-index issues with simpler approach
     */
    initializeColumnDropdownFix(columnSettingsBtn) {
        const dropdown = columnSettingsBtn.closest('.dropdown');
        if (!dropdown) return;

        // Simple fix: just increase z-index when shown
        dropdown.addEventListener('show.bs.dropdown', () => {
            dropdown.style.zIndex = '9999';
        });

        dropdown.addEventListener('hide.bs.dropdown', () => {
            dropdown.style.zIndex = '';
        });
    }
};

// Start the application
App.init();

// Export for global access
window.BrowserAJAX = BrowserAJAX;
window.PRODUCTION_CONFIG = PRODUCTION_CONFIG;
window.Utils = Utils;
window.StateManager = StateManager;
window.APIManager = APIManager;
window.TableManager = TableManager;
window.FilterManager = FilterManager;
window.PaginationManager = PaginationManager;
window.SelectionManager = SelectionManager;
window.ColumnManager = ColumnManager;
window.SortingManager = SortingManager;

