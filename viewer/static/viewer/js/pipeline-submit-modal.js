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

        // Sample tracking
        this.alignmentSamples = [];
        this.postQCSamples = [];
        this.incompleteSamples = [];
        this.unknownLibraryPrepMethodSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // Configuration will be loaded from server
        this.config = null;

        this.setupEventListeners();
        this.loadConfig();

        // Add styles for unknown library prep UI
        this.addStyles();
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
            console.log('Settings:', this.config.settings);

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

        return Object.entries(this.config.chemistries).map(([prep, chemistry]) => ({
            name: `${chemistry} (${prep})`,
            value: chemistry,
            prep: prep
        }));
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
        console.log('Getting reference for organism:', organism);
        if (!this.config?.references) {
            console.error('References not loaded in config');
            return '';
        }

        const normalizedOrganism = organism.toLowerCase().replace(/\s+/g, '_');
        const reference = this.config.references[normalizedOrganism] || this.config.references.human || '';
        console.log('Found reference:', reference);
        return reference;
    }

    getChemistry(libraryPrep) {
        console.log('Getting chemistry for library prep:', libraryPrep);
        if (!this.config?.chemistries) {
            console.error('Chemistries not loaded in config');
            return '';
        }

        const chemistry = this.config.chemistries[libraryPrep] || '';
        console.log('Found chemistry:', chemistry);
        return chemistry;
    }

    setupEventListeners() {
        // Handle modal show event
        this.modal.addEventListener('show.bs.modal', (event) => {
            this.populateModal();
        });

        // Handle modal hidden event to ensure cleanup
        this.modal.addEventListener('hidden.bs.modal', (event) => {
            // Remove backdrop if it's still present
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) {
                backdrop.remove();
            }
            // Remove modal-open class from body
            document.body.classList.remove('modal-open');
            // Remove inline styles from body
            document.body.removeAttribute('style');
        });

        // Handle auto-proceed toggle change
        if (this.autoProceedToggle) {
            this.autoProceedToggle.addEventListener('change', () => {
                this.updateCommandLists();
            });
        }

        // Handle confirm button click
        this.confirmButton.addEventListener('click', () => {
            this.handleSubmission();
        });

        // Edit button click
        this.modal.addEventListener('click', (e) => {
            const editButton = e.target.closest('.edit-command');
            if (editButton) {
                e.preventDefault();
                const cell = editButton.closest('.command-cell');
                const row = cell.closest('tr');
                const command = cell.querySelector('code').textContent;
                const stage = cell.closest('.batch-group')?.dataset.stage || 'alignment';
                const fastqName = row.querySelector('td:first-child').textContent.trim();

                console.log('Edit button clicked:', {
                    fastqName,
                    stage,
                    command
                });

                // Find the sample data
                let sample;
                if (stage === 'alignment') {
                    sample = [...this.alignmentSamples, ...this.incompleteSamples].find(s => s.fastq_name === fastqName);
                } else {
                    sample = this.postQCSamples.find(s => s.fastq_name === fastqName);
                }

                console.log('Found sample:', sample);

                const form = cell.querySelector('.command-edit-form');
                console.log('Current command before edit:', command);

                // Parse the command to check flags
                const parsedCommand = this.parseCommand(command, stage === 'alignment', this.determineWorkflow(sample) === 'MTX');
                console.log('Parsed command values:', parsedCommand);

                // Toggle the form visibility
                if (form.classList.contains('show')) {
                    form.classList.remove('show');
                } else {
                    // Hide any other open forms first
                    this.modal.querySelectorAll('.command-edit-form.show').forEach(openForm => {
                        openForm.classList.remove('show');
                    });
                    form.classList.add('show');

                    // Explicitly set checkbox states after form is shown
                    const includeIntronsCheckbox = form.querySelector('.include-introns');
                    const executionPriorityCheckbox = form.querySelector('.execution-priority');

                    if (includeIntronsCheckbox) {
                        includeIntronsCheckbox.checked = parsedCommand.includeIntrons === true;
                        console.log('Setting include-introns checkbox:', {
                            parsedValue: parsedCommand.includeIntrons,
                            checkboxState: includeIntronsCheckbox.checked
                        });
                    }

                    if (executionPriorityCheckbox) {
                        executionPriorityCheckbox.checked = parsedCommand.executionPriority === true;
                        console.log('Setting execution-priority checkbox:', {
                            parsedValue: parsedCommand.executionPriority,
                            checkboxState: executionPriorityCheckbox.checked
                        });
                    }

                    // Verify final checkbox states
                    console.log('Final checkbox states:', {
                        includeIntrons: includeIntronsCheckbox?.checked,
                        executionPriority: executionPriorityCheckbox?.checked,
                        includeIntronsExists: !!includeIntronsCheckbox,
                        executionPriorityExists: !!executionPriorityCheckbox
                    });
                }
            }
        });

        // Cancel button click
        this.modal.addEventListener('click', (e) => {
            const cancelButton = e.target.closest('.cancel-edit');
            if (cancelButton) {
                e.preventDefault();
                const form = cancelButton.closest('.command-edit-form');
                form.classList.remove('show');
            }
        });

        // Save button click
        this.modal.addEventListener('click', (e) => {
            const saveButton = e.target.closest('.save-command');
            if (saveButton) {
                e.preventDefault();
                const form = saveButton.closest('.command-edit-form');
                const cell = form.closest('.command-cell');
                const row = cell.closest('tr');
                const fastqName = row.querySelector('td:first-child').textContent.trim();
                const batchGroup = cell.closest('.batch-group');
                const stage = batchGroup ? batchGroup.dataset.stage : 'alignment';

                // Find the sample data from our tracked samples
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
                const workflow = this.determineWorkflow(sample);
                const isArc = workflow === 'MTX';

                // Get form values
                const baseCommand = form.querySelector('.command-input').value;
                const referenceSelect = form.querySelector('.reference-select');
                const chemistrySelect = form.querySelector('.chemistry-select');
                const includeIntronsCheck = form.querySelector('.include-introns');
                const executionPriorityCheck = form.querySelector('.execution-priority');

                // Build the command
                let newCommand = baseCommand;

                // Add reference if selected
                if (referenceSelect && referenceSelect.value) {
                    newCommand += ` --reference-names "${referenceSelect.value}"`;
                }

                // Add load name
                newCommand += ` --load-names "${sample.load_name}"`;

                // Add chemistry and include-introns for alignment
                if (isAlignment) {
                    if (chemistrySelect && chemistrySelect.value) {
                        newCommand += ` --cellranger-addopts "--chemistry ${chemistrySelect.value}${includeIntronsCheck && includeIntronsCheck.checked ? ' --include-introns' : ''}"`;
                    }

                    // Add execution priority if checked
                    if (executionPriorityCheck && executionPriorityCheck.checked) {
                        newCommand += ' --execution-priority HIGH';
                    }
                }

                // Add notification settings
                newCommand += ' --notify-on FAILED';
                const email = this.getNotificationEmail();
                if (email) {
                    newCommand += ` --notify ${email}`;
                }

                // Update the command display
                const codeElement = cell.querySelector('code');
                codeElement.textContent = newCommand;

                // Update the command in the sample data
                if (stage === 'alignment') {
                    sample.alignmentCommand = newCommand;
                } else {
                    sample.postQCCommand = newCommand;
                }

                // Hide the form
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
                const stage = batchGroup ? batchGroup.dataset.stage : 'alignment';

                console.log('Reset context:', {
                    fastqName,
                    stage,
                    batchGroup: batchGroup ? batchGroup.dataset.batchName : 'none'
                });

                // Find the sample data from our tracked samples
                let sample;
                if (stage === 'alignment') {
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

                console.log('Found sample:', {
                    fastqName: sample.fastq_name,
                    libraryPrepMethod: sample.library_prep_method,
                    workflow: this.determineWorkflow(sample)
                });

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
                                if (templateType === 'standard') {
                                    commandTemplate = 'ocs fastqs align tenx-rnaseq --asset-name cellranger-rnaseq --reference-names "{reference}"' +
                                        (assetTag ? ` --asset-tag ${assetTag}` : '') +
                                        ' --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry} --include-introns" --notify-on FAILED --notify {notification_email}';
                                } else {
                                    commandTemplate = 'ocs fastqs align tenx-rnaseq --asset-name cellranger-rnaseq --reference-names "{reference}"' +
                                        (assetTag ? ` --asset-tag ${assetTag}` : '') +
                                        ' --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry}" --notify-on FAILED --notify {notification_email}';
                                }
                            } else if (selectedAsset === 'cellranger-multi') {
                                commandTemplate = 'ocs fastqs align tenx-rnaseq-multi --asset-name cellranger-multi --reference-names "{reference}" --load-names "{load_name}" --cellranger-addopts \'--include-introns\' --execution-priority HIGH --notify-on FAILED --notify {notification_email}';
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

                // For known library preps or when no asset is selected for unknown preps
                const originalCommand = stage === 'alignment' ?
                    this.generateAlignmentCommand(sample) :
                    this.generatePostQCCommand(sample);

                console.log('Generated original command:', originalCommand);

                // Update the command display
                const codeElement = cell.querySelector('code');
                codeElement.textContent = originalCommand;

                // Update the command in the sample data
                if (stage === 'alignment') {
                    sample.alignmentCommand = originalCommand;
                } else {
                    sample.postQCCommand = originalCommand;
                }

                console.log('Command reset complete');
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
                selectedSamples.push(sample);
            }
        });

        // Populate the table
        selectedSamples.forEach(sample => {
            const row = document.createElement('tr');
            row.dataset.sample = sample.load_name;

            // Extract values from sample data
            const fastqName = sample.fastq_name || '';
            const loadName = sample.load_name || '';
            const workflow = this.determineWorkflow(sample);
            const organism = sample.organism_common_name || '';
            const libraryPrepMethod = sample.library_prep_method || '';
            const ingestStatus = sample.ingest_status || 'Not started';
            const alignmentStatus = sample.alignment_status || 'Not started';
            const postQCStatus = sample.postqc_status || 'Not Started';

            // Categorize the sample based on status (case-insensitive comparison)
            if (ingestStatus.toLowerCase() === 'not started') {
                this.incompleteSamples.push(sample);
            } else if (alignmentStatus.toLowerCase() !== 'completed' && ingestStatus.toLowerCase() === 'completed') {
                this.alignmentSamples.push(sample);
            } else if (postQCStatus.toLowerCase() !== 'completed' && alignmentStatus.toLowerCase() === 'completed') {
                this.postQCSamples.push(sample);
            }

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
            console.log('Config not loaded yet, waiting before processing library prep methods');
            this.loadConfig().then(() => {
                this.processUnknownLibraryPreps(selectedSamples);
                this.updateCommandLists();
                this.addUnknownLibPrepWarnings();
            });
        } else {
            // Process unknown library preps
            this.processUnknownLibraryPreps(selectedSamples);
            // Update the command lists
            this.updateCommandLists();
            // Add unknown library prep warnings if needed
            this.addUnknownLibPrepWarnings();
        }
    }

    processUnknownLibraryPreps(samples) {
        console.log('Processing unknown library preps for', samples.length, 'samples');

        // Only track unknown library preps for RTX workflow
        samples.forEach(sample => {
            const workflow = this.determineWorkflow(sample);
            if (workflow === 'RTX') {
                const libraryPrepMethod = sample.library_prep_method || '';
                console.log(`Checking if ${libraryPrepMethod} is known for sample ${sample.fastq_name}`);
                const isLibraryPrepMethodKnown = this.isLibraryPrepMethodKnown(libraryPrepMethod);
                console.log(`${libraryPrepMethod} is ${isLibraryPrepMethodKnown ? 'known' : 'unknown'}`);

                if (!isLibraryPrepMethodKnown) {
                    if (sample.ingest_status.toLowerCase() === 'completed' &&
                        sample.alignment_status.toLowerCase() !== 'completed') {
                        // Unknown library prep for alignment
                        console.log(`Adding ${sample.fastq_name} with library prep method ${libraryPrepMethod} to alignment unknown list`);
                        if (!this.unknownLibraryPrepMethodSamples.alignment.has(libraryPrepMethod)) {
                            this.unknownLibraryPrepMethodSamples.alignment.set(libraryPrepMethod, []);
                        }
                        this.unknownLibraryPrepMethodSamples.alignment.get(libraryPrepMethod).push(sample);
                    } else if (sample.alignment_status.toLowerCase() === 'completed' &&
                        sample.postqc_status.toLowerCase() !== 'completed') {
                        // Unknown library prep for postqc
                        console.log(`Adding ${sample.fastq_name} with library prep method ${libraryPrepMethod} to postqc unknown list`);
                        if (!this.unknownLibraryPrepMethodSamples.postqc.has(libraryPrepMethod)) {
                            this.unknownLibraryPrepMethodSamples.postqc.set(libraryPrepMethod, []);
                        }
                        this.unknownLibraryPrepMethodSamples.postqc.get(libraryPrepMethod).push(sample);
                    }
                }
            }
        });

        // Log the detected unknown library preps
        console.log('Unknown library prep method samples for alignment:',
            Array.from(this.unknownLibraryPrepMethodSamples.alignment.keys()));
        console.log('Unknown library prep method samples for postqc:',
            Array.from(this.unknownLibraryPrepMethodSamples.postqc.keys()));
    }

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

        // Add unknown library prep warnings if needed
        this.addUnknownLibPrepWarnings();
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
                        ${samples.map(sample => this.createSampleRow(sample, 'postqc')).join('')}
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

    createSampleRow(sample, stage) {
        const workflow = this.determineWorkflow(sample);
        const command = stage === 'alignment' ?
            this.generateAlignmentCommand(sample) :
            this.generatePostQCCommand(sample);

        return `
            <tr data-sample="${sample.load_name}" data-stage="${stage}">
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
            sample,
            stage,
            command
        });

        const isAlignment = stage === 'alignment';
        const workflow = this.determineWorkflow(sample);
        const isArc = workflow === 'MTX';

        // Parse the command to extract current values
        const currentValues = this.parseCommand(command, isAlignment, isArc);
        console.log('Current values for form creation:', currentValues);

        // Get the base command based on workflow and stage
        let baseCommand = '';
        if (isAlignment) {
            if (isArc) {
                baseCommand = 'ocs fastqs align tenx-rnaseq-multi --asset-name cellranger-multi';
            } else {
                baseCommand = 'ocs fastqs align tenx-rnaseq --asset-name cellranger-rnaseq';
            }
        } else {
            if (isArc) {
                baseCommand = 'ocs fastqs postalign tenx-arc --asset-name multi_gex_qc';
            } else {
                baseCommand = 'ocs fastqs postalign tenx-rnaseq --asset-name tenx_rnaseq_qc';
            }
        }

        // Get the organism for default reference selection
        const organism = sample.organism_common_name || '';
        const defaultReference = this.getReference(organism);

        console.log('Form generation values:', {
            baseCommand,
            currentValues,
            isAlignment,
            workflow,
            isArc
        });

        const formHtml = `
            <div class="command-edit-form">
                <div class="mb-3">
                    <label class="form-label">Base Command</label>
                    <input type="text" class="form-control command-input" value="${baseCommand}">
                </div>
                ${isAlignment ? `
                    <div class="mb-3">
                        <label class="form-label">Reference</label>
                        <select class="form-select reference-select">
                            ${this.getReferences().map(ref =>
            `<option value="${ref.value}" ${ref.value === defaultReference ? 'selected' : ''}>
                                    ${ref.name}
                                </option>`
        ).join('')}
                        </select>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Chemistry</label>
                        <select class="form-select chemistry-select">
                            ${this.getChemistries().map(chem =>
            `<option value="${chem.value}" ${chem.prep === sample.library_prep_method ? 'selected' : ''}>
                                    ${chem.name}
                                </option>`
        ).join('')}
                        </select>
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input include-introns" type="checkbox" ${currentValues.includeIntrons === true ? 'checked="checked"' : ''}>
                            <label class="form-check-label">Include introns</label>
                        </div>
                    </div>
                    <div class="mb-3">
                        <div class="form-check">
                            <input class="form-check-input execution-priority" type="checkbox" ${currentValues.executionPriority === true ? 'checked="checked"' : ''}>
                            <label class="form-check-label">High execution priority</label>
                        </div>
                    </div>
                ` : ''}
                <div class="d-flex justify-content-end gap-2">
                    <button class="btn btn-secondary cancel-edit">Cancel</button>
                    <button class="btn btn-primary save-command">Save</button>
                </div>
            </div>
        `;

        console.log('Generated form HTML with explicit checkbox states:', {
            includeIntronsChecked: currentValues.includeIntrons === true ? 'checked="checked"' : '',
            executionPriorityChecked: currentValues.executionPriority === true ? 'checked="checked"' : ''
        });

        return formHtml;
    }

    parseCommand(command, isAlignment, isArc) {
        console.log('Parsing command:', command);
        console.log('isAlignment:', isAlignment, 'isArc:', isArc);

        const values = {
            reference: '',
            chemistry: '',
            includeIntrons: false,
            executionPriority: false,
            notificationEmail: ''
        };

        // Extract reference
        const referenceMatch = command.match(/--reference-names\s+"([^"]+)"/);
        console.log('Reference match:', referenceMatch);
        if (referenceMatch) {
            values.reference = referenceMatch[1];
        }

        // Extract chemistry and include-introns from cellranger-addopts
        // Handle both single and double quotes
        const cellrangerAddoptsMatch = command.match(/--cellranger-addopts\s+['"]([^'"]+)['"]/);
        console.log('Cellranger addopts match:', cellrangerAddoptsMatch);
        if (cellrangerAddoptsMatch) {
            const addopts = cellrangerAddoptsMatch[1];
            console.log('Parsed addopts:', addopts);

            // Extract chemistry from addopts
            const chemistryMatch = addopts.match(/--chemistry\s+([^\s"']+)/);
            console.log('Chemistry match:', chemistryMatch);
            if (chemistryMatch) {
                values.chemistry = chemistryMatch[1];
            }
            // Check for include-introns in addopts
            values.includeIntrons = addopts.includes('--include-introns');
            console.log('Include introns from addopts:', values.includeIntrons);
        }

        // Also check for include-introns directly in the command (for MTX workflow)
        if (!values.includeIntrons) {
            values.includeIntrons = command.includes('--include-introns');
            console.log('Include introns from direct command:', values.includeIntrons);
        }

        // Check for execution priority
        values.executionPriority = command.includes('--execution-priority HIGH');
        console.log('Execution priority:', values.executionPriority);

        // Extract notification email
        const notifyMatch = command.match(/--notify\s+([^\s]+)/);
        if (notifyMatch) {
            values.notificationEmail = notifyMatch[1];
        }

        console.log('Final parsed values:', values);
        return values;
    }

    determineWorkflow(sample) {
        // Get batch name from vendor, default to empty string if not present
        const batchName = (sample.batch_name_from_vendor || '').toUpperCase();

        // Check for MTX workflow
        if (batchName.startsWith('MTX') || batchName.includes('ATX')) {
            return 'MTX';
        }

        // Check for RTX workflow
        if (batchName.startsWith('RTX') || !batchName.includes('-')) {
            return 'RTX';
        }

        // Default to RTX for unrecognized patterns
        return 'RTX';
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

    generateAlignmentCommand(sample) {
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const loadName = sample.load_name || '';
        const organism = sample.organism_common_name || '';
        const reference = this.getReference(organism);
        const libraryPrepMethod = sample.library_prep_method || '';
        const notificationEmail = this.getNotificationEmail();

        // Check if this is an unknown library prep method
        if (workflow === 'RTX' && !this.isLibraryPrepMethodKnown(libraryPrepMethod)) {
            // For unknown library preps, return empty command until user selects an asset
            return '';
        }

        if (!this.config?.workflows?.[workflow.toLowerCase()]?.alignment) {
            console.error(`No workflow configuration found for ${workflow} alignment`);
            return '';
        }

        // Get command template from config
        let commandTemplate = '';
        const workflowConfig = this.config.workflows[workflow.toLowerCase()].alignment;

        // For workflows with patterns like RTX
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
            // For workflows with direct command_template like MTX
            commandTemplate = workflowConfig.command_template;
        }

        if (!commandTemplate) {
            console.error(`No command template found for ${workflow} alignment with library prep method ${libraryPrepMethod}`);
            return '';
        }

        // Replace placeholders in the template
        let command = commandTemplate
            .replace(/{reference}/g, reference)
            .replace(/{load_name}/g, loadName)
            .replace(/{notification_email}/g, notificationEmail);

        // Replace chemistry placeholder if present in template
        if (command.includes('{chemistry}')) {
            const chemistry = this.getChemistry(libraryPrepMethod);
            if (chemistry) {
                command = command.replace(/{chemistry}/g, chemistry);
            } else {
                console.warn(`No chemistry found for library prep method: ${libraryPrepMethod}`);
                // If no chemistry, remove the chemistry parameter entirely
                command = command.replace(/--chemistry\s+{chemistry}/g, '');
            }
        }

        return command;
    }

    generatePostQCCommand(sample) {
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const loadName = sample.load_name || '';
        const libraryPrepMethod = sample.library_prep_method || '';
        const notificationEmail = this.getNotificationEmail();

        if (!this.config?.workflows?.[workflow.toLowerCase()]?.postqc) {
            console.error(`No workflow configuration found for ${workflow} post-QC`);
            return '';
        }

        // Get command template from config
        let commandTemplate = '';
        const workflowConfig = this.config.workflows[workflow.toLowerCase()].postqc;

        // For workflows with patterns like RTX
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
            // For workflows with direct command_template like MTX
            commandTemplate = workflowConfig.command_template;
        }

        if (!commandTemplate) {
            console.error(`No command template found for ${workflow} post-QC with library prep method ${libraryPrepMethod}`);
            return '';
        }

        // Replace placeholders in the template
        return commandTemplate
            .replace(/{load_name}/g, loadName)
            .replace(/{notification_email}/g, notificationEmail);
    }

    handleSubmission() {
        // Get the bootstrap modal instance
        const modalInstance = bootstrap.Modal.getInstance(this.modal);

        // Show processing state
        this.confirmButton.disabled = true;
        this.confirmButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Processing...';

        // Collect all custom commands from the interface
        const commands = {
            alignment: [],
            postqc: []
        };

        // Collect alignment commands
        const alignmentBuilders = this.alignmentBatches.querySelectorAll('.command-cell');
        alignmentBuilders.forEach(cell => {
            const command = cell.querySelector('code').textContent.trim();
            const sample = cell.closest('tr').dataset.sample;

            commands.alignment.push({
                sample,
                command
            });
        });

        // Collect post-QC commands (excluding those already added from auto-proceed)
        const postQCBuilders = this.postQCBatches.querySelectorAll('.command-cell');
        postQCBuilders.forEach(cell => {
            const command = cell.querySelector('code').textContent.trim();
            const sample = cell.closest('tr').dataset.sample;

            // Check if this sample's post-QC is already in the list (from auto-proceed)
            const exists = commands.postqc.some(item => item.sample === sample);
            if (!exists) {
                commands.postqc.push({
                    sample,
                    command
                });
            }
        });

        // Log collected commands for debugging
        console.log('Collected commands:', commands);

        // Simulate API call (replace with actual API call)
        setTimeout(() => {
            // Success handling
            modalInstance.hide();

            // Show success notification
            if (window.pipelineLocalData && typeof window.pipelineLocalData.showToastNotification === 'function') {
                window.pipelineLocalData.showToastNotification('Samples submitted successfully', 'success');
            }

            // Reset button state
            this.confirmButton.disabled = false;
            this.confirmButton.innerHTML = 'Confirm and Submit';

            // Clear selected samples
            if (window.pipelineLocalData) {
                window.pipelineLocalData.clearSelectedSamples();
            }
        }, 1000);
    }

    isLibraryPrepMethodKnown(libraryPrepMethod) {
        if (!libraryPrepMethod || !this.config || !this.config.workflows || !this.config.workflows.rtx) {
            return false;
        }

        const rtxConfig = this.config.workflows.rtx;
        console.log('Checking if library prep method is known:', libraryPrepMethod);

        // Check alignment patterns
        if (rtxConfig.alignment) {
            for (const pattern of Object.keys(rtxConfig.alignment)) {
                if (pattern.includes('|')) {
                    const patterns = pattern.split('|');
                    if (patterns.some(p => p.trim() === libraryPrepMethod)) {
                        console.log(`Library prep method ${libraryPrepMethod} found in alignment pattern: ${pattern}`);
                        return true;
                    }
                } else if (pattern.trim() === libraryPrepMethod) {
                    console.log(`Library prep method ${libraryPrepMethod} found as exact alignment pattern`);
                    return true;
                }
            }
        }

        // Check post-QC patterns 
        if (rtxConfig.postqc) {
            for (const pattern of Object.keys(rtxConfig.postqc)) {
                if (pattern.includes('|')) {
                    const patterns = pattern.split('|');
                    if (patterns.some(p => p.trim() === libraryPrepMethod)) {
                        console.log(`Library prep method ${libraryPrepMethod} found in postqc pattern: ${pattern}`);
                        return true;
                    }
                } else if (pattern.trim() === libraryPrepMethod) {
                    console.log(`Library prep method ${libraryPrepMethod} found as exact postqc pattern`);
                    return true;
                }
            }
        }

        console.log(`Library prep method ${libraryPrepMethod} is unknown`);
        return false;
    }

    addUnknownLibPrepWarnings() {
        // Create warning sections for both alignment and postqc
        const stages = ['alignment', 'postqc'];

        stages.forEach(stage => {
            const unknownSamples = this.unknownLibraryPrepMethodSamples[stage];
            if (unknownSamples.size > 0) {
                const warningSection = document.createElement('div');
                warningSection.className = 'unknown-libprep-section';
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

                // Add to appropriate section based on stage
                const targetSection = stage === 'alignment' ? this.alignmentBatches : this.postQCBatches;

                // Remove any existing warning section in this stage
                const existingWarning = targetSection.querySelector('.unknown-libprep-section');
                if (existingWarning) {
                    existingWarning.remove();
                }

                // Insert the new warning section at the top of its respective section
                targetSection.insertBefore(warningSection, targetSection.firstChild);

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

            // If no assets found in config, return empty array
            if (assets.size === 0) {
                console.warn('No assets found in config for stage:', stage);
                return [];
            }

            console.log(`Available assets for ${stage}:`, Array.from(assets));
            return Array.from(assets);
        } catch (error) {
            console.error('Error getting assets from config:', error);
            return [];
        }
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
                const rowSelector = `tr[data-sample="${sample.load_name}"][data-stage="${stage}"]`;
                console.log(`Looking for command cell with selector: ${rowSelector}`);
                const row = this.modal.querySelector(rowSelector);
                if (!row) {
                    console.error(`Could not find row for sample ${sample.load_name}`);
                    return;
                }
                const commandCell = row.querySelector('.command-cell code');
                if (commandCell) {
                    commandCell.textContent = '';
                } else {
                    console.error(`Could not find command cell for sample ${sample.load_name}`);
                }
            });
            return;
        }

        // Get workflow based on first sample
        const workflow = 'rtx'; // Always rtx for unknown lib preps

        // Find a matching asset template in the workflow/stage configuration
        let commandTemplate = '';
        let assetConfig = null;

        if (this.config?.workflows?.[workflow]?.[stage]) {
            const workflowConfig = this.config.workflows[workflow][stage];

            // Find any template with the matching asset name
            for (const [pattern, config] of Object.entries(workflowConfig)) {
                if (config.asset_name === selectedAsset) {
                    commandTemplate = config.command_template;
                    assetConfig = config;
                    console.log(`Found template for asset ${selectedAsset}: ${commandTemplate}`);
                    break;
                }
            }

            // If no template found, create one based on other similar templates
            if (!commandTemplate) {
                // Get any template as a base for structure
                const anyTemplate = Object.values(workflowConfig)[0]?.command_template || '';
                if (anyTemplate) {
                    // Create a template by replacing the asset name
                    commandTemplate = anyTemplate.replace(
                        /--asset-name\s+([^\s]+)/,
                        `--asset-name ${selectedAsset}`
                    );

                    // Add asset tag if provided
                    if (assetTag && !commandTemplate.includes('--asset-tag')) {
                        commandTemplate = commandTemplate.replace(
                            /--asset-name\s+([^\s]+)/,
                            `--asset-name $1 --asset-tag "${assetTag}"`
                        );
                    }

                    console.log(`Created template for ${selectedAsset} based on other templates: ${commandTemplate}`);
                }
            } else if (assetTag && !commandTemplate.includes('--asset-tag') && assetConfig) {
                // Add asset tag to existing template if provided
                commandTemplate = commandTemplate.replace(
                    /--asset-name\s+([^\s]+)/,
                    `--asset-name $1 --asset-tag "${assetTag}"`
                );
            }
        }

        // If still no command template, show an error
        if (!commandTemplate) {
            console.error(`Could not create command template for ${selectedAsset}`);
            return;
        }

        console.log(`Using command template: ${commandTemplate}`);

        // Update command for each affected sample
        affectedSamples.forEach(sample => {
            const rowSelector = `tr[data-sample="${sample.load_name}"][data-stage="${stage}"]`;
            console.log(`Looking for command cell with selector: ${rowSelector}`);
            const row = this.modal.querySelector(rowSelector);
            if (!row) {
                console.error(`Could not find row for sample ${sample.load_name}`);
                return;
            }
            const commandCell = row.querySelector('.command-cell code');
            if (!commandCell) {
                console.error(`Could not find command cell for sample ${sample.load_name}`);
                return;
            }

            // Generate command
            const command = this.generateCommandFromTemplate(commandTemplate, sample);
            console.log(`Generated command for ${sample.load_name}: ${command}`);
            commandCell.textContent = command;

            // Store the command in the sample object
            if (stage === 'alignment') {
                sample.alignmentCommand = command;
            } else {
                sample.postQCCommand = command;
            }
        });
    }

    generateCommandFromTemplate(template, sample) {
        if (!template) return '';

        const reference = this.getReference(sample.organism_common_name || '');
        const libraryPrep = sample.library_prep_method || '';
        const chemistry = this.getChemistry(libraryPrep);
        const notificationEmail = this.getNotificationEmail();

        // Replace known placeholders
        let command = template
            .replace(/{load_name}/g, sample.load_name || '')
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
}

// Add CSS for code blocks and rainbow badge
document.addEventListener('DOMContentLoaded', () => {
    const style = document.createElement('style');
    style.textContent = `
        .command-preview {
            background-color: #2d2d2d;
            color: #f8f9fa;
            padding: 12px 15px;
            font-family: monospace;
            white-space: nowrap;
            font-size: 0.9rem;
            overflow-x: auto;
            max-height: 120px;
        }
        
        #submit-modal .card {
            border: 1px solid rgba(0,0,0,.125);
            box-shadow: 0 2px 4px rgba(0,0,0,.05);
        }
        
        #submit-modal .list-group-item h6 {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        /* Rainbow badge for MTX */
        .rainbow-badge {
            background: linear-gradient(124deg, #ff2400, #e81d1d, #e8b71d, #e3e81d, #1de840, #1ddde8, #2b1de8, #dd00f3, #dd00f3);
            background-size: 1800% 1800%;
            animation: rainbow 8s ease infinite;
            color: white;
            font-weight: bold;
            padding: 0.35em 0.65em;
            border-radius: 0.375rem;
        }
        
        @keyframes rainbow { 
            0% { background-position: 0% 80% }
            50% { background-position: 100% 20% }
            100% { background-position: 0% 80% }
        }

        .cellranger-options {
            padding: 10px;
            border-radius: 4px;
            background-color: #f8f9fa;
        }

        .chemistry-select {
            max-width: 200px;
        }

        .include-introns-check {
            margin-top: 8px;
        }

        .unknown-libprep-container {
            margin-top: 1rem;
            padding: 1rem;
            background-color: rgba(255, 255, 255, 0.5);
            border-radius: 4px;
        }

        .unknown-libprep-container h6 {
            color: #856404;
            margin-bottom: 0.5rem;
        }

        .unknown-libprep-container ul {
            margin: 0.5rem 0;
            padding-left: 1.5rem;
        }

        .unknown-libprep-container .form-label {
            font-size: 0.875rem;
            color: #495057;
        }

        .unknown-libprep-container .asset-selector {
            max-width: 300px;
        }

        .alert.alert-warning h5 {
            color: #856404;
            margin-bottom: 1rem;
        }

        .alert.alert-warning p {
            margin-bottom: 0.5rem;
        }
    `;
    document.head.appendChild(style);

    // Initialize the modal handler
    window.pipelineSubmitModal = new PipelineSubmitModal();
}); 