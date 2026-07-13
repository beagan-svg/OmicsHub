/**
 * pipeline-submit-modal.js
 * Handles the submission modal functionality for the RNA-seq pipeline
 * Integrated with ModalManager for modern modal handling
 */

class PipelineSubmitModal {
    constructor() {

        // Initialize DOM elements
        this.initDOMElements();

        // Initialize state
        this.initState();

        // Set up styles
        this.addStyles();

        // Set up event listeners
        this.setupEventListeners();

        // Load configuration
        this.loadConfig();

    }

    /**
     * Initialize DOM element references
     */
    initDOMElements() {
        this.modal = document.getElementById('submit-modal');
        this.sampleList = document.getElementById('submit-sample-list');
        this.warningDiv = document.getElementById('incomplete-samples-warning');
        this.incompleteList = document.getElementById('incomplete-samples-list');
        this.confirmButton = document.getElementById('confirm-submit');
        this.autoProceedToggle = document.getElementById('auto-proceed-toggle');
        this.alignmentBatches = document.getElementById('alignment-batches');
        this.postQCBatches = document.getElementById('postqc-batches');
        this.globalNotificationEmail = document.getElementById('global-notification-email');

    }

    /**
     * Initialize state variables
     */
    initState() {
        // Add originalCommands map to store commands before editing
        this.originalCommands = new Map();

        // Sample tracking
        this.alignmentSamples = [];
        this.postQCSamples = [];
        this.incompleteSamples = [];
        this.unknownLibraryPrepMethodSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // State preservation
        this.savedState = null;

        // Configuration will be loaded from server
        this.config = null;

    }

    /**
     * Load configuration from server
     */
    async loadConfig() {
        try {
            const response = await fetch('/api/pipeline/config');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.config = await response.json();

            // After loading config, update any existing UI elements
            if (this.modal && this.modal.classList.contains('show')) {
                this.populateModal();
            }
        } catch (error) {
            console.warn('[PipelineSubmitModal] API config not available, using fallback configuration:', error.message);

            // Use fallback configuration
            this.config = this.getFallbackConfig();

            // After loading fallback config, update any existing UI elements
            if (this.modal && this.modal.classList.contains('show')) {
                this.populateModal();
            }
        }
    }

    /**
     * Get fallback configuration when API is not available
     * This matches the structure from the actual pipeline_config.yaml
     */
    getFallbackConfig() {
        return {
            references: {
                armadillo: "armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a",
                human: "human_10x_grch38_genome_star2.7.1a",
                mouse: "mouse_10x_mm10_genome_star2.7.1a",
                macaque: "macaque_ncbi_mmul10_genome_star2.7.1a",
                rat: "rat_ncbi_mratbn7.2_genome_star2.7.1a"
            },
            chemistries: {
                '10xV3.1D': 'SC3Pv3',
                '10xRseq_Mult_noATAC': 'ARC-v1',
                '10xV3.1_HT': 'SC3Pv3HT',
                '10xV4': 'SC3Pv4',
                '10Xv2': 'SC3Pv2'
            },
            workflows: {
                rtx: {
                    alignment: {
                        '10xV3.1D|10xRseq_Mult_noATAC|10xV3.1_HT|10Xv3.1': {
                            asset_name: 'cellranger-rnaseq',
                            asset_tag: 'latest',
                            command_template: 'ocs fastqs align tenx-rnaseq --asset-name cellranger-rnaseq --reference-names "{reference}" --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry} --include-introns" --notify-on FAILED --notify {notification_email}'
                        },
                        '10xV3.1_HT_CP|10xV3.1_HT_CP-BC': {
                            asset_name: 'cellranger-multi',
                            command_template: 'ocs fastqs align tenx-rnaseq-multi --asset-name cellranger-multi --reference-names "{reference}" --load-names "{load_name}" --cellranger-addopts "--include-introns" --execution-priority HIGH --notify-on FAILED --notify {notification_email}'
                        },
                        '10xV4': {
                            asset_name: 'cellranger-rnaseq',
                            asset_tag: '8.0.1',
                            command_template: 'ocs fastqs align tenx-rnaseq --asset-name cellranger-rnaseq --reference-names "{reference}" --asset-tag 8.0.1 --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry}" --notify-on FAILED --notify {notification_email}'
                        }
                    },
                    postqc: {
                        '10xV4': {
                            asset_name: 'tenx_rnaseq_qc',
                            asset_tag: '25.03.27',
                            command_template: 'ocs fastqs postalign tenx-rnaseq --asset-name tenx_rnaseq_qc --asset-tag 25.03.27 --load-names "{load_name}" --notify-on FAILED --notify {notification_email}'
                        },
                        'default': {
                            asset_name: 'tenx_rnaseq_qc',
                            asset_tag: '25.03.27',
                            command_template: 'ocs fastqs postalign tenx-rnaseq --asset-name tenx_rnaseq_qc --asset-tag 25.03.27 --load-names "{load_name}" --notify-on FAILED --notify {notification_email}'
                        }
                    }
                },
                mtx: {
                    alignment: {
                        asset_name: 'cellranger-arc',
                        command_template: 'ocs fastqs align tenx-arc --asset-name cellranger-arc --reference-names "{reference}" --load-names "{load_name}" --notify-on FAILED --notify {notification_email}'
                    },
                    postqc: {
                        asset_name: 'multi_gex_qc',
                        asset_tag: 'latest',
                        command_template: 'ocs fastqs postalign tenx-arc --asset-name multi_gex_qc --asset-tag latest --load-names "{load_name}" --notify-on FAILED --notify {notification_email}'
                    }
                }
            }
        };
    }

    /**
     * Get reference options for UI dropdown
     * @returns {Array} Array of reference options
     */
    getReferences() {
        if (!this.config) return [];

        return Object.entries(this.config.references).map(([name, value]) => ({
            name: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
            value: value
        }));
    }

    /**
     * Get chemistry options for UI dropdown
     * @returns {Array} Array of chemistry options
     */
    getChemistries() {
        if (!this.config) return [];

        // Add None option first
        const chemistries = [{
            name: 'None',
            value: '',
            prep: ''
        }];

        // Add other chemistries from config
        Object.entries(this.config.chemistries).forEach(([prep, chemistry]) => {
            chemistries.push({
                name: `${chemistry} (${prep})`,
                value: chemistry,
                prep: prep
            });
        });

        return chemistries;
    }

    /**
     * Get asset name for workflow/stage/library prep combination
     */
    getAssetName(workflow, stage, libraryPrep) {
        if (!this.config?.workflows?.[workflow]?.[stage]) return '';

        const workflowConfig = this.config.workflows[workflow][stage];

        // For RTX workflow with library prep, find matching pattern
        if (workflow === 'RTX' && libraryPrep) {
            for (const [pattern, config] of Object.entries(workflowConfig)) {
                if (pattern.split('|').includes(libraryPrep)) {
                    return config.asset_name || '';
                }
            }
        }

        // Return default asset name for the workflow/stage
        return workflowConfig.asset_name || '';
    }

    /**
     * Get asset tag for workflow/stage/library prep combination
     */
    getAssetTag(workflow, stage, libraryPrep) {
        if (!this.config?.workflows?.[workflow]?.[stage]) return 'latest';

        const workflowConfig = this.config.workflows[workflow][stage];

        // For RTX workflow with library prep, find matching pattern
        if (workflow === 'RTX' && libraryPrep) {
            for (const [pattern, config] of Object.entries(workflowConfig)) {
                if (pattern.split('|').includes(libraryPrep)) {
                    return config.asset_tag || 'latest';
                }
            }
        }

        // Return default asset tag for the workflow/stage
        return workflowConfig.asset_tag || 'latest';
    }

    /**
     * Get notification email from UI or default
     */
    getNotificationEmail() {
        return this.globalNotificationEmail?.value?.trim() ||
            '$USER@alleninstitute.org';
    }

    /**
     * Get reference for organism
     */
    getReference(organism) {
        if (!this.config?.references) {
            return '';
        }

        const normalizedOrganism = organism.toLowerCase().replace(/\s+/g, '_');
        return this.config.references[normalizedOrganism] || this.config.references.human || '';
    }

    /**
     * Get chemistry for library prep method
     * @param {string} libraryPrep - Library prep method
     * @returns {string} Chemistry name
     */
    getChemistry(libraryPrep) {
        if (!this.config?.chemistries) {
            return '';
        }

        return this.config.chemistries[libraryPrep] || '';
    }

    /**
     * Set up all event listeners
     */
    setupEventListeners() {
        this.setupModalEvents();
        this.setupFormEvents();
        this.setupCommandActions();
        this.setupNotificationEvents();
        this.setupFinalModalEvents();
    }

    /**
     * Set up modal-specific events
     */
    setupModalEvents() {
        // Ensure modal has static backdrop before it's shown
        if (this.modal && !this.modal.hasAttribute('data-bs-backdrop')) {
            this.modal.setAttribute('data-bs-backdrop', 'static');
            this.modal.setAttribute('data-bs-keyboard', 'true');
        }

        // Handle modal show event
        this.modal.addEventListener('show.bs.modal', (event) => {
            this.populateModal();
            this.setupModalCloseHandlers();

            // Reinforce static backdrop setting when the modal is about to show
            const modalInstance = bootstrap.Modal.getInstance(this.modal);
            if (modalInstance && modalInstance._config) {
                modalInstance._config.backdrop = 'static';
                modalInstance._config.keyboard = true;
            }
        });

        // Handle modal hidden event to ensure cleanup
        this.modal.addEventListener('hidden.bs.modal', (event) => {
            // Modal manager will handle backdrop cleanup automatically
        });

        // Add close button handler for submit modal
        const submitModalCloseBtn = this.modal.querySelector('.btn-close');
        if (submitModalCloseBtn) {
            submitModalCloseBtn.onclick = (e) => {
                e.preventDefault();
                if (window.modalManager) {
                    window.modalManager.closeModal('submit-modal');
                }
            };
        }

        // Add cancel button handler
        const cancelButton = this.modal.querySelector('.btn-cancel, .btn-secondary');
        if (cancelButton) {
            cancelButton.onclick = (e) => {
                e.preventDefault();
                if (window.modalManager) {
                    window.modalManager.closeModal('submit-modal');
                }
            };
        }
    }

    /**
     * Set up form-related events
     */
    setupFormEvents() {
        // Handle auto-proceed toggle change
        if (this.autoProceedToggle) {
            this.autoProceedToggle.addEventListener('change', () => {
                this.updateCommandLists();
            });
        }

        // Handle reprocess completed toggle change
        const reprocessToggle = document.getElementById('reprocess-completed-toggle');
        if (reprocessToggle) {
            reprocessToggle.addEventListener('change', () => {

                // Get the current selected samples (they should be cached from initial modal population)
                const selectedSamples = this.getSelectedSamples();

                // Re-categorize samples with the new toggle state
                this.categorizeSamples(selectedSamples);

                this.updateCommandLists();
            });
        }

        // Handle confirm button click
        this.confirmButton.addEventListener('click', () => {
            this.handleSubmission();
        });
    }

    /**
     * Set up command action events (edit, reset, etc.)
     */
    setupCommandActions() {
        // Edit button click
        this.modal.addEventListener('click', (e) => {
            const editButton = e.target.closest('.edit-command');
            if (editButton) {
                e.preventDefault();
                this.handleEditCommand(editButton);
            }
        });

        // Cancel button click
        this.modal.addEventListener('click', (e) => {
            const cancelButton = e.target.closest('.cancel-edit');
            if (cancelButton) {
                e.preventDefault();
                this.handleCancelEdit(cancelButton);
            }
        });

        // Save button click (now just confirms and closes the form)
        this.modal.addEventListener('click', (e) => {
            const saveButton = e.target.closest('.save-command');
            if (saveButton) {
                e.preventDefault();
                const form = saveButton.closest('.command-edit-form');
                form.classList.remove('show');
            }
        });

        // Reset button click
        this.modal.addEventListener('click', (e) => {
            if (e.target.closest('.reset-command')) {
                this.handleResetCommand(e.target.closest('.reset-command'));
            }
        });
    }

    /**
     * Set up notification email events
     */
    setupNotificationEvents() {
        // Handle global notification email changes
        if (this.globalNotificationEmail) {
            this.globalNotificationEmail.addEventListener('input', () => {
                this.updateAllCommandsWithEmail();
            });

            // Set initial value from config
            this.globalNotificationEmail.value = this.getNotificationEmail();
        }
    }

    /**
     * Set up final modal events
     */
    setupFinalModalEvents() {
        // Set up event listeners for final modal events
        document.addEventListener('finalModalBack', () => {
            // Back button clicked in final modal - modal manager will handle the transition
            this.restoreState();
        });

        document.addEventListener('finalModalExecute', (event) => {
            this.handleFinalExecution(event.detail.commands);
        });

        // Final modal close is handled by modal manager
        document.addEventListener('finalModalClose', () => {
            // Modal manager handles backdrop cleanup automatically
        });
    }

    /**
     * Set up modal close handlers for ESC key only (no outside click)
     */
    setupModalCloseHandlers() {
        // Remove any existing keydown listeners to prevent duplicates
        document.removeEventListener('keydown', this.escapeKeyHandler);

        // Create a single escape key handler that works for both modals
        this.escapeKeyHandler = (e) => {
            if (e.key === 'Escape') {
                // Check if submit modal is open
                if (this.modal && this.modal.classList.contains('show')) {
                    if (window.modalManager) {
                        window.modalManager.closeModal('submit-modal');
                        return;
                    }
                }

                // Check if final modal is open
                const finalModal = document.getElementById('final-commands-modal');
                if (finalModal && finalModal.classList.contains('show')) {
                    if (window.modalManager) {
                        window.modalManager.closeModal('final-commands-modal');
                        return;
                    }
                }
            }
        };

        // Add the single escape key handler
        document.addEventListener('keydown', this.escapeKeyHandler);
    }

    /**
     * Handle edit command button click
     * @param {HTMLElement} editButton - The edit button element
     */
    handleEditCommand(editButton) {
        const cell = editButton.closest('.command-cell');
        const row = cell.closest('tr');
        const currentCommand = cell.querySelector('code').textContent;
        const stage = row.dataset.stage;
        const sampleName = row.dataset.sample;
        const workflow = row.dataset.workflow;
        const isAutoProceed = row.hasAttribute('data-auto-proceed');

        // Parse the current command to extract asset tag and other values
        const currentValues = this.parseCommand(currentCommand);

        // Store the original command state with a unique key
        const commandKey = `${sampleName}-${stage}-${isAutoProceed ? 'auto' : 'regular'}`;
        this.originalCommands.set(commandKey, {
            command: currentCommand,
            values: currentValues,
            originalWorkflow: workflow // Store the original workflow
        });

        // Find sample directly from our tracked arrays by fastq_name
        let sample = null;

        if (stage === 'alignment' || (stage === 'postqc' && isAutoProceed)) {
            // For alignment or auto-proceed post-QC, look in alignment samples
            sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleName);
        } else {
            // Regular post-QC samples
            sample = this.postQCSamples.find(s => s.fastq_name === sampleName);
        }

        if (!sample) {
            console.error('Could not find sample in our data arrays');
            return;
        }

        // IMPORTANT: Preserve the original workflow from the row
        // We're removing the workflow detection code to prevent unwanted changes
        sample.workflow = workflow;

        // Store asset tag in the sample object if it exists in the command
        if (currentValues.assetTag) {
            sample.assetTag = currentValues.assetTag;
        }


        // Get the existing form and replace it
        const existingForm = cell.querySelector('.command-edit-form');
        if (existingForm) {
            // Create a temporary container to parse the HTML
            const tempContainer = document.createElement('div');
            const formHtml = this.createCommandEditForm(sample, stage, currentCommand);
            tempContainer.innerHTML = formHtml;
            const newForm = tempContainer.firstElementChild;

            // Replace the existing form
            existingForm.parentNode.replaceChild(newForm, existingForm);

            // Show the new form
            newForm.classList.add('show');

            // Make sure the asset tag field is correctly populated
            if (stage === 'postqc') {
                const assetTagInput = newForm.querySelector('.asset-tag-input');
                if (assetTagInput) {
                    // Check if we have a value from parsed command or from sample
                    const tagValue = currentValues.assetTag || sample.assetTag || '';
                    if (tagValue && (!assetTagInput.value || assetTagInput.value !== tagValue)) {
                        assetTagInput.value = tagValue;
                    }
                }
            }

            // Add event listeners to the new form
            this.setupEditFormListeners(newForm);
        }
    }

    /**
     * Setup event listeners for edit form
     * @param {HTMLElement} form - The form element
     */
    setupEditFormListeners(form) {
        const row = form.closest('tr');
        const fastqName = row.querySelector('td:first-child')?.textContent?.trim();
        const stage = row.dataset.stage;


        // Find the sample data
        let sample;
        if (stage === 'alignment') {
            sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === fastqName);
        } else {
            sample = this.postQCSamples.find(s => s.fastq_name === fastqName);
        }

        // Special handling for asset tag input
        const assetTagInput = form.querySelector('.asset-tag-input');
        if (assetTagInput) {
            // Get initial value
            const initialTag = assetTagInput.value;

            // Store on sample if not empty
            if (sample) {
                // Always store the initial value, even if empty
                sample.assetTag = initialTag;

                // CRITICAL: Force immediate command update to ensure asset tag is displayed
                this.updateCommandPreview(form);
            }

            // Add special input event listener that updates the command in real-time
            assetTagInput.addEventListener('input', (e) => {
                const newTag = e.target.value.trim();

                // Update the sample object
                if (sample) {
                    // Store the new value
                    sample.assetTag = newTag;
                }

                // Force an immediate command preview update
                this.updateCommandPreview(form);

                // Force a DOM update to ensure change is visible
                setTimeout(() => {
                    const codeElement = form.closest('.command-cell').querySelector('code');
                    const currentCommand = codeElement.textContent;
                    const hasTag = newTag ? currentCommand.includes(`--asset-tag ${newTag}`) : true;

                    // If the tag is still missing, force it again
                    if (newTag && !hasTag) {
                        console.error('EMERGENCY FIX - Asset tag still missing from command');
                        const fixedCommand = currentCommand.replace(/--asset-tag\s+[^\s]+/g, '').replace(/--load-names/, `--asset-tag ${newTag} --load-names`);
                        codeElement.textContent = fixedCommand;
                    }
                }, 10);
            });
        }

        // Add event listeners to other form inputs
        const otherInputs = form.querySelectorAll('input:not(.asset-tag-input), select');
        otherInputs.forEach(input => {
            input.addEventListener('change', () => {
                this.updateCommandPreview(form);
            });
        });

        // For other text inputs, also listen for keyup events
        const otherTextInputs = form.querySelectorAll('input[type="text"]:not(.asset-tag-input)');
        otherTextInputs.forEach(input => {
            input.addEventListener('keyup', () => {
                this.updateCommandPreview(form);
            });
        });

        // Handle cancel button
        const cancelButton = form.querySelector('.cancel-edit');
        if (cancelButton) {
            cancelButton.addEventListener('click', () => {
                form.classList.remove('show');
            });
        }

        // Handle save button
        const saveButton = form.querySelector('.save-command');
        if (saveButton) {
            saveButton.addEventListener('click', () => {
                // Get the current values from the form before hiding it
                if (assetTagInput && sample) {
                    const finalTag = assetTagInput.value.trim();
                    sample.assetTag = finalTag;

                    // Force a final update before hiding
                    this.updateCommandPreview(form);
                }
                form.classList.remove('show');
            });
        }
    }

    /**
     * Handle cancel edit button click
     * @param {HTMLElement} cancelButton - The cancel button element
     */
    handleCancelEdit(cancelButton) {
        const form = cancelButton.closest('.command-edit-form');
        const cell = form.closest('.command-cell');
        const row = cell.closest('tr');
        const sampleName = row.dataset.sample;
        const stage = row.dataset.stage;
        const isAutoProceed = row.hasAttribute('data-auto-proceed');

        // Get the original command state
        const commandKey = `${sampleName}-${stage}-${isAutoProceed ? 'auto' : 'regular'}`;
        const originalState = this.originalCommands.get(commandKey);

        if (originalState) {
            // Restore the command display
            const codeElement = cell.querySelector('code');
            codeElement.textContent = originalState.command;

            // Update the form inputs with original values
            this.restoreFormValues(form, originalState.values);

            // Update the sample's stored command
            this.updateSampleCommand(sampleName, stage, originalState.command);

            // Restore the original workflow if it was stored
            if (originalState.originalWorkflow) {
                let sample;
                if (stage === 'alignment' || (stage === 'postqc' && isAutoProceed)) {
                    sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleName);
                } else {
                    sample = this.postQCSamples.find(s => s.fastq_name === sampleName);
                }

                if (sample) {
                    sample.workflow = originalState.originalWorkflow;
                }
            }

            // Clean up the stored state
            this.originalCommands.delete(commandKey);
        }

        // Hide the form
        form.classList.remove('show');
    }

    /**
     * Restore form values from original state
     * @param {HTMLElement} form - The form element
     * @param {Object} values - The values to restore
     */
    restoreFormValues(form, values) {
        if (!values) return;

        const baseCommandInput = form.querySelector('.command-input');
        if (baseCommandInput) baseCommandInput.value = values.baseCommand || '';

        const referenceSelect = form.querySelector('.reference-select');
        if (referenceSelect) referenceSelect.value = values.reference || '';

        const chemistrySelect = form.querySelector('.chemistry-select');
        if (chemistrySelect) chemistrySelect.value = values.chemistry || '';

        const includeIntronsCheck = form.querySelector('.include-introns');
        if (includeIntronsCheck) includeIntronsCheck.checked = values.includeIntrons || false;

        const executionPriorityCheck = form.querySelector('.execution-priority');
        if (executionPriorityCheck) executionPriorityCheck.checked = values.executionPriority || false;

        const assetTagInput = form.querySelector('.asset-tag-input');
        if (assetTagInput) assetTagInput.value = values.assetTag || '';
    }

    /**
     * Update a sample's command
     * @param {string} sampleName - The sample name
     * @param {string} stage - The pipeline stage
     * @param {string} command - The command to set
     */
    updateSampleCommand(sampleName, stage, command) {
        let sample;
        if (stage === 'alignment') {
            sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleName);
        } else {
            sample = this.postQCSamples.find(s => s.fastq_name === sampleName);
        }

        if (sample) {
            if (stage === 'alignment') {
                sample.alignmentCommand = command;
            } else {
                sample.postQCCommand = command;
            }
        }
    }

    /**
     * Handle reset command button click
     * @param {HTMLElement} resetButton - The reset button element
     */
    handleResetCommand(resetButton) {
        const cell = resetButton.closest('.command-cell');
        const row = cell.closest('tr');
        const fastqName = row.querySelector('td:first-child').textContent.trim();
        const batchGroup = cell.closest('.batch-group');
        const stage = row.dataset.stage;
        const workflow = row.dataset.workflow;
        const isAutoProceed = row.hasAttribute('data-auto-proceed');

        // Find the sample data from our tracked samples
        let sample;
        if (stage === 'alignment' || (stage === 'postqc' && isAutoProceed)) {
            // For alignment or auto-proceed post-QC, look in alignment samples
            sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === fastqName);
        } else {
            sample = this.postQCSamples.find(s => s.fastq_name === fastqName);
        }

        if (!sample) {
            console.error('Sample not found:', fastqName);
            return;
        }

        // Force workflow to match the row's dataset
        sample.workflow = workflow;

        this.resetCommand(sample, stage, cell);
    }

    /**
     * Populate the modal with sample data
     */
    populateModal() {

        // Reset unknown library prep tracking
        this.unknownLibraryPrepMethodSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // Clear existing content
        this.clearModalContent();

        // Get selected samples and categorize them
        const selectedSamples = this.getSelectedSamples();

        if (selectedSamples.length === 0) {
            console.warn('[PipelineSubmitModal] No samples found to populate modal');
            return;
        }

        this.categorizeSamples(selectedSamples);

        // Populate the table with samples
        this.populateSampleTable(selectedSamples);

        // Show warning for incomplete samples
        this.showIncompleteWarning();

        // Update command lists based on selected samples
        this.updateCommandLists();

    }

    /**
     * Clear existing modal content
     */
    clearModalContent() {
        this.sampleList.innerHTML = '';
        this.incompleteList.innerHTML = '';
        this.warningDiv.classList.add('d-none');
        this.alignmentBatches.innerHTML = '';
        this.postQCBatches.innerHTML = '';
    }

    /**
     * Get selected samples from the table
     * @returns {Array} Array of sample objects
     */
    getSelectedSamples() {

        // Exclude the select-all checkbox to prevent including the header row
        const selectedRows = document.querySelectorAll('.sample-select:not(#select-all-samples):checked');

        const selectedSamples = [];

        selectedRows.forEach((checkbox, index) => {
            const row = checkbox.closest('tr');
            if (row) {

                // Helper function to safely get text content from a cell
                const getCellText = (selector) => {
                    const cell = row.querySelector(selector);
                    if (!cell) {
                        console.warn(`[PipelineSubmitModal] Cell not found for selector: ${selector} in row ${index + 1}`);
                        return '';
                    }
                    const text = cell.textContent.trim();
                    return text;
                };

                const sample = {
                    fastq_name: getCellText('td:nth-child(2)'),
                    study_set: getCellText('td:nth-child(3)'),
                    load_name: getCellText('td:nth-child(4)'),
                    batch_name_from_vendor: getCellText('td:nth-child(5)'),
                    organism_common_name: getCellText('td:nth-child(6)'),
                    library_prep_method: getCellText('td:nth-child(7)'),
                    ingest_status: getCellText('td:nth-child(8)'),
                    alignment_status: getCellText('td:nth-child(9)'),
                    postqc_status: getCellText('td:nth-child(10)')
                };

                // Validate that we have essential data
                if (!sample.fastq_name) {
                    console.error(`[PipelineSubmitModal] Sample ${index + 1} missing fastq_name, skipping`);
                    return;
                }

                // Debug log the extracted sample data

                // Pre-determine workflow and cache it on the sample object
                sample.workflow = this.determineWorkflow(sample);

                selectedSamples.push(sample);
            } else {
                console.warn(`[PipelineSubmitModal] No row found for checkbox ${index + 1}`);
            }
        });

        return selectedSamples;
    }

    /**
     * Categorize samples based on status
     * @param {Array} samples - Array of sample objects
     */
    categorizeSamples(samples) {

        // Reset sample tracking arrays
        this.alignmentSamples = [];
        this.postQCSamples = [];
        this.incompleteSamples = [];

        // Check if reprocess completed option is enabled
        const reprocessCompleted = document.getElementById('reprocess-completed-toggle')?.checked || false;

        samples.forEach((sample, index) => {
            // Categorize the sample based on status (case-insensitive comparison)
            const ingestStatus = sample.ingest_status.toLowerCase();
            const alignmentStatus = sample.alignment_status.toLowerCase();
            const postQCStatus = sample.postqc_status.toLowerCase();


            // If reprocess completed is enabled, treat all completed samples as needing alignment
            if (reprocessCompleted && ingestStatus === 'completed' && alignmentStatus === 'completed' && postQCStatus === 'completed') {
                this.alignmentSamples.push(sample);
            } else if (ingestStatus === 'not started') {
                this.incompleteSamples.push(sample);
            } else if (alignmentStatus !== 'completed') {
                this.alignmentSamples.push(sample);
            } else if (postQCStatus !== 'completed') {
                this.postQCSamples.push(sample);
            } else {
            }
        });

    }

    /**
     * Populate the sample table
     * @param {Array} samples - Array of sample objects
     */
    populateSampleTable(samples) {
        samples.forEach(sample => {
            const row = document.createElement('tr');
            row.dataset.sample = sample.fastq_name;

            // Extract values from sample data
            const fastqName = sample.fastq_name || '';
            const loadName = sample.load_name || '';
            const workflow = sample.workflow || 'RTX'; // Use cached workflow
            const organism = sample.organism_common_name || '';
            const libraryPrepMethod = sample.library_prep_method || '';
            const ingestStatus = sample.ingest_status || 'Not Started';
            const alignmentStatus = sample.alignment_status || 'Not started';
            const postQCStatus = sample.postqc_status || 'Not Started';

            row.innerHTML = `
                <td>${fastqName}</td>
                <td>${loadName}</td>
                <td>${sample.batch_name_from_vendor || ''}</td>
                <td><span class="badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span></td>
                <td>${organism}</td>
                <td>${libraryPrepMethod}</td>
                <td>${this.formatStatusBadge(ingestStatus)}</td>
                <td>${this.formatStatusBadge(alignmentStatus)}</td>
                <td>${this.formatStatusBadge(postQCStatus)}</td>
            `;
            this.sampleList.appendChild(row);
        });
    }

    /**
     * Show warning for incomplete samples
     */
    showIncompleteWarning() {
        if (this.incompleteSamples.length > 0) {
            this.warningDiv.classList.remove('d-none');
            this.incompleteSamples.forEach(sample => {
                const li = document.createElement('li');
                li.textContent = sample.fastq_name;
                this.incompleteList.appendChild(li);
            });

            // Add event listener for the checkbox
            const includeIncompleteCheckbox = document.getElementById('include-incomplete-samples');
            if (includeIncompleteCheckbox) {
                includeIncompleteCheckbox.addEventListener('change', () => {
                    this.updateCommandLists();
                });
            }
        }
    }

    /**
     * Update command lists for both alignment and post-QC
     */
    updateCommandLists() {

        // Clear existing content
        this.alignmentBatches.innerHTML = '';
        this.postQCBatches.innerHTML = '';

        const autoProceed = this.autoProceedToggle.checked;
        const includeIncomplete = document.getElementById('include-incomplete-samples')?.checked || false;


        // Group samples by batch name
        const alignmentSamples = [...this.alignmentSamples];
        if (includeIncomplete) {
            alignmentSamples.push(...this.incompleteSamples);
        }


        const alignmentBatches = this.groupSamplesByBatch(alignmentSamples);
        const postQCBatches = this.groupSamplesByBatch(this.postQCSamples);


        // Process samples for RTX unknown library preps only once
        // This combines all samples from both stages for a single pass
        const allSamplesToProcess = [...alignmentSamples];
        // Add post-QC samples that aren't in alignment
        this.postQCSamples.forEach(sample => {
            if (!allSamplesToProcess.some(s => s.fastq_name === sample.fastq_name)) {
                allSamplesToProcess.push(sample);
            }
        });

        // Process unknown library preps just once with all samples
        this.processUnknownLibraryPreps(allSamplesToProcess);

        this.renderBatchGroups(alignmentBatches, postQCBatches, autoProceed);

    }

    /**
     * Render batch groups for alignment and post-QC
     * @param {Map} alignmentBatches - Map of alignment batches
     * @param {Map} postQCBatches - Map of post-QC batches
     * @param {boolean} autoProceed - Whether to auto-proceed to post-QC
     */
    renderBatchGroups(alignmentBatches, postQCBatches, autoProceed) {

        // Render alignment batches
        if (alignmentBatches.size > 0) {
            alignmentBatches.forEach((samples, batchName) => {
                const batchGroup = this.createBatchGroup('alignment', batchName, samples, autoProceed);
                this.alignmentBatches.appendChild(batchGroup);
            });
        } else {
            this.alignmentBatches.innerHTML = '<div class="text-center text-muted">No samples eligible for alignment</div>';
        }

        // Render post-QC batches
        if (postQCBatches.size > 0) {
            postQCBatches.forEach((samples, batchName) => {
                const batchGroup = this.createBatchGroup('postqc', batchName, samples);
                this.postQCBatches.appendChild(batchGroup);
            });
        } else {
            this.postQCBatches.innerHTML = '<div class="text-center text-muted">No samples eligible for post-QC</div>';
        }

        // Remove all existing unknown library prep warnings
        document.querySelectorAll('.unknown-libprep-section').forEach(section => {
            section.remove();
        });

        // Add unknown library prep warnings only if there are samples with unknown library preps
        if (this.unknownLibraryPrepMethodSamples.alignment.size > 0 ||
            this.unknownLibraryPrepMethodSamples.postqc.size > 0) {
            this.addUnknownLibPrepWarnings();
        }

    }

    /**
     * Group samples by batch name
     * @param {Array} samples - Array of sample objects
     * @returns {Map} Map of batch name to samples
     */
    groupSamplesByBatch(samples) {
        const batches = new Map();
        samples.forEach(sample => {
            const batchName = sample.batch_name_from_vendor || 'Unnamed Batch';
            if (!batches.has(batchName)) {
                batches.set(batchName, []);
            }
            batches.get(batchName).push(sample);
        });
        return batches;
    }

    /**
     * Process samples with unknown library prep methods
     * @param {Array} samples - Array of sample objects
     */
    processUnknownLibraryPreps(samples) {
        const includeIncomplete = document.getElementById('include-incomplete-samples')?.checked || false;
        const autoProceed = document.getElementById('auto-proceed-toggle')?.checked || false;

        // Reset unknown library prep tracking
        this.unknownLibraryPrepMethodSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // Only track unknown library preps for RTX workflow
        samples.forEach(sample => {
            // Get workflow - use cached value if available
            const workflow = sample.workflow || this.determineWorkflow(sample);

            // Skip MTX samples
            if (workflow === 'MTX') {
                return; // Skip to next sample
            }

            // Only process RTX workflow samples
            if (workflow === 'RTX') {
                const libraryPrepMethod = sample.library_prep_method || '';
                const isLibraryPrepMethodKnown = this.isLibraryPrepMethodKnown(libraryPrepMethod);

                if (!isLibraryPrepMethodKnown) {
                    const isIncomplete = sample.ingest_status.toLowerCase() === 'not started';

                    // First, check alignment eligibility
                    const isEligibleForAlignment = isIncomplete ? includeIncomplete : true;

                    // Handle alignment eligibility
                    if (isEligibleForAlignment) {
                        if (!this.unknownLibraryPrepMethodSamples.alignment.has(libraryPrepMethod)) {
                            this.unknownLibraryPrepMethodSamples.alignment.set(libraryPrepMethod, []);
                        }
                        this.unknownLibraryPrepMethodSamples.alignment.get(libraryPrepMethod).push(sample);
                    }

                    // Handle post-QC eligibility separately
                    const isEligibleForPostQC =
                        // Either completed alignment and not completed post-QC
                        (sample.alignment_status.toLowerCase() === 'completed' &&
                            sample.postqc_status.toLowerCase() !== 'completed') ||
                        // Or auto-proceed is enabled and sample is eligible for alignment
                        (autoProceed && isEligibleForAlignment);

                    if (isEligibleForPostQC) {
                        if (!this.unknownLibraryPrepMethodSamples.postqc.has(libraryPrepMethod)) {
                            this.unknownLibraryPrepMethodSamples.postqc.set(libraryPrepMethod, []);
                        }
                        this.unknownLibraryPrepMethodSamples.postqc.get(libraryPrepMethod).push(sample);
                    }
                }
            }
        });
    }

    /**
     * Check if a library prep method is known
     * @param {string} libraryPrepMethod - Library prep method
     * @returns {boolean} Whether the library prep method is known
     */
    isLibraryPrepMethodKnown(libraryPrepMethod) {
        if (!libraryPrepMethod || !this.config || !this.config.workflows || !this.config.workflows.rtx) {
            return false;
        }

        const rtxConfig = this.config.workflows.rtx;

        // Function to check if a pattern matches the library prep method
        const matchesPattern = (pattern) => {
            if (pattern.includes('|')) {
                const patterns = pattern.split('|');
                return patterns.some(p => p.trim() === libraryPrepMethod);
            }
            return pattern.trim() === libraryPrepMethod;
        };

        // Check alignment patterns
        if (rtxConfig.alignment) {
            for (const pattern of Object.keys(rtxConfig.alignment)) {
                if (matchesPattern(pattern)) {
                    return true;
                }
            }
        }

        // Check post-QC patterns 
        if (rtxConfig.postqc) {
            for (const pattern of Object.keys(rtxConfig.postqc)) {
                if (matchesPattern(pattern)) {
                    return true;
                }
            }
        }

        return false;
    }

    /**
     * Get CSS class for status badge using OCS browser style
     * @param {string} status - Status text
     * @returns {string} CSS class for badge
     */
    getStatusBadgeClass(status) {
        // Always use grey for "Not started" status (equivalent to "Not completed" in OCS browser)
        if (status.toLowerCase() === 'not started') {
            return 'status-badge status-not-completed';
        }

        // Other statuses
        switch (status.toLowerCase()) {
            case 'completed':
                return 'status-badge status-completed';
            case 'running':
            case 'in progress':
                return 'status-badge status-in-progress';
            case 'failed':
                return 'status-badge status-failed';
            case 'warning':
                return 'status-badge status-pending';
            case 'pending':
            case 'submitted':
            case 'queued':
                return 'status-badge status-pending';
            case 'success':
                return 'status-badge status-completed';
            default:
                return 'status-badge status-not-completed';
        }
    }

    /**
     * Format status badge with icon using OCS browser style
     * @param {string} status - Status text
     * @returns {string} HTML for status badge
     */
    formatStatusBadge(status) {
        // Display badge mirroring the shared status_badge.html component (icon +
        // label, shared .status-badge classes). Unknown/empty -> NOT COMPLETED.
        const s = (status || '').toLowerCase().trim();
        let badgeClass, icon, label;
        if (['completed', 'complete'].includes(s)) {
            badgeClass = 'status-badge status-completed'; icon = 'bi-check-circle-fill'; label = 'COMPLETED';
        } else if (s.includes('in progress') || s === 'running') {
            badgeClass = 'status-badge status-in-progress'; icon = 'bi-arrow-clockwise';
            label = s === 'running' ? 'RUNNING' : 'IN PROGRESS';
        } else if (s.includes('error') || s.includes('fail') || s.includes('killed')) {
            badgeClass = 'status-badge status-failed'; icon = 'bi-x-circle-fill'; label = status.toUpperCase();
        } else if (s.includes('pending') || s === 'submitted' || s === 'queued') {
            badgeClass = 'status-badge status-pending'; icon = 'bi-clock-fill';
            label = s === 'submitted' ? 'SUBMITTED' : s === 'queued' ? 'QUEUED' : 'PENDING';
        } else {
            badgeClass = 'status-badge status-not-completed'; icon = 'bi-circle'; label = 'NOT COMPLETED';
        }

        return `
            <span class="${badgeClass}" title="${this.escapeHtml(status || 'Not Completed')}">
                <i class="bi ${icon}"></i>
                <span class="status-text">${label}</span>
            </span>
        `;
    }

    /**
     * HTML escape function
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }

    /**
     * Determine workflow for a sample
     * @param {Object} sample - Sample object
     * @returns {string} Workflow name
     */
    determineWorkflow(sample) {
        // Use cached result if available
        if (sample._cachedWorkflow) return sample._cachedWorkflow;

        // Check if batch name starts with MTX
        const batchName = (sample.batch_name_from_vendor || '').toUpperCase();
        const result = batchName.startsWith('MTX') ? 'MTX' : 'RTX';

        // Cache result and return
        sample._cachedWorkflow = result;
        return result;
    }

    /**
     * Check if a sample uses MTX workflow
     * @param {Object} sample - Sample object
     * @returns {boolean} Whether the sample uses MTX workflow
     */
    isMtxWorkflow(sample) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample);
        return workflow === 'MTX';
    }

    /**
     * Check if a sample uses RTX workflow
     * @param {Object} sample - Sample object
     * @returns {boolean} Whether the sample uses RTX workflow
     */
    isRtxWorkflow(sample) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample);
        return workflow === 'RTX';
    }

    createBatchGroup(stage, batchName, samples, showAutoProceed = false) {
        const batchGroup = document.createElement('div');
        batchGroup.className = 'batch-group';
        batchGroup.dataset.batchName = batchName;
        batchGroup.dataset.stage = stage;

        // Create batch header
        const header = document.createElement('div');
        header.className = 'batch-header';
        header.innerHTML = `
            <span class="batch-name">${batchName}</span>
            <button class="btn btn-sm btn-outline-secondary toggle-batch">
                <i class="bi bi-chevron-down"></i> Show/Hide
            </button>
        `;

        // Create batch content
        const content = document.createElement('div');
        content.className = 'batch-content';
        content.style.display = 'none';

        // Create table
        const table = document.createElement('table');
        table.className = 'batch-table';
        table.innerHTML = `
            <thead>
                <tr>
                    <th>Fastq Name</th>
                    <th>Workflow</th>
                    <th>Command</th>
                </tr>
            </thead>
            <tbody>
                ${samples.map(sample => this.createSampleRow(sample, stage)).join('')}
            </tbody>
        `;

        content.appendChild(table);

        // Add auto-proceed section if needed
        if (showAutoProceed && stage === 'alignment') {
            const autoProceedSection = document.createElement('div');
            autoProceedSection.className = 'auto-proceed-section';
            autoProceedSection.innerHTML = `
                <div class="auto-proceed-badge">Auto-proceed to Post-QC</div>
                <table class="batch-table">
                    <thead>
                        <tr>
                            <th>Fastq Name</th>
                            <th>Workflow</th>
                            <th>Post-QC Command</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${samples.map(sample => this.createSampleRow(sample, 'postqc', true)).join('')}
                    </tbody>
                </table>
            `;
            content.appendChild(autoProceedSection);
        }

        batchGroup.appendChild(header);
        batchGroup.appendChild(content);

        // Add event listeners
        const toggleBtn = header.querySelector('.toggle-batch');
        toggleBtn.addEventListener('click', () => {
            const isHidden = content.style.display === 'none';
            content.style.display = isHidden ? 'block' : 'none';
            toggleBtn.querySelector('i').className = isHidden ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
        });

        return batchGroup;
    }

    createSampleRow(sample, stage, isAutoProceed = false) {
        // Determine workflow
        const workflow = this.determineWorkflow(sample);
        // Store workflow directly on the sample for later reference
        sample.workflow = workflow;

        const command = stage === 'alignment' ?
            this.generateAlignmentCommand(sample) :
            this.generatePostQCCommand(sample);

        // Add data-auto-proceed attribute if this is part of auto-proceed
        const autoProceedAttr = isAutoProceed ? 'data-auto-proceed="true"' : '';

        return `
            <tr data-sample="${sample.fastq_name}" data-stage="${stage}" data-workflow="${workflow}" ${autoProceedAttr}>
                <td>${sample.fastq_name}</td>
                <td><span class="badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span></td>
                <td class="command-cell">
                    <code>${command}</code>
                    <div class="command-actions">
                        <button class="btn btn-sm btn-outline-secondary reset-command">
                            <i class="bi bi-arrow-counterclockwise"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-primary edit-command">
                            <i class="bi bi-pencil-square"></i>
                        </button>
                    </div>
                    ${this.createCommandEditForm(sample, stage, command)}
                </td>
            </tr>
        `;
    }

    /**
     * Create the edit form for the command
     * @param {Object} sample - The sample object
     * @param {string} stage - The pipeline stage
     * @param {string} command - The command
     * @returns {string} HTML for the edit form
     */
    createCommandEditForm(sample, stage, command) {
        console.log('Creating command edit form for:', {
            sample: sample ? {
                fastqName: sample.fastq_name,
                loadName: sample.load_name,
                workflow: sample.workflow, // Use workflow directly, don't try to determine it
                libraryPrepMethod: sample.library_prep_method
            } : 'No sample',
            stage,
            command
        });

        // Parse the command to extract current values
        const currentValues = this.parseCommand(command);

        // Check if this is post-QC stage
        const isPostQC = stage === 'postqc';

        // Get asset tag from parsed values, from sample object, or directly from command
        let assetTag = '';
        if (isPostQC) {
            // Priority 1: Try to get from parsed values
            if (currentValues.assetTag) {
                assetTag = currentValues.assetTag;
            }
            // Priority 2: Try to get from sample object
            else if (sample.assetTag) {
                assetTag = sample.assetTag;
            }
            // Priority 3: Try to extract directly from command
            else {
                const assetTagMatch = command.match(/--asset-tag\s+([^\s"]+)/);
                if (assetTagMatch) {
                    assetTag = assetTagMatch[1];
                }
            }
        }

        // Create the form HTML
        const formHtml = `
            <div class="command-edit-form">
                <div class="mb-3">
                    <label class="form-label">Base Command</label>
                    <input type="text" class="form-control command-input" value="${currentValues.baseCommand || ''}" data-workflow="${sample.workflow}" style="font-family: monospace;">
                </div>
                ${isPostQC ? `
                    <div class="mb-3">
                        <label class="form-label">Asset Tag</label>
                        <input type="text" class="form-control asset-tag-input" value="${assetTag}" placeholder="e.g., 25.03.27">
                        <div class="form-text">Leave empty for no asset tag</div>
                    </div>
                ` : ''}
                ${stage === 'alignment' ? `
                    <div class="mb-3">
                        <label class="form-label">Reference</label>
                        <select class="form-select reference-select">
                            ${this.getReferences().map(ref =>
            `<option value="${ref.value}" ${ref.value === currentValues.reference ? 'selected' : ''}>
                                    ${ref.name}
                                </option>`
        ).join('')}
                        </select>
                    </div>
                        <div class="mb-3">
                            <label class="form-label">Chemistry</label>
                            <select class="form-select chemistry-select">
                                ${this.getChemistries().map(chem =>
            `<option value="${chem.value}" ${chem.value === currentValues.chemistry ? 'selected' : ''}>
                                        ${chem.name}
                                    </option>`
        ).join('')}
                            </select>
                        </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input include-introns" type="checkbox" id="include-introns-${sample.fastq_name}" 
                                ${currentValues.includeIntrons ? 'checked' : ''}>
                            <label class="form-check-label" for="include-introns-${sample.fastq_name}">
                                Include introns
                            </label>
                        </div>
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input execution-priority" type="checkbox" id="execution-priority-${sample.fastq_name}"
                                ${currentValues.executionPriority ? 'checked' : ''}>
                            <label class="form-check-label" for="execution-priority-${sample.fastq_name}">
                                High execution priority
                            </label>
                        </div>
                        </div>
                    ` : ''}
                <div class="d-flex justify-content-end gap-2">
                    <button type="button" class="btn btn-secondary cancel-edit">Cancel</button>
                    <button type="button" class="btn btn-primary save-command">Save</button>
                </div>
            </div>
        `;

        return formHtml;
    }

    parseCommand(command) {
        const values = {};

        if (!command) {
            return values;
        }

        // Extract the base command up to the first -- flag
        const commandParts = command.split(/\s+--/);
        values.baseCommand = commandParts[0];

        // Add back the asset-name part if it exists in the original command
        const assetNameMatch = command.match(/--asset-name\s+([^\s"]+)/);
        if (assetNameMatch) {
            values.baseCommand += ` --asset-name ${assetNameMatch[1]}`;
        }

        // Extract asset tag - try both patterns (with quotes and without)
        const assetTagMatch = command.match(/--asset-tag\s+([^\s"]+)/) || command.match(/--asset-tag\s+"([^"]+)"/);
        if (assetTagMatch) {
            values.assetTag = assetTagMatch[1];
        }


        // Extract reference
        const referenceMatch = command.match(/--reference-names\s+"([^"]+)"/);
        if (referenceMatch) {
            values.reference = referenceMatch[1];
        }

        // Extract cellranger-addopts
        const cellrangerAddoptsMatch = command.match(/--cellranger-addopts\s+["']([^"']+)["']/);
        if (cellrangerAddoptsMatch) {
            const addopts = cellrangerAddoptsMatch[1];

            // Extract chemistry from addopts
            const chemistryMatch = addopts.match(/--chemistry\s+([^\s"']+)/);
            if (chemistryMatch) {
                values.chemistry = chemistryMatch[1];
            }

            // Check for include-introns in addopts
            values.includeIntrons = addopts.includes('--include-introns');
        }

        // Also check for include-introns directly in command
        if (!values.hasOwnProperty('includeIntrons')) {
            values.includeIntrons = command.includes('--include-introns');
        }

        // Check for execution priority
        values.executionPriority = command.includes('--execution-priority HIGH');

        return values;
    }

    generateCommandFromTemplate(template, sample) {
        if (!template) return '';

        const reference = this.getReference(sample.organism_common_name || '');
        const libraryPrep = sample.library_prep_method || '';
        const chemistry = this.getChemistry(libraryPrep);
        const notificationEmail = this.getNotificationEmail();
        const loadName = sample.load_name || '';

        // Determine workflow for asset name/tag lookup
        const workflow = sample.workflow || this.determineWorkflow(sample);

        // Get asset name and tag if available in the config
        const workflowLower = workflow.toLowerCase();
        const assetName = this.getAssetName(workflow, sample.stage || (template.includes('postalign') || template.includes('postqc') ? 'postqc' : 'alignment'), libraryPrep);

        // If the sample already has an asset tag set (for unknown library preps), use that
        // Otherwise, get it from the config
        const assetTag = sample.assetTag || this.getAssetTag(workflow, sample.stage || (template.includes('postalign') || template.includes('postqc') ? 'postqc' : 'alignment'), libraryPrep);

        // Replace known placeholders
        let command = template
            .replace(/{load_name}/g, loadName)
            .replace(/{reference}/g, reference)
            .replace(/{notification_email}/g, notificationEmail);

        // Handle chemistry placeholder specially
        if (command.includes('{chemistry}')) {
            if (chemistry) {
                command = command.replace(/{chemistry}/g, chemistry);
            } else {
                console.warn(`No chemistry found for library prep: ${libraryPrep}`);
                // Try to get a default chemistry from config
                const defaultChemistry = Object.values(this.config?.chemistries || {})[0];
                if (defaultChemistry) {
                    command = command.replace(/{chemistry}/g, defaultChemistry);
                } else {
                    // If no chemistry available, remove the chemistry parameter entirely
                    command = command.replace(/--chemistry\s+{chemistry}/g, '');
                }
            }
        }

        // Handle asset tag
        if (assetTag && assetTag !== 'latest') {
            if (command.includes('--asset-tag')) {
                // Replace existing asset tag
                command = command.replace(/--asset-tag\s+([^\s"]+)/, `--asset-tag ${assetTag}`);
            } else if (!command.includes('--asset-tag')) {
                // Add asset tag after asset-name parameter if not already present
                command = command.replace(/--asset-name\s+(\S+)/, `--asset-name $1 --asset-tag ${assetTag}`);
            }
        }

        // Log the generated command
        return command;
    }

    generateAlignmentCommand(sample) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const libraryPrepMethod = sample.library_prep_method || '';

        console.log('Generating alignment command for:', {
            sample: sample.fastq_name,
            workflow,
            libraryPrepMethod
        });

        // Check if this is an unknown library prep method
        if (this.isRtxWorkflow(sample) && !this.isLibraryPrepMethodKnown(libraryPrepMethod)) {
            return '';
        }

        const commandTemplate = this.getCommandTemplate(workflow, 'alignment', libraryPrepMethod);
        console.log('Got command template:', {
            workflow,
            stage: 'alignment',
            template: commandTemplate
        });

        if (!commandTemplate) {
            console.error(`No command template found for ${workflow} alignment with library prep method ${libraryPrepMethod}`);
            return '';
        }

        const command = this.generateCommandFromTemplate(commandTemplate, sample);
        return command;
    }

    generatePostQCCommand(sample) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const libraryPrepMethod = sample.library_prep_method || '';

        console.log('Generating post-QC command for:', {
            sample: sample.fastq_name,
            workflow,
            libraryPrepMethod
        });

        // Check if this is an unknown library prep method
        if (this.isRtxWorkflow(sample) && !this.isLibraryPrepMethodKnown(libraryPrepMethod)) {
            return '';
        }

        const commandTemplate = this.getCommandTemplate(workflow, 'postqc', libraryPrepMethod);
        console.log('Got command template:', {
            workflow,
            stage: 'postqc',
            template: commandTemplate
        });

        if (!commandTemplate) {
            console.error(`No command template found for ${workflow} post-QC with library prep method ${libraryPrepMethod}`);
            return '';
        }

        const command = this.generateCommandFromTemplate(commandTemplate, sample);
        return command;
    }

    handleSubmission() {
        this.saveState();

        // Collect all commands
        const commands = [];
        const autoToggle = this.autoProceedToggle.checked;

        // First, create a map of samples that should have auto-toggle enabled
        const autoToggleSamples = new Map();

        // Process alignment commands first to determine which samples should auto-proceed
        const alignmentBatchGroups = this.alignmentBatches.querySelectorAll('.batch-group');
        alignmentBatchGroups.forEach(batchGroup => {
            const batchName = batchGroup.dataset.batchName || '';
            const cells = batchGroup.querySelectorAll('tr[data-sample]');
            cells.forEach(row => {
                const sampleId = row.dataset.sample;
                const workflow = row.dataset.workflow; // Get workflow directly from row
                let command = row.querySelector('.command-cell code')?.textContent?.trim();
                if (!command) {
                    const commandInput = row.querySelector('.command-edit-form textarea[name="command"]');
                    if (commandInput) {
                        command = commandInput.value.trim();
                    }
                }
                if (command && sampleId) {
                    let sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleId);
                    if (!sample) sample = { batch_name_from_vendor: '', workflow: workflow, fastq_name: sampleId, alignment_status: '' };
                    // Use the workflow from the row dataset
                    // Detect if this is a post-QC command
                    const isPostQC = /\bpostalign\b|\bpostqc\b/.test(command);

                    // Set autoToggle based on alignment status and auto-proceed toggle
                    const shouldAutoToggle = autoToggle && sample.alignment_status &&
                        sample.alignment_status.trim().toLowerCase() !== 'completed';

                    if (shouldAutoToggle) {
                        autoToggleSamples.set(sampleId, true);
                    }

                    commands.push({
                        fastq_name: sample.fastq_name,
                        command,
                        alignment: !isPostQC,
                        postqc: isPostQC,
                        autoToggle: shouldAutoToggle,
                        batch_name_from_vendor: sample.batch_name_from_vendor || '',
                        workflow: workflow ? workflow.toLowerCase() : ''
                    });
                }
            });
        });

        // Post-QC commands
        const postQCBatchGroups = this.postQCBatches.querySelectorAll('.batch-group');
        postQCBatchGroups.forEach(batchGroup => {
            const batchName = batchGroup.dataset.batchName || '';
            const cells = batchGroup.querySelectorAll('tr[data-sample]');
            cells.forEach(row => {
                const sampleId = row.dataset.sample;
                const workflow = row.dataset.workflow; // Get workflow directly from row
                let command = row.querySelector('.command-cell code')?.textContent?.trim();
                if (!command) {
                    const commandInput = row.querySelector('.command-edit-form textarea[name="command"]');
                    if (commandInput) {
                        command = commandInput.value.trim();
                    }
                }
                if (!command) {
                    const generatedCommand = row.querySelector('.generated-command')?.textContent?.trim();
                    if (generatedCommand) {
                        command = generatedCommand;
                    }
                }
                if (command && sampleId) {
                    let sample = this.postQCSamples.find(s => s.fastq_name === sampleId);
                    if (!sample) sample = { batch_name_from_vendor: '', workflow: workflow, fastq_name: sampleId };
                    // Use the workflow from the row dataset

                    // Use the autoToggleSamples map to determine if this sample should auto-proceed
                    const shouldAutoToggle = autoToggleSamples.has(sampleId);

                    commands.push({
                        fastq_name: sample.fastq_name,
                        command,
                        alignment: false,
                        postqc: true,
                        autoToggle: shouldAutoToggle,
                        batch_name_from_vendor: sample.batch_name_from_vendor || '',
                        workflow: workflow ? workflow.toLowerCase() : ''
                    });
                }
            });
        });

        // Log the new storage data structure

        // Dispatch event for modal manager to handle transition
        document.dispatchEvent(new CustomEvent('pipelineSubmitComplete', {
            detail: { commands }
        }));
    }

    handleFinalExecution(commands) {
        // Show processing state
        this.confirmButton.disabled = true;
        this.confirmButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';

        // Reset button state after a short delay
        setTimeout(() => {
            // Reset button state
            this.confirmButton.disabled = false;
            this.confirmButton.innerHTML = 'Confirm and Submit';

            // Note: Sample clearing is now handled by the final modal after API confirmation
        }, 1000);
    }

    addUnknownLibPrepWarnings() {
        // Create warning sections for both alignment and postqc in correct order
        const stages = ['alignment', 'postqc'];

        // Find the notification email card
        const notificationCard = document.querySelector('.card.mb-4');
        if (!notificationCard) {
            console.error('Could not find notification email card');
            return;
        }

        // Process stages in order
        stages.forEach(stage => {
            const unknownSamples = this.unknownLibraryPrepMethodSamples[stage];
            if (unknownSamples.size > 0) {
                const warningSection = document.createElement('div');
                warningSection.className = 'unknown-libprep-section';
                warningSection.dataset.stage = stage; // Add data attribute to identify the stage
                warningSection.innerHTML = `
                    <div class="unknown-libprep-header">
                        <div class="d-flex align-items-center gap-2">
                            <i class="bi bi-exclamation-triangle-fill text-warning"></i>
                            <h5 class="mb-0">Unknown Library Prep Methods for ${stage === 'alignment' ? 'Alignment' : 'Post-QC'}</h5>
                        </div>
                        <p class="text-muted mb-0">Please select an asset name for each group to proceed with submission</p>
                    </div>
                    <div class="unknown-libprep-container">
                        ${Array.from(unknownSamples.entries()).map(([libraryPrepMethod, samples]) => {
                    // Determine workflow from the first sample (should be the same for all samples with same library prep)
                    const workflow = samples.length > 0 ? (samples[0].workflow || 'RTX') : 'RTX';
                    return `
                            <div class="unknown-libprep-card" data-library-prep-method="${libraryPrepMethod}" data-stage="${stage}" data-workflow="${workflow}">
                                <div class="unknown-libprep-card-header">
                                    <div class="d-flex align-items-center gap-2">
                                        <span class="badge bg-warning text-dark">${libraryPrepMethod}</span>
                                        <span class="text-muted">(${samples.length} sample${samples.length !== 1 ? 's' : ''})</span>
                                        <span class="badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span>
                                    </div>
                                </div>
                                <div class="unknown-libprep-card-body">
                                    <div class="asset-selector-container">
                                        ${this.createAssetSelector(stage, libraryPrepMethod, workflow)}
                                    </div>
                                    <div class="samples-list">
                                        <div class="samples-header">
                                            <i class="bi bi-list-ul"></i>
                                            <span>Affected Samples</span>
                                        </div>
                                        <div class="samples-content">
                                            ${samples.map(s => `
                                                <div class="sample-item">
                                                    <i class="bi bi-file-earmark-text"></i>
                                                    <span>${s.fastq_name}</span>
                                                </div>
                                            `).join('')}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `}).join('')}
                    </div>
                `;

                // Remove any existing warning section for this stage
                const existingWarning = document.querySelector(`.unknown-libprep-section[data-stage="${stage}"]`);
                if (existingWarning) {
                    existingWarning.remove();
                }

                // Find the correct insertion point
                // For alignment, insert after notification card
                // For postqc, insert after alignment warning if it exists, otherwise after notification card
                let insertAfterElement = stage === 'alignment' ?
                    notificationCard :
                    document.querySelector('.unknown-libprep-section[data-stage="alignment"]') || notificationCard;

                // Insert the warning section
                insertAfterElement.insertAdjacentElement('afterend', warningSection);

                // Add event listeners for asset selectors
                warningSection.querySelectorAll('.asset-selector').forEach(selector => {
                    selector.addEventListener('change', (event) => {
                        const libraryPrepCard = event.target.closest('.unknown-libprep-card');
                        const libraryPrepMethod = libraryPrepCard.dataset.libraryPrepMethod;
                        const stage = libraryPrepCard.dataset.stage;
                        const workflow = libraryPrepCard.dataset.workflow || 'RTX';
                        const selectedAsset = event.target.value;


                        // Show additional options when an asset is selected
                        const cardBody = libraryPrepCard.querySelector('.unknown-libprep-card-body');
                        const existingOptions = cardBody.querySelector('.additional-options');
                        if (existingOptions) {
                            existingOptions.remove();
                        }

                        if ((stage === 'alignment' && selectedAsset === 'cellranger-rnaseq') ||
                            (stage === 'postqc' && selectedAsset === 'tenx_rnaseq_qc')) {
                            const additionalOptions = document.createElement('div');
                            additionalOptions.className = 'additional-options mt-3';
                            additionalOptions.innerHTML = `
                                <div class="card">
                                    <div class="card-body">
                                        <h6 class="card-title">Additional Configuration</h6>
                                        
                                        <div class="mb-3">
                                            <label class="form-label">Asset Tag (Optional)</label>
                                            <input type="text" class="form-control asset-tag-input" 
                                                placeholder="${stage === 'postqc' ? 'e.g., 25.03.27' : 'e.g., 8.0.1'}"
                                                value="${stage === 'postqc' ? '25.03.27' : ''}">
                                            <div class="form-text">Leave empty for no asset tag</div>
                                        </div>

                                        ${stage === 'alignment' ? `
                                        <div class="mb-3">
                                            <label class="form-label">Command Template</label>
                                            <div class="form-check">
                                                <input class="form-check-input" type="radio" name="template-${libraryPrepMethod}" id="template1-${libraryPrepMethod}" value="standard" checked>
                                                <label class="form-check-label" for="template1-${libraryPrepMethod}">
                                                    Standard (with --include-introns)
                                                    <div class="form-text">Uses --cellranger-addopts "--chemistry {chemistry} --include-introns"</div>
                                                </label>
                                            </div>
                                            <div class="form-check mt-2">
                                                <input class="form-check-input" type="radio" name="template-${libraryPrepMethod}" id="template2-${libraryPrepMethod}" value="no-introns">
                                                <label class="form-check-label" for="template2-${libraryPrepMethod}">
                                                    Without --include-introns
                                                    <div class="form-text">Uses --cellranger-addopts "--chemistry {chemistry}"</div>
                                                </label>
                                            </div>
                                        </div>
                                        ` : ''}
                                    </div>
                                </div>
                            `;
                            cardBody.appendChild(additionalOptions);

                            // Add immediate update handler for asset tag input changes
                            const assetTagInput = additionalOptions.querySelector('.asset-tag-input');
                            if (assetTagInput) {
                                assetTagInput.addEventListener('input', () => {
                                    this.updateUnknownLibPrepCommands(stage, libraryPrepMethod, selectedAsset);
                                });
                            }
                        }

                        // Update commands for all affected samples
                        this.updateUnknownLibPrepCommands(stage, libraryPrepMethod, selectedAsset);
                    });
                });

                // Add event listeners for asset tag and template changes
                warningSection.addEventListener('change', (event) => {
                    if (event.target.matches('.asset-tag-input') ||
                        event.target.matches('input[type="radio"]')) {
                        const libraryPrepCard = event.target.closest('.unknown-libprep-card');
                        const libraryPrepMethod = libraryPrepCard.dataset.libraryPrepMethod;
                        const stage = libraryPrepCard.dataset.stage;
                        const selectedAsset = libraryPrepCard.querySelector('.asset-selector').value;

                        this.updateUnknownLibPrepCommands(stage, libraryPrepMethod, selectedAsset);
                    }
                });
            }
        });
    }

    createAssetSelector(stage, libraryPrepMethod, workflow = 'RTX') {
        const assets = this.getAvailableAssets(stage, workflow);

        // Return the HTML string directly instead of creating a DOM element
        return `
            <div class="mb-3">
                <label class="form-label">Select Asset Name:</label>
                <select class="form-select asset-selector">
                    <option value="">Select an asset...</option>
                    ${assets.map(asset => `<option value="${asset}">${asset}</option>`).join('')}
                </select>
            </div>
        `;
    }

    getAvailableAssets(stage, workflow = '') {
        const assets = new Set();

        // Default to both workflows if none specified
        const workflowLower = workflow.toLowerCase() || '';

        try {
            // Check RTX workflow config if no specific workflow is provided or RTX is requested
            if ((workflowLower === '' || workflowLower === 'rtx') && this.config?.workflows?.rtx?.[stage]) {
                const rtxConfig = this.config.workflows.rtx[stage];

                // Extract unique asset names from the RTX config
                for (const [pattern, config] of Object.entries(rtxConfig)) {
                    if (config && typeof config === 'object' && config.asset_name) {
                        assets.add(config.asset_name);
                    }
                }
            }

            // Check MTX workflow config if no specific workflow is provided or MTX is requested
            if ((workflowLower === '' || workflowLower === 'mtx') && this.config?.workflows?.mtx?.[stage]) {
                const mtxConfig = this.config.workflows.mtx[stage];

                // For direct asset_name in the config
                if (typeof mtxConfig === 'object' && mtxConfig.asset_name) {
                    assets.add(mtxConfig.asset_name);
                }
            }

            // Sort assets alphabetically for consistent display
            const sortedAssets = Array.from(assets).sort();
            return sortedAssets;
        } catch (error) {
            console.error('Error getting assets from config:', error);
            return [];
        }
    }

    // Add this method to store original commands when generated
    storeOriginalCommand(sample, stage, command) {
        if (!sample.originalCommands) {
            sample.originalCommands = {};
        }
        sample.originalCommands[stage] = command;
    }

    updateUnknownLibPrepCommands(stage, libraryPrepMethod, selectedAsset) {

        // Get the container for this library prep method
        const container = this.modal.querySelector(`.unknown-libprep-card[data-stage="${stage}"][data-library-prep-method="${libraryPrepMethod}"]`);
        if (!container) {
            console.error(`Could not find container for ${stage} ${libraryPrepMethod}`);
            return;
        }

        // Get the workflow from the container
        const workflow = container.dataset.workflow || 'RTX';

        // Get the asset tag input value
        const assetTagInput = container.querySelector('.asset-tag-input');
        const assetTag = assetTagInput ? assetTagInput.value.trim() : '';

        // Get all affected samples
        const affectedSamples = this.unknownLibraryPrepMethodSamples[stage].get(libraryPrepMethod) || [];

        // If no asset is selected, clear commands for all affected samples
        if (!selectedAsset) {
            affectedSamples.forEach(sample => {
                const rowSelector = `tr[data-sample="${sample.fastq_name}"][data-stage="${stage}"]`;
                const row = this.modal.querySelector(rowSelector);
                if (!row) {
                    console.error(`Could not find row for sample ${sample.fastq_name}`);
                    return;
                }
                const commandCell = row.querySelector('.command-cell code');
                if (commandCell) {
                    commandCell.textContent = '';
                } else {
                    console.error(`Could not find command cell for sample ${sample.fastq_name}`);
                }
            });
            return;
        }

        // Use the workflow from the card, already normalized to lowercase
        const workflowLower = workflow.toLowerCase();

        // Create a temporary command template based on the selected asset
        let commandTemplate = '';
        let assetTagToUse = assetTag;

        // For alignment stage
        if (stage === 'alignment') {
            // Check if we have a template in the config
            if (this.config?.workflows?.[workflowLower]?.[stage]) {
                const workflowConfig = this.config.workflows[workflowLower][stage];

                // For direct command_template (like in MTX)
                if (workflowConfig.asset_name === selectedAsset) {
                    commandTemplate = workflowConfig.command_template;
                    // Use asset tag from config if available and not explicitly set by user
                    if (!assetTagToUse && workflowConfig.asset_tag && workflowConfig.asset_tag !== 'latest') {
                        assetTagToUse = workflowConfig.asset_tag;
                    }
                }
                // For pattern-based configs (like in RTX)
                else if (!workflowConfig.command_template) {
                    // Try to find a template matching the selected asset
                    for (const [pattern, config] of Object.entries(workflowConfig)) {
                        if (config.asset_name === selectedAsset) {
                            commandTemplate = config.command_template;
                            // Use asset tag from config if available and not explicitly set by user
                            if (!assetTagToUse && config.asset_tag && config.asset_tag !== 'latest') {
                                assetTagToUse = config.asset_tag;
                            }
                            break;
                        }
                    }
                }
            }

            // If no template was found, create a basic one based on the workflow and asset
            if (!commandTemplate) {
                const templateType = workflowLower === 'mtx' ? 'tenx-arc' : 'tenx-rnaseq';
                // Create command template with asset tag if provided
                if (assetTagToUse) {
                    commandTemplate = `ocs fastqs align ${templateType} --asset-name ${selectedAsset} --asset-tag ${assetTagToUse} --reference-names "{reference}" --load-names "{load_name}" --notify-on FAILED --notify {notification_email}`;
                } else {
                    commandTemplate = `ocs fastqs align ${templateType} --asset-name ${selectedAsset} --reference-names "{reference}" --load-names "{load_name}" --notify-on FAILED --notify {notification_email}`;
                }
            } else if (assetTagToUse && !commandTemplate.includes('--asset-tag')) {
                // Add asset tag to existing template if not already present
                commandTemplate = commandTemplate.replace(/--asset-name\s+([^\s]+)/, `--asset-name $1 --asset-tag ${assetTagToUse}`);
            }
        }
        // For postqc stage
        else if (stage === 'postqc') {
            // Check if we have a template in the config
            if (this.config?.workflows?.[workflowLower]?.[stage]) {
                const workflowConfig = this.config.workflows[workflowLower][stage];

                // For direct command_template (like in MTX)
                if (workflowConfig.asset_name === selectedAsset) {
                    commandTemplate = workflowConfig.command_template;
                    // Use asset tag from config if available and not explicitly set by user
                    if (!assetTagToUse && workflowConfig.asset_tag && workflowConfig.asset_tag !== 'latest') {
                        assetTagToUse = workflowConfig.asset_tag;
                    }
                }
                // For pattern-based configs (like in RTX)
                else if (!workflowConfig.command_template) {
                    // Try to find a template matching the selected asset
                    for (const [pattern, config] of Object.entries(workflowConfig)) {
                        if (config.asset_name === selectedAsset) {
                            commandTemplate = config.command_template;
                            // Use asset tag from config if available and not explicitly set by user
                            if (!assetTagToUse && config.asset_tag && config.asset_tag !== 'latest') {
                                assetTagToUse = config.asset_tag;
                            }
                            break;
                        }
                    }
                }
            }

            // If no template was found, create a basic one based on the workflow and asset
            if (!commandTemplate) {
                const templateType = workflowLower === 'mtx' ? 'tenx-arc' : 'tenx-rnaseq';
                // Create command template with asset tag if provided
                if (assetTagToUse) {
                    commandTemplate = `ocs fastqs postalign ${templateType} --asset-name ${selectedAsset} --asset-tag ${assetTagToUse} --load-names "{load_name}" --notify-on FAILED --notify {notification_email}`;
                } else {
                    commandTemplate = `ocs fastqs postalign ${templateType} --asset-name ${selectedAsset} --load-names "{load_name}" --notify-on FAILED --notify {notification_email}`;
                }
            } else if (assetTagToUse && !commandTemplate.includes('--asset-tag')) {
                // Add asset tag to existing template if not already present
                commandTemplate = commandTemplate.replace(/--asset-name\s+([^\s]+)/, `--asset-name $1 --asset-tag ${assetTagToUse}`);
            } else if (assetTagToUse && commandTemplate.includes('--asset-tag')) {
                // Update existing asset tag in the template
                commandTemplate = commandTemplate.replace(/--asset-tag\s+([^\s]+)/, `--asset-tag ${assetTagToUse}`);
            }
        }


        if (!commandTemplate) {
            console.error(`No command template could be created for ${workflow} ${stage} with asset ${selectedAsset}`);
            return;
        }

        // Check if we need to handle additional template options for alignment
        if (stage === 'alignment' && workflowLower === 'rtx') {
            const templateRadios = container.querySelectorAll('input[type="radio"][name^="template-"]');
            if (templateRadios.length > 0) {
                let selectedTemplate = '';
                templateRadios.forEach(radio => {
                    if (radio.checked) {
                        selectedTemplate = radio.value;
                    }
                });

                // Modify the command template based on template selection
                if (selectedTemplate === 'standard') {
                    // Ensure the include-introns flag is present
                    if (!commandTemplate.includes('--include-introns')) {
                        commandTemplate = commandTemplate.replace(/--chemistry {chemistry}/g, '--chemistry {chemistry} --include-introns');
                    }
                } else if (selectedTemplate === 'no-introns') {
                    // Remove the include-introns flag
                    commandTemplate = commandTemplate.replace(/\s*--include-introns/g, '');
                }
            }
        }

        // Update command for each affected sample
        affectedSamples.forEach(sample => {
            const rowSelector = `tr[data-sample="${sample.fastq_name}"][data-stage="${stage}"]`;
            const row = this.modal.querySelector(rowSelector);
            if (!row) {
                console.error(`Could not find row for sample ${sample.fastq_name}`);
                return;
            }
            const commandCell = row.querySelector('.command-cell code');
            if (!commandCell) {
                console.error(`Could not find command cell for sample ${sample.fastq_name}`);
                return;
            }

            // Add the stage to the sample for asset tag lookup
            sample.stage = stage;
            // Ensure the workflow is set correctly
            sample.workflow = workflow;
            // Store the asset tag in the sample for future reference
            sample.assetTag = assetTagToUse;

            // Generate command from template
            const command = this.generateCommandFromTemplate(commandTemplate, sample);
            commandCell.textContent = command;

            // Store the command in the sample object
            if (stage === 'alignment') {
                sample.alignmentCommand = command;
                // Store the original command for reset functionality
                this.storeOriginalCommand(sample, 'alignment', command);
            } else {
                sample.postQCCommand = command;
                // Store the original command for reset functionality
                this.storeOriginalCommand(sample, 'postqc', command);
            }
        });
    }

    updateAllCommandsWithEmail() {
        const email = this.globalNotificationEmail.value.trim();

        // Update all command cells
        const commandCells = this.modal.querySelectorAll('.command-cell');
        commandCells.forEach(cell => {
            const codeElement = cell.querySelector('code');
            if (codeElement) {
                let command = codeElement.textContent;
                // Replace existing email or add new one
                if (command.includes('--notify ')) {
                    command = command.replace(/--notify\s+[^\s]+/, `--notify ${email}`);
                } else {
                    command += ` --notify ${email}`;
                }
                codeElement.textContent = command;
            }
        });

        // Update stored commands in samples
        [...this.alignmentSamples, ...this.postQCSamples, ...this.incompleteSamples].forEach(sample => {
            if (sample.alignmentCommand) {
                sample.alignmentCommand = sample.alignmentCommand.replace(/--notify\s+[^\s]+/, `--notify ${email}`);
            }
            if (sample.postQCCommand) {
                sample.postQCCommand = sample.postQCCommand.replace(/--notify\s+[^\s]+/, `--notify ${email}`);
            }
        });
    }

    /**
     * Build a command from components
     * @param {string} baseCommand - Base command
     * @param {Object} sample - Sample object
     * @param {Object} options - Options
     * @returns {string} Built command
     */
    buildCommand(baseCommand, sample, options = {}) {
        const {
            reference = '',
            chemistry = '',
            includeIntrons = false,
            executionPriority = false,
            assetTag = '',
            isAlignment = false,
            assetName = '',
            preserveBaseCommand = false
        } = options;


        // Start with the base command
        let command = preserveBaseCommand ? baseCommand : `${baseCommand.split('--asset-name')[0].trim()} --asset-name ${assetName}`;

        // First, remove any existing asset tag in the command (we'll add it back if needed)
        command = command.replace(/--asset-tag\s+[^\s"']+/g, '').trim();

        // Add reference only for alignment commands
        if (reference && isAlignment) {
            command += ` --reference-names "${reference}"`;
        }

        // Add load name
        command += ` --load-names "${sample.load_name}"`;

        // Add asset tag if provided
        if (assetTag) {
            command += ` --asset-tag ${assetTag}`;
        }

        // Add chemistry and include-introns for alignment
        if (isAlignment) {
            // Only add cellranger-addopts if chemistry is selected or include-introns is checked
            if (chemistry || includeIntrons) {
                let addopts = '';
                if (chemistry) {
                    addopts += `--chemistry ${chemistry}`;
                }
                if (includeIntrons) {
                    addopts += (addopts ? ' ' : '') + '--include-introns';
                }
                if (addopts) {
                    command += ` --cellranger-addopts "${addopts}"`;
                }
            }

            // Add execution priority if checked
            if (executionPriority) {
                command += ' --execution-priority HIGH';
            }
        }

        // Add notification settings
        command += ' --notify-on FAILED';
        const email = this.getNotificationEmail();
        if (email) {
            command += ` --notify ${email}`;
        }

        return command;
    }

    /**
     * Update command preview based on form values
     * @param {HTMLElement} form - The form element 
     */
    updateCommandPreview(form) {
        const cell = form.closest('.command-cell');
        const row = cell.closest('tr');
        const fastqName = row.querySelector('td:first-child').textContent.trim();
        const workflow = row.dataset.workflow; // Get the original workflow from the row
        const batchGroup = cell.closest('.batch-group');
        const stage = batchGroup ? batchGroup.dataset.stage : 'alignment';

        // Find the sample data
        let sample;
        if (stage === 'alignment') {
            sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === fastqName);
        } else {
            sample = this.postQCSamples.find(s => s.fastq_name === fastqName);
        }

        if (!sample) {
            console.error('Sample not found:', fastqName);
            return;
        }

        // Preserve the original workflow
        sample.workflow = workflow;

        const isAlignment = stage === 'alignment';
        const isPostQC = stage === 'postqc';
        const baseCommand = form.querySelector('.command-input').value;

        // Get asset tag from the form input if it exists
        let assetTag = '';
        if (isPostQC) {
            const assetTagInput = form.querySelector('.asset-tag-input');
            if (assetTagInput) {
                assetTag = assetTagInput.value.trim();

                // Store the asset tag on the sample for future use
                sample.assetTag = assetTag; // Always store it, even if empty
            }
        }

        // Extract asset name from base command
        const assetNameMatch = baseCommand.match(/--asset-name\s+([^\s]+)/);
        const assetName = assetNameMatch ? assetNameMatch[1] : '';

        let newCommand;

        if (isPostQC) {
            // FOR POST-QC: COMPLETELY MANUAL APPROACH
            // Start with the base part of the command (up to and including asset-name)
            const commandBase = baseCommand.replace(/--asset-tag\s+[^\s]+/, '').trim();

            // Build the command parts explicitly
            const parts = [
                commandBase,
                assetTag ? `--asset-tag ${assetTag}` : '',
                `--load-names "${sample.load_name}"`,
                '--notify-on FAILED',
                `--notify ${this.getNotificationEmail()}`
            ];

            // Join the parts, filtering out empty ones
            newCommand = parts.filter(part => part).join(' ');

            console.log(`Manually constructed command with parts:`, {
                commandBase,
                assetTagPart: assetTag ? `--asset-tag ${assetTag}` : 'NONE',
                loadNamePart: `--load-names "${sample.load_name}"`,
                finalCommand: newCommand
            });
        } else {
            // For alignment, use the regular build method
            newCommand = this.buildCommand(baseCommand, sample, {
                reference: form.querySelector('.reference-select')?.value,
                chemistry: form.querySelector('.chemistry-select')?.value,
                includeIntrons: form.querySelector('.include-introns')?.checked,
                executionPriority: form.querySelector('.execution-priority')?.checked,
                isAlignment,
                assetName,
                assetTag: assetTag, // Pass the asset tag directly
                preserveBaseCommand: true
            });
        }

        // Update the command display - DIRECTLY SET THE TEXT
        const codeElement = cell.querySelector('code');
        codeElement.textContent = newCommand;

        // Update the command in the sample data
        if (stage === 'alignment') {
            sample.alignmentCommand = newCommand;
        } else {
            sample.postQCCommand = newCommand;
        }

        // Double-check the displayed command for debugging
        setTimeout(() => {
            const displayedCommand = codeElement.textContent;
            const hasExpectedAssetTag = assetTag ? displayedCommand.includes(`--asset-tag ${assetTag}`) : true;

            console.log(`VERIFICATION CHECK:`, {
                assetTagFromForm: assetTag,
                displayedCommand: displayedCommand,
                hasExpectedAssetTag: hasExpectedAssetTag
            });

            // If expected asset tag is missing, force it in as a last resort
            if (assetTag && !hasExpectedAssetTag) {
                console.error('CRITICAL ERROR: Asset tag from form not found in displayed command!');

                // Try one last approach - completely rebuild the command
                const fixedCommand = displayedCommand.replace(/--asset-tag\s+[^\s]+/, '').replace(/--load-names/, `--asset-tag ${assetTag} --load-names`);

                codeElement.textContent = fixedCommand;

                // Update the sample data too
                if (stage === 'alignment') {
                    sample.alignmentCommand = fixedCommand;
                } else {
                    sample.postQCCommand = fixedCommand;
                }
            }
        }, 10);
    }

    addStyles() {
        const style = document.createElement('style');
        // Status-badge styling is provided by components.css (one source of
        // truth); only submit-modal-specific styles are injected here.
        style.textContent = `
            /* (badge styles removed — see components.css) */
            .unknown-libprep-section {
                background-color: #fff;
                border-radius: 0.5rem;
                box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
                margin-bottom: 1.5rem;
                overflow: hidden;
            }

            .unknown-libprep-header {
                background-color: #fff3cd;
                padding: 1rem 1.25rem;
                border-bottom: 1px solid rgba(0, 0, 0, 0.125);
            }

            .unknown-libprep-header h5 {
                color: #856404;
                font-size: 1.1rem;
                font-weight: 600;
            }

            .unknown-libprep-container {
                padding: 1.25rem;
                display: grid;
                gap: 1rem;
            }

            .unknown-libprep-card {
                background-color: #fff;
                border: 1px solid rgba(0, 0, 0, 0.125);
                border-radius: 0.375rem;
                overflow: hidden;
                transition: all 0.2s ease-in-out;
            }

            .unknown-libprep-card:hover {
                box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
            }

            .unknown-libprep-card-header {
                background-color: #f8f9fa;
                padding: 0.75rem 1.25rem;
                border-bottom: 1px solid rgba(0, 0, 0, 0.125);
            }

            .unknown-libprep-card-body {
                padding: 1.25rem;
            }

            .asset-selector-container {
                margin-bottom: 1.25rem;
            }

            .asset-selector-container .form-label {
                font-weight: 500;
                color: #495057;
                margin-bottom: 0.5rem;
            }

            .asset-selector-container .form-select {
                border-radius: 0.375rem;
                border-color: #ced4da;
                padding: 0.5rem 1rem;
                font-size: 0.875rem;
            }

            .samples-list {
                background-color: #f8f9fa;
                border-radius: 0.375rem;
                overflow: hidden;
            }

            .samples-header {
                background-color: #e9ecef;
                padding: 0.5rem 1rem;
                font-size: 0.875rem;
                font-weight: 500;
                color: #495057;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }

            .samples-content {
                padding: 0.75rem 1rem;
                max-height: 200px;
                overflow-y: auto;
            }

            .sample-item {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 0;
                font-size: 0.875rem;
                color: #6c757d;
            }

            .sample-item:not(:last-child) {
                border-bottom: 1px solid rgba(0, 0, 0, 0.05);
            }

            .sample-item i {
                color: #adb5bd;
            }

            .additional-options {
                margin-top: 1rem;
                padding: 1rem;
                background-color: #f8f9fa;
                border-radius: 0.375rem;
            }

            .additional-options .card {
                border: none;
                background-color: transparent;
            }

            .additional-options .card-title {
                font-size: 0.875rem;
                font-weight: 500;
                color: #495057;
                margin-bottom: 1rem;
            }

            .additional-options .form-check {
                margin-bottom: 0.75rem;
            }

            .additional-options .form-check-label {
                font-size: 0.875rem;
            }

            .additional-options .form-text {
                font-size: 0.75rem;
                color: #6c757d;
                margin-top: 0.25rem;
            }

            .asset-tag-input {
                font-size: 0.875rem;
            }

            /* Custom scrollbar for samples list */
            .samples-content::-webkit-scrollbar {
                width: 6px;
            }

            .samples-content::-webkit-scrollbar-track {
                background: #f1f1f1;
            }

            .samples-content::-webkit-scrollbar-thumb {
                background: #c1c1c1;
                border-radius: 3px;
            }

            .samples-content::-webkit-scrollbar-thumb:hover {
                background: #a8a8a8;
            }

            .command-edit-form {
                display: none;
                background-color: #fff;
                padding: 1rem;
                border: 1px solid rgba(0, 0, 0, 0.125);
                border-radius: 0.375rem;
                margin-top: 1rem;
            }

            .command-edit-form.show {
                display: block;
            }

            .command-cell {
                position: relative;
            }

            .command-actions {
                margin-top: 0.5rem;
                display: flex;
                gap: 0.5rem;
            }

            .command-input {
                font-family: monospace;
                font-size: 0.875rem;
            }

            code {
                display: block;
                white-space: pre-wrap;
                word-break: break-all;
                background-color: #f8f9fa;
                padding: 0.5rem;
                border-radius: 0.25rem;
                font-size: 0.875rem;
                color: #212529;
            }
        `;
        document.head.appendChild(style);
    }

    // Save current state of the modal
    saveState() {

        // Save sample states
        const sampleStates = new Map();

        // Save alignment samples
        this.alignmentSamples.forEach(sample => {
            sampleStates.set(sample.fastq_name, {
                sample: JSON.parse(JSON.stringify(sample)), // Deep clone the sample
                category: 'alignment'
            });
        });

        // Save post-QC samples
        this.postQCSamples.forEach(sample => {
            sampleStates.set(sample.fastq_name, {
                sample: JSON.parse(JSON.stringify(sample)), // Deep clone the sample
                category: 'postqc'
            });
        });

        // Save incomplete samples
        this.incompleteSamples.forEach(sample => {
            sampleStates.set(sample.fastq_name, {
                sample: JSON.parse(JSON.stringify(sample)), // Deep clone the sample
                category: 'incomplete'
            });
        });

        // Save UI state - expanded/collapsed batch groups
        const batchGroupStates = new Map();
        const batchGroups = this.modal.querySelectorAll('.batch-group');
        batchGroups.forEach(group => {
            const batchName = group.dataset.batchName;
            const isExpanded = group.querySelector('.batch-content').style.display !== 'none';
            batchGroupStates.set(batchName, {
                expanded: isExpanded,
                stage: group.dataset.stage
            });
        });

        // Save form states - opened edit forms
        const editFormStates = new Map();
        const editForms = this.modal.querySelectorAll('.command-edit-form.show');
        editForms.forEach(form => {
            const cell = form.closest('.command-cell');
            const row = cell.closest('tr');
            const sampleName = row.dataset.sample;
            const stage = row.dataset.stage;

            editFormStates.set(`${sampleName}-${stage}`, {
                baseCommand: form.querySelector('.command-input')?.value,
                reference: form.querySelector('.reference-select')?.value,
                chemistry: form.querySelector('.chemistry-select')?.value,
                includeIntrons: form.querySelector('.include-introns')?.checked,
                executionPriority: form.querySelector('.execution-priority')?.checked,
                assetTag: form.querySelector('.asset-tag-input')?.value
            });
        });

        // Save unknown library prep selections
        const unknownLibPrepStates = new Map();
        const unknownLibPrepCards = this.modal.querySelectorAll('.unknown-libprep-card');
        unknownLibPrepCards.forEach(card => {
            const libraryPrepMethod = card.dataset.libraryPrepMethod;
            const stage = card.dataset.stage;
            const selector = card.querySelector('.asset-selector');

            if (selector) {
                unknownLibPrepStates.set(`${libraryPrepMethod}-${stage}`, {
                    selectedAsset: selector.value,
                    assetTag: card.querySelector('.asset-tag-input')?.value,
                    templateType: card.querySelector('input[type="radio"]:checked')?.value
                });
            }
        });

        // Save checkbox states
        const includeIncomplete = document.getElementById('include-incomplete-samples')?.checked || false;
        const autoProceed = this.autoProceedToggle?.checked || false;
        const reprocessCompleted = document.getElementById('reprocess-completed-toggle')?.checked || false;

        // Save notification email
        const notificationEmail = this.globalNotificationEmail?.value || '';

        // Combine all state data
        this.savedState = {
            sampleStates,
            batchGroupStates,
            editFormStates,
            unknownLibPrepStates,
            includeIncomplete,
            autoProceed,
            reprocessCompleted,
            notificationEmail,
            originalCommands: new Map(this.originalCommands) // Clone the map
        };

        console.log('State saved:', {
            sampleCount: sampleStates.size,
            batchGroupCount: batchGroupStates.size,
            editFormCount: editFormStates.size,
            unknownLibPrepCount: unknownLibPrepStates.size
        });
    }

    // Restore previously saved state
    restoreState() {
        if (!this.savedState) {
            return;
        }


        // First restore basic settings
        if (this.autoProceedToggle) {
            this.autoProceedToggle.checked = this.savedState.autoProceed;
        }

        const includeIncompleteCheckbox = document.getElementById('include-incomplete-samples');
        if (includeIncompleteCheckbox) {
            includeIncompleteCheckbox.checked = this.savedState.includeIncomplete;
        }

        const reprocessCompletedCheckbox = document.getElementById('reprocess-completed-toggle');
        if (reprocessCompletedCheckbox) {
            reprocessCompletedCheckbox.checked = this.savedState.reprocessCompleted || false;
        }

        if (this.globalNotificationEmail) {
            this.globalNotificationEmail.value = this.savedState.notificationEmail;
        }

        // Restore original commands
        this.originalCommands = new Map(this.savedState.originalCommands);

        // Restore sample data
        this.alignmentSamples = [];
        this.postQCSamples = [];
        this.incompleteSamples = [];

        this.savedState.sampleStates.forEach((state, sampleName) => {
            const sample = state.sample;

            if (state.category === 'alignment') {
                this.alignmentSamples.push(sample);
            } else if (state.category === 'postqc') {
                this.postQCSamples.push(sample);
            } else if (state.category === 'incomplete') {
                this.incompleteSamples.push(sample);
            }
        });

        // Regenerate the UI based on restored data
        this.updateCommandLists();

        // After UI is regenerated, restore UI states

        // Restore batch group expansion state
        this.savedState.batchGroupStates.forEach((state, batchName) => {
            const batchGroups = this.modal.querySelectorAll(`.batch-group[data-batch-name="${batchName}"][data-stage="${state.stage}"]`);
            batchGroups.forEach(group => {
                const content = group.querySelector('.batch-content');
                const toggleBtn = group.querySelector('.toggle-batch i');

                if (content && toggleBtn) {
                    content.style.display = state.expanded ? 'block' : 'none';
                    toggleBtn.className = state.expanded ? 'bi bi-chevron-up' : 'bi bi-chevron-down';
                }
            });
        });

        // Restore edit forms
        this.savedState.editFormStates.forEach((state, key) => {
            const [sampleName, stage] = key.split('-');
            const row = this.modal.querySelector(`tr[data-sample="${sampleName}"][data-stage="${stage}"]`);

            if (row) {
                const editButton = row.querySelector('.edit-command');
                if (editButton) {
                    // Click the edit button to open the form
                    editButton.click();

                    // Now find the form and restore values
                    const form = row.querySelector('.command-edit-form');
                    if (form) {
                        if (form.querySelector('.command-input')) {
                            form.querySelector('.command-input').value = state.baseCommand || '';
                        }

                        if (form.querySelector('.reference-select')) {
                            form.querySelector('.reference-select').value = state.reference || '';
                        }

                        if (form.querySelector('.chemistry-select')) {
                            form.querySelector('.chemistry-select').value = state.chemistry || '';
                        }

                        if (form.querySelector('.include-introns')) {
                            form.querySelector('.include-introns').checked = state.includeIntrons || false;
                        }

                        if (form.querySelector('.execution-priority')) {
                            form.querySelector('.execution-priority').checked = state.executionPriority || false;
                        }

                        if (form.querySelector('.asset-tag-input')) {
                            form.querySelector('.asset-tag-input').value = state.assetTag || '';
                        }

                        // Update the command preview
                        this.updateCommandPreview(form);
                    }
                }
            }
        });

        // Restore unknown library prep selections
        this.savedState.unknownLibPrepStates.forEach((state, key) => {
            const [libraryPrepMethod, stage] = key.split('-');
            const card = this.modal.querySelector(`.unknown-libprep-card[data-library-prep-method="${libraryPrepMethod}"][data-stage="${stage}"]`);

            if (card) {
                const selector = card.querySelector('.asset-selector');
                if (selector && state.selectedAsset) {
                    selector.value = state.selectedAsset;

                    // Trigger change event to show additional options if needed
                    const event = new Event('change');
                    selector.dispatchEvent(event);

                    // Now restore additional option values
                    if (card.querySelector('.asset-tag-input') && state.assetTag) {
                        card.querySelector('.asset-tag-input').value = state.assetTag;
                    }

                    if (state.templateType) {
                        const templateRadio = card.querySelector(`input[type="radio"][value="${state.templateType}"]`);
                        if (templateRadio) {
                            templateRadio.checked = true;
                        }
                    }

                    // Update commands based on restored selections
                    this.updateUnknownLibPrepCommands(stage, libraryPrepMethod, state.selectedAsset);
                }
            }
        });

    }

    setupModalCloseHandlers() {
        // Remove any existing keydown listeners to prevent duplicates
        document.removeEventListener('keydown', this.escapeKeyHandler);

        // Create a single escape key handler that works for both modals
        this.escapeKeyHandler = (e) => {
            if (e.key === 'Escape') {
                // Check if submit modal is open
                if (this.modal && this.modal.classList.contains('show')) {
                    if (window.modalManager) {
                        window.modalManager.closeModal('submit-modal');
                        return;
                    }
                }

                // Check if final modal is open
                const finalModal = document.getElementById('final-commands-modal');
                if (finalModal && finalModal.classList.contains('show')) {
                    if (window.modalManager) {
                        window.modalManager.closeModal('final-commands-modal');
                        return;
                    }
                }
            }
        };

        // Add the single escape key handler
        document.addEventListener('keydown', this.escapeKeyHandler);
    }


    /**
     * Reset a command to its original state or regenerate it
     * @param {Object} sample - The sample object
     * @param {string} stage - The pipeline stage
     * @param {HTMLElement} cell - The cell containing the command
     */
    resetCommand(sample, stage, cell) {
        // Check if we have a stored original command
        const originalCommand = sample.originalCommands?.[stage];
        if (originalCommand) {
            const codeElement = cell.querySelector('code');
            codeElement.textContent = originalCommand;
            if (stage === 'alignment') {
                sample.alignmentCommand = originalCommand;
            } else {
                sample.postQCCommand = originalCommand;
            }
            return;
        }

        // Generate a fresh command based on workflow
        if (sample.workflow === 'MTX') {
            let commandTemplate;

            // Get appropriate template for MTX
            if (stage === 'alignment') {
                commandTemplate = this.getCommandTemplate('mtx', 'alignment', sample.library_prep_method);
            } else {
                commandTemplate = this.getCommandTemplate('mtx', 'postqc', sample.library_prep_method);
            }

            if (commandTemplate) {
                const command = this.generateCommandFromTemplate(commandTemplate, sample);
                const codeElement = cell.querySelector('code');
                codeElement.textContent = command;

                this.storeCommandAndUpdateSample(sample, stage, command);
                return;
            }
        }

        // For unknown library prep methods, check if there's a selected asset
        if (stage === 'alignment' && !this.isLibraryPrepMethodKnown(sample.library_prep_method)) {
            const libraryPrepMethodContainer = document.querySelector(
                `.unknown-libprep-card[data-library-prep-method="${sample.library_prep_method}"][data-stage="alignment"]`
            );

            if (libraryPrepMethodContainer) {
                const selectedAsset = libraryPrepMethodContainer.querySelector('.asset-selector')?.value;
                if (selectedAsset) {
                    const assetTag = libraryPrepMethodContainer.querySelector('.asset-tag-input')?.value || '';
                    const templateType = libraryPrepMethodContainer.querySelector(
                        `input[name="template-${sample.library_prep_method}"]:checked`
                    )?.value || 'standard';

                    let commandTemplate;
                    if (selectedAsset === 'cellranger-rnaseq') {
                        commandTemplate = this.getCommandTemplate('rtx', 'alignment', sample.library_prep_method);
                    } else if (selectedAsset === 'cellranger-multi') {
                        commandTemplate = this.getCommandTemplate('mtx', 'alignment', sample.library_prep_method);
                    }

                    if (commandTemplate) {
                        const command = this.generateCommandFromTemplate(commandTemplate, sample);
                        const codeElement = cell.querySelector('code');
                        codeElement.textContent = command;

                        this.storeCommandAndUpdateSample(sample, 'alignment', command);
                        return;
                    }
                }
            }
        }

        // For post-QC stage, try to regenerate command
        if (stage === 'postqc') {
            const workflow = this.determineWorkflow(sample);
            let originalCommand = '';

            // Special case for RTX workflow with unknown library prep method
            if (workflow === 'RTX' && !this.isLibraryPrepMethodKnown(sample.library_prep_method)) {
                // Check if we have the original command stored
                if (sample.originalPostQCCommand) {
                    originalCommand = sample.originalPostQCCommand;
                } else {
                    // If no original command stored, use the current command from UI
                    const codeElement = cell.querySelector('code');
                    originalCommand = codeElement.textContent.trim();

                    // Store this as the original command for future resets
                    sample.originalPostQCCommand = originalCommand;
                }
            } else {
                // Try to get template from config
                const libraryPrepMethod = sample.library_prep_method || '';
                const commandTemplate = this.getCommandTemplate(workflow, 'postqc', libraryPrepMethod);

                // Generate command from template if available
                if (commandTemplate) {
                    originalCommand = this.generateCommandFromTemplate(commandTemplate, sample);
                }
            }

            // Only update if we got a valid command
            if (originalCommand) {
                // Update the command display
                const codeElement = cell.querySelector('code');
                codeElement.textContent = originalCommand;

                this.storeCommandAndUpdateSample(sample, stage, originalCommand);
            }
        }
    }

    /**
     * Store a command for a sample and update the sample object
     * @param {Object} sample - The sample object
     * @param {string} stage - The pipeline stage
     * @param {string} command - The command to store
     */
    storeCommandAndUpdateSample(sample, stage, command) {
        // Update the command in the sample
        if (stage === 'alignment') {
            sample.alignmentCommand = command;
            // Store as original command for future resets
            if (!sample.originalCommands) {
                sample.originalCommands = {};
            }
            sample.originalCommands.alignment = command;
        } else {
            sample.postQCCommand = command;
            // Store as original command for future resets
            if (!sample.originalCommands) {
                sample.originalCommands = {};
            }
            sample.originalCommands.postqc = command;

            // Also store as originalPostQCCommand for backward compatibility
            if (!sample.originalPostQCCommand) {
                sample.originalPostQCCommand = command;
            }
        }
    }

    /**
     * Get command template from configuration
     * @param {string} workflow - Workflow name (rtx/mtx)
     * @param {string} stage - Pipeline stage (alignment/postqc)
     * @param {string} libraryPrepMethod - Library prep method
     * @returns {string} Command template
     */
    getCommandTemplate(workflow, stage, libraryPrepMethod) {
        // Normalize workflow name to lowercase
        const workflowLower = workflow.toLowerCase();

        // Check if the workflow and stage exist in config
        if (!this.config?.workflows?.[workflowLower]?.[stage]) {
            return '';
        }

        // Get command template from config
        let commandTemplate = '';
        const workflowConfig = this.config.workflows[workflowLower][stage];

        // For workflows with pattern-based configs (like RTX)
        if (typeof workflowConfig === 'object' && !workflowConfig.command_template) {
            // Find matching pattern for this library prep method
            for (const [pattern, config] of Object.entries(workflowConfig)) {
                if (pattern.includes('|')) {
                    // Multi-value pattern (separated by |)
                    const patterns = pattern.split('|');
                    if (patterns.includes(libraryPrepMethod)) {
                        commandTemplate = config.command_template;
                        break;
                    }
                } else if (pattern === libraryPrepMethod) {
                    // Single value pattern
                    commandTemplate = config.command_template;
                    break;
                }
            }
        } else {
            // For workflows with direct command_template (like MTX)
            commandTemplate = workflowConfig.command_template;
        }

        return commandTemplate;
    }

    /**
     * Generate command from template
     * @param {string} template - Command template
     * @param {Object} sample - Sample object
     * @returns {string} Generated command
     */
    generateCommandFromTemplate(template, sample) {
        if (!template) return '';

        const reference = this.getReference(sample.organism_common_name || '');
        const libraryPrep = sample.library_prep_method || '';
        const chemistry = this.getChemistry(libraryPrep);
        const notificationEmail = this.getNotificationEmail();
        const loadName = sample.load_name || '';

        // Determine workflow for asset name/tag lookup
        const workflow = sample.workflow || this.determineWorkflow(sample);

        // Get asset name and tag if available in the config
        const workflowLower = workflow.toLowerCase();
        const assetName = this.getAssetName(workflow, sample.stage || (template.includes('postalign') || template.includes('postqc') ? 'postqc' : 'alignment'), libraryPrep);

        // If the sample already has an asset tag set (for unknown library preps), use that
        // Otherwise, get it from the config
        const assetTag = sample.assetTag || this.getAssetTag(workflow, sample.stage || (template.includes('postalign') || template.includes('postqc') ? 'postqc' : 'alignment'), libraryPrep);

        // Replace known placeholders
        let command = template
            .replace(/{load_name}/g, loadName)
            .replace(/{reference}/g, reference)
            .replace(/{notification_email}/g, notificationEmail);

        // Handle chemistry placeholder specially
        if (command.includes('{chemistry}')) {
            if (chemistry) {
                command = command.replace(/{chemistry}/g, chemistry);
            } else {
                // Try to get a default chemistry from config
                const defaultChemistry = Object.values(this.config?.chemistries || {})[0];
                if (defaultChemistry) {
                    command = command.replace(/{chemistry}/g, defaultChemistry);
                } else {
                    // If no chemistry available, remove the chemistry parameter entirely
                    command = command.replace(/--chemistry\s+{chemistry}/g, '');
                }
            }
        }

        // Handle asset tag
        if (assetTag && assetTag !== 'latest') {
            if (command.includes('--asset-tag')) {
                // Replace existing asset tag
                command = command.replace(/--asset-tag\s+([^\s"]+)/, `--asset-tag ${assetTag}`);
            } else if (!command.includes('--asset-tag')) {
                // Add asset tag after asset-name parameter if not already present
                command = command.replace(/--asset-name\s+(\S+)/, `--asset-name $1 --asset-tag ${assetTag}`);
            }
        }

        return command;
    }

    /**
     * Generate alignment command for a sample
     * @param {Object} sample - Sample object
     * @returns {string} Alignment command
     */
    generateAlignmentCommand(sample) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const libraryPrepMethod = sample.library_prep_method || '';

        // Check if this is an unknown library prep method
        if (this.isRtxWorkflow(sample) && !this.isLibraryPrepMethodKnown(libraryPrepMethod)) {
            return '';
        }

        const commandTemplate = this.getCommandTemplate(workflow, 'alignment', libraryPrepMethod);
        if (!commandTemplate) {
            return '';
        }

        return this.generateCommandFromTemplate(commandTemplate, sample);
    }

    /**
     * Generate post-QC command for a sample
     * @param {Object} sample - Sample object
     * @returns {string} Post-QC command
     */
    generatePostQCCommand(sample) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const libraryPrepMethod = sample.library_prep_method || '';

        // Check if this is an unknown library prep method
        if (this.isRtxWorkflow(sample) && !this.isLibraryPrepMethodKnown(libraryPrepMethod)) {
            return '';
        }

        const commandTemplate = this.getCommandTemplate(workflow, 'postqc', libraryPrepMethod);
        if (!commandTemplate) {
            return '';
        }

        return this.generateCommandFromTemplate(commandTemplate, sample);
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    // Add global styles
    const style = document.createElement('style');
    style.textContent = `
        /* Global backdrop styling */
        .global-backdrop {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            background-color: rgba(0, 0, 0, 0.5);
            /* z-index removed to fix backdrop layering */
            display: none;
        }
        
        /* Fix for modal display - z-index removed */
        .modal {
            /* z-index removed */
        }
        
        /* Hide bootstrap modal backdrops */
        .modal-backdrop {
            display: none !important;
        }
        
        /* Add CSS to ensure the modal doesn't close on backdrop click */
        #submit-modal[data-bs-backdrop="static"] {
            pointer-events: auto !important;
        }
        
        /* Ensure modal dialog has pointer events */
        #submit-modal .modal-dialog {
            pointer-events: auto !important;
        }
    `;
    document.head.appendChild(style);

    // Initialize the modal handler
    window.pipelineSubmitModal = new PipelineSubmitModal();

    // Set the modal to static backdrop mode to prevent closing when clicking outside
    const setStaticBackdrop = () => {
        const modalElement = document.getElementById('submit-modal');
        if (modalElement) {
            // Set data attributes directly on the element
            modalElement.setAttribute('data-bs-backdrop', 'static');
            modalElement.setAttribute('data-bs-keyboard', 'true');

            // If a Bootstrap modal instance already exists, update its config
            const existingModal = bootstrap.Modal.getInstance(modalElement);
            if (existingModal) {
                if (existingModal._config) {
                    existingModal._config.backdrop = 'static';
                    existingModal._config.keyboard = true;
                }
            } else {
                // Create a new modal instance with static backdrop
                try {
                    new bootstrap.Modal(modalElement, {
                        backdrop: 'static',
                        keyboard: true
                    });
                } catch (e) {
                    console.error('Error creating modal:', e);
                }
            }

            // Add a direct event handler as a final failsafe
            modalElement.addEventListener('click', (event) => {
                if (event.target === modalElement) {
                    event.stopPropagation();
                    event.preventDefault();
                    return false;
                }
            }, true);
        }
    };

    // Apply settings immediately
    setStaticBackdrop();

    // Also apply after a short delay to ensure it takes effect after any other initializations
    setTimeout(setStaticBackdrop, 500);

    // Listen for submit button click from Pipeline Checkout
    const submitActionBtn = document.getElementById('submit-action-btn');
}); 