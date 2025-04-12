/**
 * Combined column management functionality
 * Merges column-settings-rebuild.js, column-toggle.js, table-column-classes.js, and toggle-refresh.js
 */

class ColumnManager {
    constructor() {
        this.isInitializing = true;
        this.allColumnsVisible = false;
        this.lastMessage = '';
        this.lastMessageTime = 0;
        this.COLUMNS_INITIALIZED_KEY = 'columnsInitialized';
        this.previousColumnStates = null; // Store previous column states

        // Initialize column mappings
        this.columnMappings = {
            'fastq_name': { title: 'Fastq Name', category: 'sample', domClass: 'fastq-name' },
            'study_set': { title: 'Study Set', category: 'sample', domClass: 'study-set' },
            'load_name': { title: 'Load Name', category: 'sample', domClass: 'load-name' },
            'batch_name': { title: 'Batch Name', category: 'sample', domClass: 'batch-name' },
            'batch_name_from_vendor': { title: 'Batch Name From Vendor', category: 'sample', domClass: 'batch-name-from-vendor' },
            'cell_capture': { title: 'Cell Capture', category: 'sample', domClass: 'cell-capture' },
            'sample_id': { title: 'Sample ID', category: 'sample', domClass: 'sample-id' },
            'amplification_name': { title: 'Amplification', category: 'amplification', domClass: 'amplification-name' },
            'amplification_id': { title: 'Amplification ID', category: 'amplification', domClass: 'amplification-id' },
            'cell_prep_type': { title: 'Cell Prep Type', category: 'preparation', domClass: 'cell-prep-type' },
            'sequencing_vendor': { title: 'Sequencing Vendor', category: 'preparation', domClass: 'sequencing-vendor' },
            'alignment_method': { title: 'Alignment Method', category: 'preparation', domClass: 'alignment-method' },
            'library_prep_method_id': { title: 'Library Prep Method ID', category: 'library', domClass: 'library-prep-method-id' },
            'library_prep_name': { title: 'Library Prep Name', category: 'library', domClass: 'library-prep-name' },
            'library_prep_method': { title: 'Library Prep Method', category: 'library', domClass: 'library-prep-method' },
            'organism_common_name': { title: 'Organism Common Name', category: 'organism', domClass: 'organism-common-name' },
            'ingest_status': { title: 'Ingest Status', category: 'status', domClass: 'ingest-status' },
            'alignment_status': { title: 'Alignment Status', category: 'status', domClass: 'alignment-status' },
            'postqc_status': { title: 'PostQC Status', category: 'status', domClass: 'postqc-status' },
            'ingest_fid': { title: 'Ingest FID', category: 'fid', domClass: 'ingest-fid' },
            'alignment_fid': { title: 'Alignment FID', category: 'fid', domClass: 'alignment-fid' },
            'postqc_fid': { title: 'PostQC FID', category: 'fid', domClass: 'postqc-fid' },
            'ingest_start_time': { title: 'Ingest Start', category: 'time', domClass: 'ingest-start-time' },
            'ingest_end_time': { title: 'Ingest End', category: 'time', domClass: 'ingest-end-time' },
            'alignment_start_time': { title: 'Alignment Start', category: 'time', domClass: 'alignment-start-time' },
            'alignment_end_time': { title: 'Alignment End', category: 'time', domClass: 'alignment-end-time' },
            'postqc_start_time': { title: 'PostQC Start', category: 'time', domClass: 'postqc-start-time' },
            'postqc_end_time': { title: 'PostQC End', category: 'time', domClass: 'postqc-end-time' }
        };

        // Add alternative names mapping for backward compatibility
        this.columnAliases = {
            'fastqname': 'fastq_name',
            'studyset': 'study_set',
            'loadname': 'load_name',
            'batchname': 'batch_name',
            'batchnamefromvendor': 'batch_name_from_vendor',
            'cellcapture': 'cell_capture',
            'sampleid': 'sample_id',
            'amplificationname': 'amplification_name',
            'amplificationid': 'amplification_id',
            'cellpreptype': 'cell_prep_type',
            'sequencingvendor': 'sequencing_vendor',
            'alignmentmethod': 'alignment_method',
            'libraryprepmethod': 'library_prep_method',
            'libraryprepmethodid': 'library_prep_method_id',
            'libraryprepname': 'library_prep_name',
            'organism': 'organism_common_name',
            'organismcommonname': 'organism_common_name'
        };

        // Default visible columns
        this.defaultVisibleColumns = [
            'fastq_name',
            'study_set',
            'load_name',
            'library_prep_method',
            'organism_common_name',
            'ingest_status',
            'alignment_status',
            'postqc_status'
        ];

        this.initializeSettings();
        this.setupEventListeners();
    }

    initializeSettings() {
        if (!localStorage.getItem(this.COLUMNS_INITIALIZED_KEY)) {
            console.log('First visit detected, initializing default column settings');
            this.setDefaultColumnVisibility();
            localStorage.setItem(this.COLUMNS_INITIALIZED_KEY, 'true');
        }

        const savedSettings = localStorage.getItem('columnVisibilitySettings');
        this.columnSettings = savedSettings ? JSON.parse(savedSettings) : this.getDefaultSettings();

        this.applySettings();
        console.log('Column settings initialized:', this.columnSettings);
    }

    setDefaultColumnVisibility() {
        const settings = {};
        Object.keys(this.columnMappings).forEach(columnName => {
            settings[columnName] = this.defaultVisibleColumns.includes(columnName);
        });
        this.columnSettings = settings;
        this.saveSettings();
        console.log('Default column visibility set:', settings);
    }

    getDefaultSettings() {
        const settings = {};
        Object.keys(this.columnMappings).forEach(columnName => {
            settings[columnName] = this.defaultVisibleColumns.includes(columnName);
        });
        return settings;
    }

    setupEventListeners() {
        // Individual column toggles
        document.querySelectorAll('.column-toggle-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => this.handleColumnToggle(e));

            // Set initial state
            const columnName = this.getColumnNameFromCheckbox(checkbox);
            if (columnName && this.columnSettings[columnName] !== undefined) {
                checkbox.checked = this.columnSettings[columnName];
            }
        });

        // Toggle all columns
        const toggleAllCheckbox = document.getElementById('toggleAllColumns');
        if (toggleAllCheckbox) {
            toggleAllCheckbox.addEventListener('change', (e) => this.handleToggleAll(e));
        }

        // Reset to defaults
        const resetButton = document.getElementById('resetColumnDefaults');
        if (resetButton) {
            resetButton.addEventListener('click', () => this.resetToDefaults());
        }

        console.log('Event listeners set up');
    }

    handleColumnToggle(event) {
        const checkbox = event.target;
        const columnName = this.getColumnNameFromCheckbox(checkbox);

        if (columnName) {
            console.log(`Toggling column ${columnName} to ${checkbox.checked}`);
            this.columnSettings[columnName] = checkbox.checked;
            this.saveSettings();
            this.applyColumnVisibility(columnName, checkbox.checked);
            this.updateToggleAllState();
            showFeedbackMessage(`${checkbox.checked ? 'Showing' : 'Hiding'} ${this.columnMappings[columnName]?.title || columnName}...`, 'success');
        }
    }

    handleToggleAll(event) {
        const isChecked = event.target.checked;
        console.log(`Toggle all columns to ${isChecked}`);

        if (isChecked) {
            // Store current state before showing all
            this.previousColumnStates = { ...this.columnSettings };

            // Show all columns
            document.querySelectorAll('.column-toggle-checkbox').forEach(checkbox => {
                checkbox.checked = true;
                const columnName = this.getColumnNameFromCheckbox(checkbox);
                if (columnName) {
                    this.columnSettings[columnName] = true;
                    this.applyColumnVisibility(columnName, true);
                }
            });
        } else {
            // Restore previous state
            if (this.previousColumnStates) {
                document.querySelectorAll('.column-toggle-checkbox').forEach(checkbox => {
                    const columnName = this.getColumnNameFromCheckbox(checkbox);
                    if (columnName) {
                        const previousState = this.previousColumnStates[columnName];
                        checkbox.checked = previousState;
                        this.columnSettings[columnName] = previousState;
                        this.applyColumnVisibility(columnName, previousState);
                    }
                });
            }
        }

        this.saveSettings();
        this.updateToggleAllState();
        showFeedbackMessage(isChecked ? 'Showing all columns...' : 'Restoring previous column visibility...', 'success');
    }

    applyColumnVisibility(columnName, isVisible) {
        const table = document.querySelector('.table');
        if (!table) {
            console.error('Table not found');
            return;
        }

        // Normalize the column name
        const normalizedName = this.normalizeColumnName(columnName);
        const columnInfo = this.columnMappings[normalizedName];

        if (!columnInfo) {
            console.warn(`No column mapping found for ${columnName}`);
            return;
        }

        // Try multiple class patterns to find the right elements
        const selectors = [
            `th[data-column="${normalizedName}"], td[data-column="${normalizedName}"]`,
            `th[data-column="${columnName}"], td[data-column="${columnName}"]`,
            `th.field-${normalizedName}, td.field-${normalizedName}`,
            `th.column-${normalizedName}, td.column-${normalizedName}`,
            `th.${columnInfo.domClass}, td.${columnInfo.domClass}`,
            `th[data-field="${normalizedName}"], td[data-field="${normalizedName}"]`
        ];

        let elements = [];
        selectors.forEach(selector => {
            const found = table.querySelectorAll(selector);
            if (found.length > 0) {
                elements = [...elements, ...found];
            }
        });

        if (elements.length === 0) {
            console.warn(`No elements found for column ${columnName}`);
            return;
        }

        elements.forEach(element => {
            element.style.display = isVisible ? '' : 'none';
            element.classList.add('animate-column-toggle');
            setTimeout(() => {
                element.classList.remove('animate-column-toggle');
            }, 300);
        });

        console.log(`Applied visibility ${isVisible} to ${elements.length} elements for column ${columnName}`);
    }

    resetToDefaults() {
        console.log('Resetting to default column settings');
        this.columnSettings = this.getDefaultSettings();
        this.saveSettings();
        this.applySettings();
        this.updateCheckboxes();
        this.updateToggleAllState();
        showFeedbackMessage('Resetting to default columns...', 'success');
    }

    applySettings() {
        Object.entries(this.columnSettings).forEach(([columnName, isVisible]) => {
            this.applyColumnVisibility(columnName, isVisible);
        });
        this.updateCheckboxes();
        this.updateToggleAllState();
    }

    updateCheckboxes() {
        document.querySelectorAll('.column-toggle-checkbox').forEach(checkbox => {
            const columnName = this.getColumnNameFromCheckbox(checkbox);
            if (columnName && this.columnSettings[columnName] !== undefined) {
                checkbox.checked = this.columnSettings[columnName];
            }
        });
    }

    updateToggleAllState() {
        const toggleAllCheckbox = document.getElementById('toggleAllColumns');
        if (!toggleAllCheckbox) return;

        const allCheckboxes = Array.from(document.querySelectorAll('.column-toggle-checkbox'));
        const allChecked = allCheckboxes.every(cb => cb.checked);
        const allUnchecked = allCheckboxes.every(cb => !cb.checked);

        toggleAllCheckbox.checked = allChecked;
        toggleAllCheckbox.indeterminate = !allChecked && !allUnchecked;
        this.allColumnsVisible = allChecked;
        this.updateToggleAllLabel(allChecked);
    }

    updateToggleAllLabel(allVisible) {
        const label = document.getElementById('toggleAllColumnsLabel');
        if (label) {
            label.textContent = allVisible ? 'Hide All Columns' : 'Show All Columns';
        }
    }

    getColumnNameFromCheckbox(checkbox) {
        // Try different patterns to get the column name
        const columnAttr = checkbox.getAttribute('data-column');
        if (columnAttr) {
            const name = columnAttr.replace(/^(column-|field-)/, '');
            return this.normalizeColumnName(name);
        }

        // Try to get from ID
        const id = checkbox.id;
        if (id && id.startsWith('toggle')) {
            const name = id.replace('toggle', '').toLowerCase();
            return this.normalizeColumnName(this.toCamelCase(name));
        }

        console.warn('Could not determine column name from checkbox:', checkbox);
        return null;
    }

    normalizeColumnName(name) {
        // First check if it's a direct match
        if (this.columnMappings[name]) {
            return name;
        }

        // Check aliases
        if (this.columnAliases[name]) {
            return this.columnAliases[name];
        }

        // Try converting from camelCase to snake_case
        const snakeCase = name.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
        if (this.columnMappings[snakeCase]) {
            return snakeCase;
        }

        return name;
    }

    toCamelCase(str) {
        return str.replace(/[-_]([a-z])/g, (g) => g[1].toLowerCase());
    }

    saveSettings() {
        localStorage.setItem('columnVisibilitySettings', JSON.stringify(this.columnSettings));
        console.log('Saved column settings:', this.columnSettings);
    }

    debugTableColumns() {
        const table = document.querySelector('.table');
        if (!table) {
            console.warn('No table found in the DOM');
            return;
        }

        console.log('===== TABLE COLUMN DEBUG =====');
        const headers = table.querySelectorAll('thead th');
        headers.forEach((header, index) => {
            console.log(`Column ${index}: "${header.textContent.trim()}" - Classes: ${header.className}`);
        });

        const firstRow = table.querySelector('tbody tr');
        if (firstRow) {
            const cells = firstRow.querySelectorAll('td');
            console.log('===== FIRST ROW CELLS =====');
            cells.forEach((cell, index) => {
                console.log(`Cell ${index}: Classes: ${cell.className}`);
            });
        }

        console.log('===== COLUMN MAPPINGS =====');
        Object.entries(this.columnMappings).forEach(([key, value]) => {
            console.log(`${key} -> "${value.title}" (${value.category})`);
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.columnManager = new ColumnManager();
}); 