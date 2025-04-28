/**
 * pipeline-submit-modal.js
 * Handles the submission modal functionality for the RNA-seq pipeline
 */

class PipelineSubmitModal {
    constructor() {
        this.modal = document.getElementById('submit-modal');
        this.sampleList = document.getElementById('submit-sample-list');
        this.warningDiv = document.getElementById('incomplete-samples-warning');
        this.incompleteList = document.getElementById('incomplete-samples-list');
        this.confirmButton = document.getElementById('confirm-submit');
        this.autoProceedToggle = document.getElementById('auto-proceed-toggle');
        this.alignmentBatches = document.getElementById('alignment-batches');
        this.postQCBatches = document.getElementById('postqc-batches');
        this.globalNotificationEmail = document.getElementById('global-notification-email');

        // Create global backdrop
        this.ensureGlobalBackdrop();

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

        this.setupEventListeners();
        this.loadConfig();

        // Add styles for unknown library prep UI
        this.addStyles();
    }

    // Create or ensure global backdrop element exists
    ensureGlobalBackdrop() {
        let backdrop = document.getElementById('global-modal-backdrop');
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = 'global-modal-backdrop';
            backdrop.className = 'global-backdrop';
            backdrop.style.position = 'fixed';
            backdrop.style.top = '0';
            backdrop.style.right = '0';
            backdrop.style.bottom = '0';
            backdrop.style.left = '0';
            backdrop.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
            backdrop.style.zIndex = '1030';  // Lower than bootstrap modals (1050)
            backdrop.style.display = 'none'; // Hidden by default
            document.body.appendChild(backdrop);

            // Add style for body when backdrop is active
            const style = document.createElement('style');
            style.textContent = `
                body.backdrop-active {
                    overflow: hidden;
                    padding-right: 17px; /* Compensate for scrollbar */
                }
                
                /* Ensure modals are above backdrop */
                .modal {
                    z-index: 1050 !important;
                }
                
                /* Ensure modal backdrops don't appear */
                .modal-backdrop {
                    display: none !important;
                }
            `;
            document.head.appendChild(style);
        }

        return backdrop;
    }

    showGlobalBackdrop() {
        const backdrop = this.ensureGlobalBackdrop();
        backdrop.style.display = 'block';
        document.body.classList.add('backdrop-active');
        console.log('Global backdrop shown', {
            timestamp: new Date().toISOString(),
            backdropId: backdrop.id,
            backdropStyle: backdrop.style.display,
            bodyClass: document.body.classList.toString()
        });
    }

    hideGlobalBackdrop() {
        const backdrop = document.getElementById('global-modal-backdrop');
        if (backdrop) {
            backdrop.style.display = 'none';
            document.body.classList.remove('backdrop-active');
            console.log('Global backdrop hidden', {
                timestamp: new Date().toISOString(),
                backdropId: backdrop.id,
                backdropStyle: backdrop.style.display,
                bodyClass: document.body.classList.toString()
            });
        }
    }

    async loadConfig() {
        try {
            console.log('Loading pipeline configuration...');
            const response = await fetch('/api/pipeline/config');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            this.config = await response.json();
            console.log('Pipeline configuration loaded:', this.config);

            // Debug: Check specific configuration sections
            console.log('References:', this.config.references);
            console.log('Chemistries:', this.config.chemistries);
            console.log('Workflows:', this.config.workflows);
            console.log('MTX workflow config:', this.config.workflows?.mtx);
            console.log('Settings:', this.config.settings);

            // Validate MTX workflow configuration
            if (!this.config?.workflows?.mtx) {
                console.error('MTX workflow configuration is missing');
            } else {
                console.log('MTX workflow stages:', Object.keys(this.config.workflows.mtx));
                for (const stage of ['alignment', 'postqc']) {
                    if (this.config.workflows.mtx[stage]) {
                        console.log(`MTX ${stage} config:`, this.config.workflows.mtx[stage]);
                    } else {
                        console.error(`MTX ${stage} configuration is missing`);
                    }
                }
            }

            // After loading config, update any existing UI elements
            if (this.modal.classList.contains('show')) {
                this.populateModal();
            }
        } catch (error) {
            console.error('Error loading pipeline configuration:', error);
            // Show error message to user
            const errorDiv = document.createElement('div');
            errorDiv.className = 'alert alert-danger';
            errorDiv.textContent = 'Failed to load pipeline configuration. Please try refreshing the page.';
            this.modal.querySelector('.modal-body').prepend(errorDiv);
        }
    }

    getReferences() {
        if (!this.config) return [];

        return Object.entries(this.config.references).map(([name, value]) => ({
            name: name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
            value: value
        }));
    }

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

    getNotificationEmail() {
        return this.globalNotificationEmail?.value?.trim() || this.config?.settings?.notifications?.email?.recipients?.[0] || '$USER@alleninstitute.org';
    }

    getReference(organism) {
        // console.log('Getting reference for organism:', organism);
        if (!this.config?.references) {
            console.error('References not loaded in config');
            return '';
        }

        const normalizedOrganism = organism.toLowerCase().replace(/\s+/g, '_');
        const reference = this.config.references[normalizedOrganism] || this.config.references.human || '';
        // console.log('Found reference:', reference);
        return reference;
    }

    getChemistry(libraryPrep) {
        // console.log('Getting chemistry for library prep:', libraryPrep);
        if (!this.config?.chemistries) {
            console.error('Chemistries not loaded in config');
            return '';
        }

        const chemistry = this.config.chemistries[libraryPrep] || '';
        console.log('Found chemistry:', chemistry);
        return chemistry;
    }

    // Add this helper method at the top of the class
    cleanupModal() {
        console.log('Cleaning up modal state...');
        document.body.classList.remove('modal-open');

        // Remove all modal backdrops
        const backdrops = document.querySelectorAll('.modal-backdrop');
        backdrops.forEach(backdrop => {
            backdrop.remove();
        });

        // Reset body styles
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }

    setupEventListeners() {
        // Handle modal show event
        this.modal.addEventListener('show.bs.modal', (event) => {
            this.populateModal();
            this.setupModalCloseHandlers();

            // Check if this is from an external "Submit Selected" button click
            // We can detect this by checking for the source element of the event
            if (event.relatedTarget && event.relatedTarget.classList.contains('submit-selected-btn')) {
                console.log('Submit Selected button clicked in dashboard, showing backdrop');
                this.showGlobalBackdrop();
            }
        });

        // Handle modal hidden event to ensure cleanup
        this.modal.addEventListener('hidden.bs.modal', (event) => {
            // We don't hide backdrop here - only done via explicit cancel/close button clicks
        });

        // Add close button handler for submit modal
        const submitModalCloseBtn = this.modal.querySelector('.btn-close');
        if (submitModalCloseBtn) {
            submitModalCloseBtn.onclick = (e) => {
                e.preventDefault();
                console.log('Submit modal close button clicked, hiding backdrop');
                const modalInstance = bootstrap.Modal.getInstance(this.modal);
                if (modalInstance) {
                    modalInstance.hide();
                    this.hideGlobalBackdrop();
                }
            };
        }

        // Add cancel button handler
        const cancelButton = this.modal.querySelector('.btn-cancel, .btn-secondary');
        if (cancelButton) {
            cancelButton.onclick = (e) => {
                e.preventDefault();
                console.log('Submit modal cancel button clicked, hiding backdrop');
                const modalInstance = bootstrap.Modal.getInstance(this.modal);
                if (modalInstance) {
                    modalInstance.hide();
                    this.hideGlobalBackdrop();
                }
            };
        }

        // Handle auto-proceed toggle change
        if (this.autoProceedToggle) {
            this.autoProceedToggle.addEventListener('change', () => {
                this.updateCommandLists();
            });
        }

        // Handle confirm button click
        this.confirmButton.addEventListener('click', () => {
            console.log('Confirm and Submit button clicked, showing backdrop');
            this.showGlobalBackdrop();
            this.handleSubmission();
        });

        // Set up event listeners for final modal events
        document.addEventListener('finalModalBack', () => {
            console.log('finalModalBack event received in submit modal');
            // Back button clicked in final modal
            console.log('Back button clicked in final modal, showing backdrop');
            this.showGlobalBackdrop();

            const submitModal = new bootstrap.Modal(this.modal);
            submitModal.show();

            // Restore state when returning from final modal
            this.restoreState();
        });

        document.addEventListener('finalModalExecute', (event) => {
            this.handleFinalExecution(event.detail.commands);
        });

        // Add event listener for final modal close
        document.addEventListener('finalModalClose', () => {
            console.log('Final modal closed (from X/Cancel/ESC), hiding backdrop');
            this.hideGlobalBackdrop();
        });

        // Edit button click
        this.modal.addEventListener('click', (e) => {
            const editButton = e.target.closest('.edit-command');
            if (editButton) {
                console.log('Edit button clicked');
                e.preventDefault();
                const cell = editButton.closest('.command-cell');
                const row = cell.closest('tr');
                const currentCommand = cell.querySelector('code').textContent;
                const stage = row.dataset.stage;
                const sampleName = row.dataset.sample;
                const workflow = row.dataset.workflow;
                const isAutoProceed = row.hasAttribute('data-auto-proceed');

                // Store the original command state with a unique key
                const commandKey = `${sampleName}-${stage}-${isAutoProceed ? 'auto' : 'regular'}`;
                this.originalCommands.set(commandKey, {
                    command: currentCommand,
                    values: this.parseCommand(currentCommand)
                });

                console.log('Stored original command state:', {
                    key: commandKey,
                    state: this.originalCommands.get(commandKey)
                });

                console.log('Edit command context:', {
                    currentCommand,
                    sampleName,
                    stage,
                    workflow,
                    isAutoProceed
                });

                // Find sample directly from our tracked arrays by fastq_name
                let sample = null;

                if (stage === 'alignment' || (stage === 'postqc' && isAutoProceed)) {
                    // For alignment or auto-proceed post-QC, look in alignment samples
                    sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleName);
                    console.log('Looking for sample in alignment/incomplete:', {
                        alignmentSamples: this.alignmentSamples.length,
                        incompleteSamples: this.incompleteSamples.length,
                        found: !!sample,
                        searchingFor: sampleName
                    });
                } else {
                    // Regular post-QC samples
                    sample = this.postQCSamples.find(s => s.fastq_name === sampleName);
                    console.log('Looking for sample in postQC:', {
                        postQCSamples: this.postQCSamples.length,
                        found: !!sample,
                        searchingFor: sampleName
                    });
                }

                if (!sample) {
                    console.error('Could not find sample in our data arrays');
                    return;
                }

                // Look for MTX indicators in the command
                const isMtxCommand = currentCommand.includes('tenx-rnaseq-multi') ||
                    currentCommand.includes('cellranger-multi');

                console.log('Command analysis:', {
                    originalCommand: currentCommand,
                    isMtxCommand,
                    sampleWorkflow: sample.workflow,
                    commandContainsArc: currentCommand.includes('tenx-arc'),
                    commandContainsMulti: currentCommand.includes('tenx-rnaseq-multi')
                });

                // Force workflow based on command for more reliability
                if (isMtxCommand) {
                    sample.workflow = 'MTX';
                    console.log('Forced workflow to MTX based on command');
                }

                // CRITICAL: Parse the command to extract values
                const currentValues = this.parseCommand(currentCommand);
                console.log('Parsed values from command:', currentValues);

                // Get the existing form and replace it
                const existingForm = cell.querySelector('.command-edit-form');
                if (existingForm) {
                    console.log('Replacing existing form with newly generated one');
                    // Create a temporary container to parse the HTML
                    const tempContainer = document.createElement('div');
                    const formHtml = this.createCommandEditForm(sample, stage, currentCommand);
                    console.log('Generated form HTML with command:', currentCommand);
                    tempContainer.innerHTML = formHtml;
                    const newForm = tempContainer.firstElementChild;

                    // Replace the existing form
                    existingForm.parentNode.replaceChild(newForm, existingForm);

                    // Show the new form
                    newForm.classList.add('show');

                    // Log the form state before adding event listeners
                    const formState = {
                        baseCommand: newForm.querySelector('.command-input')?.value,
                        reference: newForm.querySelector('.reference-select')?.value,
                        chemistry: newForm.querySelector('.chemistry-select')?.value,
                        includeIntrons: newForm.querySelector('.include-introns')?.checked,
                        executionPriority: newForm.querySelector('.execution-priority')?.checked
                    };
                    console.log('Form state after creation:', formState);

                    // Add event listeners to the new form
                    const inputs = newForm.querySelectorAll('input, select');
                    inputs.forEach(input => {
                        input.addEventListener('change', () => {
                            console.log('Input changed:', {
                                type: input.type,
                                class: input.className,
                                value: input.type === 'checkbox' ? input.checked : input.value
                            });
                            this.updateCommandPreview(newForm);
                        });
                    });

                    // For text inputs, also listen for keyup events
                    const textInputs = newForm.querySelectorAll('input[type="text"]');
                    textInputs.forEach(input => {
                        input.addEventListener('keyup', () => {
                            console.log('Text input keyup:', {
                                class: input.className,
                                value: input.value
                            });
                            this.updateCommandPreview(newForm);
                        });
                    });

                    // Handle cancel button
                    const cancelButton = newForm.querySelector('.cancel-edit');
                    if (cancelButton) {
                        cancelButton.addEventListener('click', () => {
                            console.log('Cancel button clicked');
                            newForm.classList.remove('show');
                        });
                    }

                    // Handle save button
                    const saveButton = newForm.querySelector('.save-command');
                    if (saveButton) {
                        saveButton.addEventListener('click', () => {
                            console.log('Save button clicked');
                            newForm.classList.remove('show');
                        });
                    }

                    // Log the final form state
                    console.log('Final form state:', {
                        baseCommand: newForm.querySelector('.command-input')?.value,
                        reference: newForm.querySelector('.reference-select')?.value,
                        chemistry: newForm.querySelector('.chemistry-select')?.value,
                        includeIntrons: newForm.querySelector('.include-introns')?.checked,
                        executionPriority: newForm.querySelector('.execution-priority')?.checked
                    });
                }
            }
        });

        // Cancel button click
        this.modal.addEventListener('click', (e) => {
            const cancelButton = e.target.closest('.cancel-edit');
            if (cancelButton) {
                e.preventDefault();
                console.log('Cancel button clicked');
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
                    console.log('Restoring original command state:', originalState);

                    // Restore the command display
                    const codeElement = cell.querySelector('code');
                    codeElement.textContent = originalState.command;

                    // Update the form inputs with original values
                    if (originalState.values) {
                        const baseCommandInput = form.querySelector('.command-input');
                        if (baseCommandInput) baseCommandInput.value = originalState.values.baseCommand || '';

                        const referenceSelect = form.querySelector('.reference-select');
                        if (referenceSelect) referenceSelect.value = originalState.values.reference || '';

                        const chemistrySelect = form.querySelector('.chemistry-select');
                        if (chemistrySelect) chemistrySelect.value = originalState.values.chemistry || '';

                        const includeIntronsCheck = form.querySelector('.include-introns');
                        if (includeIntronsCheck) includeIntronsCheck.checked = originalState.values.includeIntrons || false;

                        const executionPriorityCheck = form.querySelector('.execution-priority');
                        if (executionPriorityCheck) executionPriorityCheck.checked = originalState.values.executionPriority || false;

                        const assetTagInput = form.querySelector('.asset-tag-input');
                        if (assetTagInput) assetTagInput.value = originalState.values.assetTag || '';
                    }

                    // Update the sample's stored command
                    let sample;
                    if (stage === 'alignment' || (stage === 'postqc' && isAutoProceed)) {
                        sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleName);
                    } else {
                        sample = this.postQCSamples.find(s => s.fastq_name === sampleName);
                    }

                    if (sample) {
                        if (stage === 'alignment') {
                            sample.alignmentCommand = originalState.command;
                        } else {
                            sample.postQCCommand = originalState.command;
                        }
                    }

                    // Clean up the stored state
                    this.originalCommands.delete(commandKey);
                } else {
                    console.warn('No original command state found for:', commandKey);
                }

                // Hide the form
                form.classList.remove('show');
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
                console.log('Reset button clicked');
                const cell = e.target.closest('.command-cell');
                const row = cell.closest('tr');
                const fastqName = row.querySelector('td:first-child').textContent.trim();
                const batchGroup = cell.closest('.batch-group');
                const stage = row.dataset.stage;
                const workflow = row.dataset.workflow;
                const isAutoProceed = row.hasAttribute('data-auto-proceed');

                console.log('Reset context:', {
                    fastqName,
                    stage,
                    workflow,
                    isAutoProceed,
                    batchGroup: batchGroup ? batchGroup.dataset.batchName : 'none'
                });

                // Find the sample data from our tracked samples
                let sample;
                if (stage === 'alignment' || (stage === 'postqc' && isAutoProceed)) {
                    // For alignment or auto-proceed post-QC, look in alignment samples
                    sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === fastqName);
                    console.log('Looking for sample in alignment/incomplete:', {
                        alignmentSamples: this.alignmentSamples.length,
                        incompleteSamples: this.incompleteSamples.length,
                        found: !!sample
                    });
                } else {
                    sample = this.postQCSamples.find(s => s.fastq_name === fastqName);
                    console.log('Looking for sample in postQC:', {
                        postQCSamples: this.postQCSamples.length,
                        found: !!sample
                    });
                }

                if (!sample) {
                    console.error('Sample not found:', fastqName);
                    return;
                }

                // Force workflow to match the row's dataset
                sample.workflow = workflow;

                console.log('Found sample:', {
                    fastqName: sample.fastq_name,
                    libraryPrepMethod: sample.library_prep_method,
                    workflow: sample.workflow
                });

                // Check if we have a stored original command
                const originalCommand = sample.originalCommands?.[stage];
                if (originalCommand) {
                    console.log(`Found stored original ${stage} command:`, originalCommand);
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
                    console.log('Regenerating command for MTX sample');
                    let commandTemplate;

                    // Get appropriate template for MTX
                    if (stage === 'alignment') {
                        commandTemplate = this.getCommandTemplate('mtx', 'alignment', sample.library_prep_method);
                    } else {
                        commandTemplate = this.getCommandTemplate('mtx', 'postqc', sample.library_prep_method);
                    }

                    if (commandTemplate) {
                        const command = this.generateCommandFromTemplate(commandTemplate, sample);
                        console.log(`Generated new command for MTX ${stage}:`, command);
                        const codeElement = cell.querySelector('code');
                        codeElement.textContent = command;

                        if (stage === 'alignment') {
                            sample.alignmentCommand = command;
                            // Store this as the original command for future resets
                            if (!sample.originalCommands) {
                                sample.originalCommands = {};
                            }
                            sample.originalCommands.alignment = command;
                        } else {
                            sample.postQCCommand = command;
                            // Store this as the original command for future resets
                            if (!sample.originalCommands) {
                                sample.originalCommands = {};
                            }
                            sample.originalCommands.postqc = command;
                        }
                        return;
                    } else {
                        console.error(`No command template found for MTX ${stage}`);
                    }
                }

                // For unknown library prep methods, we need to check if there's a selected asset
                if (stage === 'alignment' && !this.isLibraryPrepMethodKnown(sample.library_prep_method)) {
                    const libraryPrepMethodContainer = document.querySelector(`.unknown-libprep-card[data-library-prep-method="${sample.library_prep_method}"][data-stage="alignment"]`);
                    if (libraryPrepMethodContainer) {
                        const selectedAsset = libraryPrepMethodContainer.querySelector('.asset-selector')?.value;
                        if (selectedAsset) {
                            // Use the same logic as updateUnknownLibPrepCommands to generate the command
                            let commandTemplate = '';
                            if (selectedAsset === 'cellranger-rnaseq') {
                                const assetTag = libraryPrepMethodContainer.querySelector('.asset-tag-input')?.value || '';
                                const templateType = libraryPrepMethodContainer.querySelector(`input[name="template-${sample.library_prep_method}"]:checked`)?.value || 'standard';
                                const commandTemplate = this.getCommandTemplate('rtx', 'alignment', sample.library_prep_method);
                                if (commandTemplate) {
                                    const command = this.generateCommandFromTemplate(commandTemplate, sample);
                                    console.log('Generated command for unknown library prep method:', command);
                                    const codeElement = cell.querySelector('code');
                                    codeElement.textContent = command;
                                    sample.alignmentCommand = command;
                                    console.log('Command reset complete');
                                    return;
                                }
                            } else if (selectedAsset === 'cellranger-multi') {
                                const commandTemplate = this.getCommandTemplate('mtx', 'alignment', sample.library_prep_method);
                                if (commandTemplate) {
                                    const command = this.generateCommandFromTemplate(commandTemplate, sample);
                                    console.log('Generated command for unknown library prep method:', command);
                                    const codeElement = cell.querySelector('code');
                                    codeElement.textContent = command;
                                    sample.alignmentCommand = command;
                                    console.log('Command reset complete');
                                    return;
                                }
                            }

                            if (commandTemplate) {
                                const command = this.generateCommandFromTemplate(commandTemplate, sample);
                                console.log('Generated command for unknown library prep method:', command);
                                const codeElement = cell.querySelector('code');
                                codeElement.textContent = command;
                                sample.alignmentCommand = command;
                                console.log('Command reset complete');
                                return;
                            }
                        }
                    }
                }

                // For post-QC stage, try to regenerate command
                if (stage === 'postqc') {
                    const workflow = this.determineWorkflow(sample);
                    console.log(`Regenerating post-QC command for ${sample.fastq_name} with workflow ${workflow}`);

                    // Initialize originalCommand variable
                    let originalCommand = '';

                    // Special case for RTX workflow with unknown library prep method
                    if (workflow === 'RTX' && !this.isLibraryPrepMethodKnown(sample.library_prep_method)) {
                        console.log('Unknown library prep method for RTX post-QC, checking for original command');

                        // Check if we have the original command stored
                        if (sample.originalPostQCCommand) {
                            console.log('Found stored original command:', sample.originalPostQCCommand);
                            originalCommand = sample.originalPostQCCommand;
                        } else {
                            // If no original command stored, use the current command from UI
                            const codeElement = cell.querySelector('code');
                            originalCommand = codeElement.textContent.trim();
                            console.log('No stored command found, using current command:', originalCommand);

                            // Store this as the original command for future resets
                            sample.originalPostQCCommand = originalCommand;
                        }

                        console.log('Using command for unknown RTX post-QC:', originalCommand);
                    } else {
                        // Try to get template from config
                        const libraryPrepMethod = sample.library_prep_method || '';
                        const commandTemplate = this.getCommandTemplate(workflow, 'postqc', libraryPrepMethod);

                        // Generate command from template if available
                        if (commandTemplate) {
                            console.log('Using template from config:', commandTemplate);
                            originalCommand = this.generateCommandFromTemplate(commandTemplate, sample);
                            console.log('Generated command from template:', originalCommand);
                        } else {
                            console.error('Failed to generate post-QC command');
                        }
                    }

                    console.log('Generated original command:', originalCommand);

                    // Only update if we got a valid command
                    if (originalCommand) {
                        // Update the command display
                        const codeElement = cell.querySelector('code');
                        codeElement.textContent = originalCommand;

                        // Update the command in the sample data
                        if (stage === 'alignment') {
                            sample.alignmentCommand = originalCommand;
                        } else {
                            sample.postQCCommand = originalCommand;
                            // Store the original command for reset functionality
                            if (!sample.originalPostQCCommand) {
                                sample.originalPostQCCommand = originalCommand;
                                console.log('Stored original post-QC command:', originalCommand);
                            }
                        }

                        console.log('Command reset complete');
                    } else {
                        console.warn('No valid command generated for reset');
                    }
                }
            }
        });

        // Handle global notification email changes
        if (this.globalNotificationEmail) {
            this.globalNotificationEmail.addEventListener('input', () => {
                this.updateAllCommandsWithEmail();
            });

            // Set initial value from config
            this.globalNotificationEmail.value = this.getNotificationEmail();
        }
    }

    populateModal() {
        // Reset unknown library prep tracking
        this.unknownLibraryPrepMethodSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // Clear existing content
        this.sampleList.innerHTML = '';
        this.incompleteList.innerHTML = '';
        this.warningDiv.classList.add('d-none');
        this.alignmentBatches.innerHTML = '';
        this.postQCBatches.innerHTML = '';

        // Reset sample tracking arrays
        this.alignmentSamples = [];
        this.postQCSamples = [];
        this.incompleteSamples = [];

        // Get only the checked samples from the table
        const selectedRows = document.querySelectorAll('.sample-select:checked');
        const selectedSamples = [];

        console.log('Processing selected samples...');

        selectedRows.forEach(checkbox => {
            const row = checkbox.closest('tr');
            if (row) {
                const sample = {
                    fastq_name: row.querySelector('td:nth-child(2)').textContent.trim(),
                    study_set: row.querySelector('td:nth-child(3)').textContent.trim(),
                    load_name: row.querySelector('td:nth-child(4)').textContent.trim(),
                    batch_name_from_vendor: row.querySelector('td:nth-child(5)').textContent.trim(),
                    organism_common_name: row.querySelector('td:nth-child(6)').textContent.trim(),
                    library_prep_method: row.querySelector('td:nth-child(7)').textContent.trim(),
                    ingest_status: row.querySelector('td:nth-child(8)').textContent.trim(),
                    alignment_status: row.querySelector('td:nth-child(9)').textContent.trim(),
                    postqc_status: row.querySelector('td:nth-child(10)').textContent.trim()
                };

                // Pre-determine workflow and cache it on the sample object
                sample.workflow = this.determineWorkflow(sample);

                selectedSamples.push(sample);

                console.log('Processing sample for categorization:', {
                    fastqName: sample.fastq_name,
                    ingestStatus: sample.ingest_status,
                    alignmentStatus: sample.alignment_status,
                    postQCStatus: sample.postqc_status,
                    workflow: sample.workflow
                });

                // Categorize the sample based on status (case-insensitive comparison)
                const ingestStatus = sample.ingest_status.toLowerCase();
                const alignmentStatus = sample.alignment_status.toLowerCase();
                const postQCStatus = sample.postqc_status.toLowerCase();

                if (ingestStatus === 'not started') {
                    console.log(`${sample.fastq_name} categorized as incomplete`);
                    this.incompleteSamples.push(sample);
                } else if (alignmentStatus !== 'completed') {
                    console.log(`${sample.fastq_name} categorized for alignment`);
                    this.alignmentSamples.push(sample);
                } else if (postQCStatus !== 'completed') {
                    console.log(`${sample.fastq_name} categorized for post-QC`);
                    this.postQCSamples.push(sample);
                } else {
                    console.log(`${sample.fastq_name} already completed all stages`);
                }
            }
        });

        console.log('Sample categorization results:', {
            totalSelected: selectedSamples.length,
            incomplete: this.incompleteSamples.length,
            forAlignment: this.alignmentSamples.length,
            forPostQC: this.postQCSamples.length
        });

        // Populate the table
        selectedSamples.forEach(sample => {
            const row = document.createElement('tr');
            row.dataset.sample = sample.fastq_name;

            // Extract values from sample data
            const fastqName = sample.fastq_name || '';
            const loadName = sample.load_name || '';
            const workflow = sample.workflow || 'RTX'; // Use cached workflow
            const organism = sample.organism_common_name || '';
            const libraryPrepMethod = sample.library_prep_method || '';
            const ingestStatus = sample.ingest_status || 'Not started';
            const alignmentStatus = sample.alignment_status || 'Not started';
            const postQCStatus = sample.postqc_status || 'Not Started';

            row.innerHTML = `
                <td>${fastqName}</td>
                <td>${loadName}</td>
                <td>${sample.batch_name_from_vendor || ''}</td>
                <td><span class="badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span></td>
                <td>${organism}</td>
                <td>${libraryPrepMethod}</td>
                <td><span class="badge ${this.getStatusBadgeClass(ingestStatus)}">${ingestStatus}</span></td>
                <td><span class="badge ${this.getStatusBadgeClass(alignmentStatus)}">${alignmentStatus}</span></td>
                <td><span class="badge ${this.getStatusBadgeClass(postQCStatus)}">${postQCStatus}</span></td>
            `;
            this.sampleList.appendChild(row);
        });

        // Show warning if there are incomplete samples
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

        // Wait for config to be loaded if not already
        if (!this.config) {
            console.log('Config not loaded yet, waiting before updating command lists');
            this.loadConfig().then(() => {
                // Just call updateCommandLists which handles everything
                this.updateCommandLists();
            });
        } else {
            // Just call updateCommandLists which now handles everything
            this.updateCommandLists();
        }
    }

    processUnknownLibraryPreps(samples) {
        console.log('Processing Unknown Library Prep');
        const includeIncomplete = document.getElementById('include-incomplete-samples')?.checked || false;
        const autoProceed = document.getElementById('auto-proceed-toggle')?.checked || false;
        console.log('Settings:', {
            includeIncomplete,
            autoProceed
        });

        // Reset unknown library prep tracking
        this.unknownLibraryPrepMethodSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // Only track unknown library preps for RTX workflow
        samples.forEach(sample => {
            console.log('\nProcessing sample:', {
                fastqName: sample.fastq_name,
                loadName: sample.load_name,
                ingestStatus: sample.ingest_status,
                alignmentStatus: sample.alignment_status,
                postQCStatus: sample.postqc_status,
                libraryPrepMethod: sample.library_prep_method,
                batchName: sample.batch_name_from_vendor
            });

            // Get workflow - use cached value if available
            const workflow = sample.workflow || this.determineWorkflow(sample);

            // Skip MTX samples
            if (workflow === 'MTX') {
                console.log(`Skipping ${sample.fastq_name} - MTX samples don't need unknown library prep processing`);
                return; // Skip to next sample
            }

            // Only process RTX workflow samples
            if (workflow === 'RTX') {
                const libraryPrepMethod = sample.library_prep_method || '';
                const isLibraryPrepMethodKnown = this.isLibraryPrepMethodKnown(libraryPrepMethod);
                console.log('Library prep method check:', {
                    method: libraryPrepMethod,
                    isKnown: isLibraryPrepMethodKnown
                });

                if (!isLibraryPrepMethodKnown) {
                    const isIncomplete = sample.ingest_status.toLowerCase() === 'not started';

                    // First, check alignment eligibility
                    const isEligibleForAlignment = isIncomplete ? includeIncomplete : true;

                    console.log('Sample eligibility check:', {
                        sample: sample.fastq_name,
                        isIncomplete,
                        includeIncomplete,
                        isEligibleForAlignment,
                        ingestStatus: sample.ingest_status,
                        alignmentStatus: sample.alignment_status,
                        postQCStatus: sample.postqc_status,
                        autoProceed
                    });

                    // Handle alignment eligibility
                    if (isEligibleForAlignment) {
                        console.log(`Adding ${sample.fastq_name} to alignment unknown list`);
                        if (!this.unknownLibraryPrepMethodSamples.alignment.has(libraryPrepMethod)) {
                            this.unknownLibraryPrepMethodSamples.alignment.set(libraryPrepMethod, []);
                        }
                        this.unknownLibraryPrepMethodSamples.alignment.get(libraryPrepMethod).push(sample);
                    } else {
                        console.log(`Skipping ${sample.fastq_name} for alignment - not eligible (incomplete sample and include-incomplete not checked)`);
                    }

                    // Handle post-QC eligibility separately
                    const isEligibleForPostQC =
                        // Either completed alignment and not completed post-QC
                        (sample.alignment_status.toLowerCase() === 'completed' &&
                            sample.postqc_status.toLowerCase() !== 'completed') ||
                        // Or auto-proceed is enabled and sample is eligible for alignment
                        (autoProceed && isEligibleForAlignment);

                    if (isEligibleForPostQC) {
                        console.log(`Adding ${sample.fastq_name} to post-QC unknown list`);
                        if (!this.unknownLibraryPrepMethodSamples.postqc.has(libraryPrepMethod)) {
                            this.unknownLibraryPrepMethodSamples.postqc.set(libraryPrepMethod, []);
                        }
                        this.unknownLibraryPrepMethodSamples.postqc.get(libraryPrepMethod).push(sample);
                    } else {
                        console.log(`Skipping ${sample.fastq_name} for post-QC - not eligible`);
                    }
                }
            }
        });

        // After processing all samples, ensure warnings are displayed
        this.addUnknownLibPrepWarnings();

        console.log('\nFinal unknown library prep state:', {
            alignmentMethods: Array.from(this.unknownLibraryPrepMethodSamples.alignment.keys()),
            alignmentSampleCounts: Array.from(this.unknownLibraryPrepMethodSamples.alignment.entries()).map(([method, samples]) => ({
                method,
                count: samples.length,
                samples: samples.map(s => s.fastq_name)
            })),
            postqcMethods: Array.from(this.unknownLibraryPrepMethodSamples.postqc.keys()),
            postqcSampleCounts: Array.from(this.unknownLibraryPrepMethodSamples.postqc.entries()).map(([method, samples]) => ({
                method,
                count: samples.length,
                samples: samples.map(s => s.fastq_name)
            }))
        });
    }

    updateCommandLists() {
        console.log('Updating Command Lists');
        // Clear existing content
        this.alignmentBatches.innerHTML = '';
        this.postQCBatches.innerHTML = '';

        const autoProceed = this.autoProceedToggle.checked;
        const includeIncomplete = document.getElementById('include-incomplete-samples')?.checked || false;

        console.log('Update context:', {
            autoProceed,
            includeIncomplete,
            alignmentSamplesCount: this.alignmentSamples.length,
            incompleteSamplesCount: this.incompleteSamples.length,
            postQCSamplesCount: this.postQCSamples.length
        });

        // Group samples by batch name
        const alignmentSamples = [...this.alignmentSamples];
        if (includeIncomplete) {
            console.log('Including incomplete samples:', {
                count: this.incompleteSamples.length,
                samples: this.incompleteSamples.map(s => ({
                    fastqName: s.fastq_name,
                    ingestStatus: s.ingest_status,
                    libraryPrepMethod: s.library_prep_method
                }))
            });
            alignmentSamples.push(...this.incompleteSamples);
        }

        const alignmentBatches = this.groupSamplesByBatch(alignmentSamples);
        const postQCBatches = this.groupSamplesByBatch(this.postQCSamples);

        console.log('Grouped samples:', {
            alignmentBatchCount: alignmentBatches.size,
            postQCBatchCount: postQCBatches.size
        });

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
        };
    }

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

    createCommandEditForm(sample, stage, command) {
        console.log('Creating command edit form for:', {
            sample: sample ? {
                fastqName: sample.fastq_name,
                loadName: sample.load_name,
                workflow: sample.workflow || this.determineWorkflow(sample),
                libraryPrepMethod: sample.library_prep_method
            } : 'No sample',
            stage,
            command
        });

        // Parse the command to extract current values
        const currentValues = this.parseCommand(command);
        console.log('Current values from command:', currentValues);

        // Check if this is post-QC stage
        const isPostQC = stage === 'postqc';

        // Try to extract asset tag from command if it's post-QC
        let assetTag = '';
        if (isPostQC) {
            const assetTagMatch = command.match(/--asset-tag\s+([^\s"]+)/);
            if (assetTagMatch) {
                assetTag = assetTagMatch[1];
                //console.log('Found asset tag in command:', assetTag);
            }
        }

        // Create the form HTML
        const formHtml = `
            <div class="command-edit-form">
                <div class="mb-3">
                    <label class="form-label">Base Command</label>
                    <input type="text" class="form-control command-input" value="${currentValues.baseCommand || ''}" data-workflow="${this.determineWorkflow(sample)}" style="font-family: monospace;">
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
        console.log('Parsing command:', command);
        const values = {};

        if (!command) {
            console.log('No command to parse');
            return values;
        }

        // Extract the base command up to the first -- flag
        const commandParts = command.split(/\s+--/);
        values.baseCommand = commandParts[0];

        // Add back the asset-name part if it exists in the original command
        const assetNameMatch = command.match(/--asset-name\s+([^\s"]+)/);
        if (assetNameMatch) {
            values.baseCommand += ` --asset-name ${assetNameMatch[1]}`;
            // console.log('Found asset name in command:', assetNameMatch[1]);
        }

        // Extract asset tag
        const assetTagMatch = command.match(/--asset-tag\s+([^\s"]+)/);
        if (assetTagMatch) {
            values.assetTag = assetTagMatch[1];
            // console.log('Found asset tag in command:', values.assetTag);
        }

        console.log('Extracted base command:', values.baseCommand);

        // Extract reference
        const referenceMatch = command.match(/--reference-names\s+"([^"]+)"/);
        if (referenceMatch) {
            values.reference = referenceMatch[1];
            console.log('Found reference in command:', values.reference);
        }

        // Extract cellranger-addopts
        const cellrangerAddoptsMatch = command.match(/--cellranger-addopts\s+["']([^"']+)["']/);
        if (cellrangerAddoptsMatch) {
            const addopts = cellrangerAddoptsMatch[1];
            console.log('Found cellranger-addopts:', addopts);

            // Extract chemistry from addopts
            const chemistryMatch = addopts.match(/--chemistry\s+([^\s"']+)/);
            if (chemistryMatch) {
                values.chemistry = chemistryMatch[1];
                console.log('Found chemistry in addopts:', values.chemistry);
            }

            // Check for include-introns in addopts
            values.includeIntrons = addopts.includes('--include-introns');
            console.log('Include introns in addopts:', values.includeIntrons);
        }

        // Also check for include-introns directly in command
        if (!values.hasOwnProperty('includeIntrons')) {
            values.includeIntrons = command.includes('--include-introns');
            console.log('Include introns in command:', values.includeIntrons);
        }

        // Check for execution priority
        values.executionPriority = command.includes('--execution-priority HIGH');
        console.log('Execution priority in command:', values.executionPriority);

        console.log('Final parsed values:', values);
        return values;
    }

    determineWorkflow(sample, options = {}) {
        // If workflow is already cached on the sample, return it
        if (sample._cachedWorkflow) {
            return sample._cachedWorkflow;
        }

        const {
            checkCommand = false,
            command = '',
            forceMtx = false
        } = options;

        console.log('Determining workflow for sample:', {
            fastqName: sample.fastq_name,
            batchName: sample.batch_name_from_vendor,
            checkCommand,
            command,
            forceMtx
        });

        // If forceMtx is true, return MTX immediately
        if (forceMtx) {
            console.log('Force MTX option is true, returning MTX workflow');
            const result = 'MTX';
            sample._cachedWorkflow = result;
            return result;
        }

        // Get batch name from vendor, default to empty string if not present
        const batchName = (sample.batch_name_from_vendor || '').toUpperCase();

        // Check for MTX workflow indicators
        const isMtxBatch = batchName.startsWith('MTX') || batchName.includes('ATX');
        const isMtxCommand = checkCommand && command && (
            command.includes('tenx-rnaseq-multi') ||
            command.includes('cellranger-multi')
        );

        console.log('MTX workflow checks:', {
            batchName,
            isMtxBatch,
            isMtxCommand,
            checkCommand,
            hasMultiCommand: command.includes('tenx-rnaseq-multi'),
            hasCellrangerMulti: command.includes('cellranger-multi')
        });

        // Return MTX if either indicator is present
        if (isMtxBatch || isMtxCommand) {
            console.log('Detected MTX workflow');
            const result = 'MTX';
            sample._cachedWorkflow = result;
            return result;
        }

        // Check for RTX workflow
        if (batchName.startsWith('RTX') || !batchName.includes('-')) {
            console.log('Detected RTX workflow');
            const result = 'RTX';
            sample._cachedWorkflow = result;
            return result;
        }

        // Default to RTX for unrecognized patterns
        console.log('No specific workflow detected, defaulting to RTX');
        const result = 'RTX';
        sample._cachedWorkflow = result;
        return result;
    }

    isMtxWorkflow(sample, options = {}) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample, options);
        return workflow === 'MTX';
    }

    isRtxWorkflow(sample, options = {}) {
        // Use cached workflow if available, otherwise determine it
        const workflow = sample.workflow || this.determineWorkflow(sample, options);
        return workflow === 'RTX';
    }

    getStatusBadgeClass(status) {
        // Always use grey for "Not started" status
        if (status.toLowerCase() === 'not started') {
            return 'bg-secondary';
        }

        // Other statuses
        switch (status.toLowerCase()) {
            case 'completed':
                return 'bg-success';
            case 'running':
            case 'in progress':
                return 'bg-primary';
            case 'failed':
                return 'bg-danger';
            case 'warning':
                return 'bg-warning';
            default:
                return 'bg-secondary';
        }
    }

    getCommandTemplate(workflow, stage, libraryPrepMethod) {
        console.log(`Getting command template for workflow: ${workflow}, stage: ${stage}, libraryPrep: ${libraryPrepMethod}`);

        // Fallback templates for MTX
        const fallbackTemplates = {
            mtx: {
                alignment: 'ocs fastqs align tenx-rnaseq-multi --asset-name cellranger-multi --reference-names "{reference}" --load-names "{load_name}" --notify-on FAILED --notify {notification_email}',
                postqc: 'ocs results postqc multi_gex_qc --asset-name multi_gex_qc --load-names "{load_name}" --notify-on FAILED --notify {notification_email}'
            }
        };

        if (!this.config?.workflows?.[workflow.toLowerCase()]?.[stage]) {
            console.error(`No workflow configuration found for ${workflow} ${stage}`);
            console.log('Available workflows:', Object.keys(this.config?.workflows || {}));
            console.log('Config structure:', JSON.stringify(this.config?.workflows || {}, null, 2));

            // Use fallback template for MTX
            if (workflow.toLowerCase() === 'mtx' && fallbackTemplates.mtx[stage]) {
                console.log(`Using fallback template for MTX ${stage}`);
                return fallbackTemplates.mtx[stage];
            }

            return '';
        }

        // Get command template from config
        let commandTemplate = '';
        const workflowConfig = this.config.workflows[workflow.toLowerCase()][stage];
        console.log(`Found workflow config for ${workflow}:`, workflowConfig);

        // For workflows with patterns like RTX
        if (typeof workflowConfig === 'object' && !workflowConfig.command_template) {
            console.log('Processing pattern-based workflow config');
            // Find matching pattern for this library prep method
            for (const [pattern, config] of Object.entries(workflowConfig)) {
                console.log(`Checking pattern: ${pattern}`);
                if (pattern.includes('|')) {
                    // Multi-value pattern (separated by |)
                    const patterns = pattern.split('|');
                    if (patterns.includes(libraryPrepMethod)) {
                        commandTemplate = config.command_template;
                        console.log(`Found matching multi-pattern template: ${commandTemplate}`);
                        break;
                    }
                } else if (pattern === libraryPrepMethod) {
                    // Single value pattern
                    commandTemplate = config.command_template;
                    console.log(`Found matching single pattern template: ${commandTemplate}`);
                    break;
                }
            }
        } else {
            // For workflows with direct command_template like MTX
            console.log('Processing direct command template workflow');
            commandTemplate = workflowConfig.command_template;
            console.log(`Found direct command template: ${commandTemplate}`);
        }

        // Use fallback if still no template found for MTX
        if (!commandTemplate && workflow.toLowerCase() === 'mtx' && fallbackTemplates.mtx[stage]) {
            console.log(`No template found in config for MTX ${stage}, using fallback`);
            commandTemplate = fallbackTemplates.mtx[stage];
        }

        if (!commandTemplate) {
            console.error(`No command template found for ${workflow} ${stage} with library prep method ${libraryPrepMethod}`);
        }

        return commandTemplate;
    }

    generateCommandFromTemplate(template, sample) {
        if (!template) return '';

        const reference = this.getReference(sample.organism_common_name || '');
        const libraryPrep = sample.library_prep_method || '';
        const chemistry = this.getChemistry(libraryPrep);
        const notificationEmail = this.getNotificationEmail();
        const loadName = sample.load_name || '';

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
                    console.log(`Using default chemistry: ${defaultChemistry}`);
                    command = command.replace(/{chemistry}/g, defaultChemistry);
                } else {
                    // If no chemistry available, remove the chemistry parameter entirely
                    command = command.replace(/--chemistry\s+{chemistry}/g, '');
                }
            }
        }

        // Log the generated command
        console.log(`Generated command for ${sample.load_name}:`, command);
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
            console.log('Unknown library prep method for RTX workflow, returning empty command');
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
        console.log('Generated command:', command);
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
            console.log('Unknown library prep method for RTX workflow, returning empty command');
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
        console.log('Generated command:', command);
        return command;
    }

    handleSubmission() {
        console.log('handleSubmission started');
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
                let command = row.querySelector('.command-cell code')?.textContent?.trim();
                if (!command) {
                    const commandInput = row.querySelector('.command-edit-form textarea[name="command"]');
                    if (commandInput) {
                        command = commandInput.value.trim();
                    }
                }
                if (command && sampleId) {
                    let sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === sampleId);
                    if (!sample) sample = { batch_name_from_vendor: '', workflow: '', fastq_name: sampleId, alignment_status: '' };
                    const workflow = sample.workflow || this.determineWorkflow(sample);
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
                    if (!sample) sample = { batch_name_from_vendor: '', workflow: '', fastq_name: sampleId };
                    const workflow = sample.workflow || this.determineWorkflow(sample);

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
        console.log('Storage Data Structure:', { commands });

        // Hide the submit modal
        const modalInstance = bootstrap.Modal.getInstance(this.modal);
        if (modalInstance) {
            modalInstance.hide();
            setTimeout(() => {
                if (window.pipelineFinalModal) {
                    window.pipelineFinalModal.show({ commands });
                    const finalModal = document.querySelector('.final-modal');
                    if (finalModal) {
                        const closeButtons = finalModal.querySelectorAll('.btn-close, .btn-cancel');
                        closeButtons.forEach(btn => {
                            btn.addEventListener('click', () => {
                                console.log('Close/cancel button clicked in final modal, hiding backdrop');
                                this.hideGlobalBackdrop();
                            }, { once: true });
                        });
                    }
                }
            }, 50);
            return;
        }
        if (window.pipelineFinalModal) {
            window.pipelineFinalModal.show({ commands });
        }
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

    isLibraryPrepMethodKnown(libraryPrepMethod) {
        if (!libraryPrepMethod || !this.config || !this.config.workflows || !this.config.workflows.rtx) {
            return false;
        }

        const rtxConfig = this.config.workflows.rtx;
        console.log('Checking if library prep method is known:', libraryPrepMethod);

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
                    console.log(`Library prep method ${libraryPrepMethod} found in alignment pattern: ${pattern}`);
                    return true;
                }
            }
        }

        // Check post-QC patterns 
        if (rtxConfig.postqc) {
            for (const pattern of Object.keys(rtxConfig.postqc)) {
                if (matchesPattern(pattern)) {
                    console.log(`Library prep method ${libraryPrepMethod} found in postqc pattern: ${pattern}`);
                    return true;
                }
            }
        }

        console.log(`Library prep method ${libraryPrepMethod} is unknown`);
        return false;
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
                        ${Array.from(unknownSamples.entries()).map(([libraryPrepMethod, samples]) => `
                            <div class="unknown-libprep-card" data-library-prep-method="${libraryPrepMethod}" data-stage="${stage}">
                                <div class="unknown-libprep-card-header">
                                    <div class="d-flex align-items-center gap-2">
                                        <span class="badge bg-warning text-dark">${libraryPrepMethod}</span>
                                        <span class="text-muted">(${samples.length} sample${samples.length !== 1 ? 's' : ''})</span>
                                    </div>
                                </div>
                                <div class="unknown-libprep-card-body">
                                    <div class="asset-selector-container">
                                        ${this.createAssetSelector(stage, libraryPrepMethod)}
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
                        `).join('')}
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
                        const selectedAsset = event.target.value;

                        console.log('Asset selected:', { libraryPrepMethod, stage, selectedAsset });

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

                        console.log('Additional option changed:', { libraryPrepMethod, stage, selectedAsset });
                        this.updateUnknownLibPrepCommands(stage, libraryPrepMethod, selectedAsset);
                    }
                });
            }
        });
    }

    createAssetSelector(stage, libraryPrepMethod) {
        const assets = this.getAvailableAssets(stage);

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

    getAvailableAssets(stage) {
        // If no config is available, return an empty array
        if (!this.config?.workflows?.rtx?.[stage]) {
            console.warn('No RTX workflow config available for stage:', stage);
            return [];
        }

        try {
            const rtxConfig = this.config.workflows.rtx[stage];
            const assets = new Set();

            // Extract unique asset names from the config
            for (const [pattern, config] of Object.entries(rtxConfig)) {
                if (config && typeof config === 'object' && config.asset_name) {
                    assets.add(config.asset_name);
                }
            }

            // For post-QC stage, always include tenx_rnaseq_qc
            if (stage === 'postqc') {
                assets.add('tenx_rnaseq_qc');
            }

            // Sort assets alphabetically for consistent display
            const sortedAssets = Array.from(assets).sort();
            console.log(`Available assets for ${stage}:`, sortedAssets);
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
        console.log(`Stored original ${stage} command:`, command);
    }

    updateUnknownLibPrepCommands(stage, libraryPrepMethod, selectedAsset) {
        console.log(`Updating commands for ${stage} with library prep method ${libraryPrepMethod}, selected asset: ${selectedAsset}`);

        // Get the container for this library prep method
        const container = this.modal.querySelector(`.unknown-libprep-card[data-stage="${stage}"][data-library-prep-method="${libraryPrepMethod}"]`);
        if (!container) {
            console.error(`Could not find container for ${stage} ${libraryPrepMethod}`);
            return;
        }

        // Get the asset tag input value
        const assetTagInput = container.querySelector('.asset-tag-input');
        const assetTag = assetTagInput ? assetTagInput.value.trim() : '';
        console.log(`Asset tag: ${assetTag}`);

        // Get all affected samples
        const affectedSamples = this.unknownLibraryPrepMethodSamples[stage].get(libraryPrepMethod) || [];
        console.log(`Found ${affectedSamples.length} affected samples`);

        // If no asset is selected, clear commands for all affected samples
        if (!selectedAsset) {
            console.log('No asset selected, clearing commands');
            affectedSamples.forEach(sample => {
                const rowSelector = `tr[data-sample="${sample.fastq_name}"][data-stage="${stage}"]`;
                console.log(`Looking for command cell with selector: ${rowSelector}`);
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

        // Find the appropriate command template from the config
        let commandTemplate = '';
        let workflow = 'rtx';

        // For post-QC stage, check if we should use MTX workflow for the template
        if (stage === 'postqc' && selectedAsset === 'multi_gex_qc') {
            workflow = 'mtx';
        }

        // Look for a template matching the selected asset
        if (this.config?.workflows?.[workflow]) {
            const workflowConfig = this.config.workflows[workflow][stage];

            if (typeof workflowConfig === 'object') {
                // For direct command_template like MTX
                if (workflowConfig.asset_name === selectedAsset) {
                    commandTemplate = workflowConfig.command_template;
                    console.log(`Found simple template for ${workflow} ${stage} with asset ${selectedAsset}: ${commandTemplate}`);
                }
                // For pattern-based configs like RTX
                else if (!workflowConfig.command_template) {
                    for (const [pattern, config] of Object.entries(workflowConfig)) {
                        if (config.asset_name === selectedAsset) {
                            commandTemplate = config.command_template;
                            console.log(`Found pattern-based template for ${selectedAsset}: ${commandTemplate}`);
                            break;
                        }
                    }
                }
            }
        }

        if (!commandTemplate) {
            console.error(`No command template found for ${workflow} ${stage} with asset ${selectedAsset}`);
            return;
        }

        // Update command for each affected sample
        affectedSamples.forEach(sample => {
            console.log(`Processing sample: ${sample.fastq_name}`);
            const rowSelector = `tr[data-sample="${sample.fastq_name}"][data-stage="${stage}"]`;
            console.log(`Looking for command cell with selector: ${rowSelector}`);
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

            // Generate command from template
            const command = this.generateCommandFromTemplate(commandTemplate, sample);
            console.log(`Generated command for ${sample.fastq_name}: ${command}`);
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

        // If preserveBaseCommand is true, use the entire base command as is
        let command = preserveBaseCommand ? baseCommand : `${baseCommand.split('--asset-name')[0].trim()} --asset-name ${assetName}`;

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

    updateCommandPreview(form) {
        const cell = form.closest('.command-cell');
        const row = cell.closest('tr');
        const fastqName = row.querySelector('td:first-child').textContent.trim();
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

        const isAlignment = stage === 'alignment';
        const isPostQC = stage === 'postqc';
        const baseCommand = form.querySelector('.command-input').value;

        // Get asset tag for post-QC
        const assetTag = isPostQC ? form.querySelector('.asset-tag-input')?.value?.trim() : '';

        // Extract asset name from base command
        const assetNameMatch = baseCommand.match(/--asset-name\s+([^\s]+)/);
        const assetName = assetNameMatch ? assetNameMatch[1] : '';
        console.log('Extracted asset name:', assetName);

        // Get form values
        const referenceSelect = form.querySelector('.reference-select');
        const chemistrySelect = form.querySelector('.chemistry-select');
        const includeIntronsCheck = form.querySelector('.include-introns');
        const executionPriorityCheck = form.querySelector('.execution-priority');

        // Build the command
        let newCommand;

        if (isPostQC) {
            // For post-QC, specially handle asset tag
            let processedBaseCommand = baseCommand;

            // Remove existing asset tag if present
            processedBaseCommand = processedBaseCommand.replace(/--asset-tag\s+[^\s]+/, '').trim();

            // Add load names and notifications
            newCommand = `${processedBaseCommand} ${assetTag ? `--asset-tag ${assetTag} ` : ''}--load-names "${sample.load_name}" --notify-on FAILED --notify ${this.getNotificationEmail()}`;
        } else {
            // For alignment, use the regular build method
            newCommand = this.buildCommand(baseCommand, sample, {
                reference: referenceSelect?.value,
                chemistry: chemistrySelect?.value,
                includeIntrons: includeIntronsCheck?.checked,
                executionPriority: executionPriorityCheck?.checked,
                isAlignment,
                assetName,
                assetTag: '',  // Not used for alignment
                preserveBaseCommand: true
            });
        }

        console.log('Generated command:', {
            baseCommand,
            assetName,
            assetTag: isPostQC ? assetTag : '',
            newCommand
        });

        // Update the command display
        const codeElement = cell.querySelector('code');
        codeElement.textContent = newCommand;

        // Update the command in the sample data
        if (stage === 'alignment') {
            sample.alignmentCommand = newCommand;
        } else {
            sample.postQCCommand = newCommand;
        }
    }

    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
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
        console.log('Saving submit modal state');

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
            console.log('No saved state to restore');
            return;
        }

        console.log('Restoring submit modal state');

        // First restore basic settings
        if (this.autoProceedToggle) {
            this.autoProceedToggle.checked = this.savedState.autoProceed;
        }

        const includeIncompleteCheckbox = document.getElementById('include-incomplete-samples');
        if (includeIncompleteCheckbox) {
            includeIncompleteCheckbox.checked = this.savedState.includeIncomplete;
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

        console.log('State restored successfully');
    }

    setupModalCloseHandlers() {
        // Handle ESC key press
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                const modalInstance = bootstrap.Modal.getInstance(this.modal);
                if (modalInstance) {
                    modalInstance.hide();
                    console.log('ESC key pressed to close submit modal, hiding backdrop');
                    this.hideGlobalBackdrop();
                }
            }
        });

        // Handle clicking outside the modal
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                const modalInstance = bootstrap.Modal.getInstance(this.modal);
                if (modalInstance) {
                    modalInstance.hide();
                    console.log('Clicked outside submit modal, hiding backdrop');
                    this.hideGlobalBackdrop();
                }
            }
        });
    }

    // Add method to expose backdrop showing for external callers
    showBackdropForSubmitSelected() {
        console.log('Submit Selected button clicked in dashboard, showing backdrop');
        this.showGlobalBackdrop();
    }
}

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', () => {
    const style = document.createElement('style');
    style.textContent = `
        /* ... existing styles ... */
        
        /* Global backdrop styling */
        .global-backdrop {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            left: 0;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 1030; /* Lower than bootstrap modals */
            display: none;
        }
        
        /* Fix for modal display */
        .modal {
            z-index: 1050 !important;
        }
        
        /* Hide bootstrap modal backdrops */
        .modal-backdrop {
            display: none !important;
        }
    `;
    document.head.appendChild(style);

    // Initialize the modal handler
    window.pipelineSubmitModal = new PipelineSubmitModal();

    // Listen for submit button click from dashboard
    const submitActionBtn = document.getElementById('submit-action-btn');
    if (submitActionBtn) {
        submitActionBtn.addEventListener('click', () => {
            // Show backdrop when submit selected is clicked
            if (window.pipelineSubmitModal) {
                window.pipelineSubmitModal.showBackdropForSubmitSelected();
            }
        });
    }
}); 