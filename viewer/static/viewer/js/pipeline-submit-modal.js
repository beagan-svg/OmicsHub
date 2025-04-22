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
        this.alignmentCommandsList = document.getElementById('alignment-commands-list');
        this.postQCCommandsList = document.getElementById('postqc-commands-list');

        // Sample tracking
        this.alignmentSamples = [];
        this.postQCSamples = [];
        this.incompleteSamples = [];

        // Add new properties for unknown library prep tracking
        this.unknownLibPrepSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        this.setupEventListeners();

        // Add styles for unknown library prep UI
        this.addStyles();
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
    }

    populateModal() {
        // Reset unknown library prep tracking
        this.unknownLibPrepSamples = {
            alignment: new Map(),
            postqc: new Map()
        };

        // Clear existing content
        this.sampleList.innerHTML = '';
        this.incompleteList.innerHTML = '';
        this.warningDiv.classList.add('d-none');
        this.alignmentCommandsList.innerHTML = '';
        this.postQCCommandsList.innerHTML = '';

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
                    library_prep: row.querySelector('td:nth-child(7)').textContent.trim(),
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

            // Extract values from sample data
            const fastqName = sample.fastq_name || '';
            const loadName = sample.load_name || '';
            const workflow = this.determineWorkflow(sample);
            const organism = sample.organism_common_name || '';
            const libraryPrepMethod = sample.library_prep || '';
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
        }

        // Only track unknown library preps for RTX workflow
        selectedSamples.forEach(sample => {
            const workflow = this.determineWorkflow(sample);
            if (workflow === 'RTX') {
                const libraryPrep = sample.library_prep || '';
                const isLibPrepKnown = this.isLibraryPrepKnown(libraryPrep);

                if (!isLibPrepKnown) {
                    if (sample.ingest_status.toLowerCase() === 'completed' &&
                        sample.alignment_status.toLowerCase() !== 'completed') {
                        // Unknown library prep for alignment
                        if (!this.unknownLibPrepSamples.alignment.has(libraryPrep)) {
                            this.unknownLibPrepSamples.alignment.set(libraryPrep, []);
                        }
                        this.unknownLibPrepSamples.alignment.get(libraryPrep).push(sample);
                    } else if (sample.alignment_status.toLowerCase() === 'completed' &&
                        sample.postqc_status.toLowerCase() !== 'completed') {
                        // Unknown library prep for postqc
                        if (!this.unknownLibPrepSamples.postqc.has(libraryPrep)) {
                            this.unknownLibPrepSamples.postqc.set(libraryPrep, []);
                        }
                        this.unknownLibPrepSamples.postqc.get(libraryPrep).push(sample);
                    }
                }
            }
        });

        // Update the command lists
        this.updateCommandLists();

        // Add unknown library prep warnings if needed
        this.addUnknownLibPrepWarnings();
    }

    updateCommandLists() {
        // Clear existing command lists
        this.alignmentCommandsList.innerHTML = '';
        this.postQCCommandsList.innerHTML = '';

        const autoProceed = this.autoProceedToggle.checked;

        // Populate alignment commands list
        if (this.alignmentSamples.length > 0) {
            this.alignmentSamples.forEach(sample => {
                const workflow = sample.workflow || this.determineWorkflow(sample);
                const libraryPrep = sample.library_prep || '';
                const isUnknownLibPrep = workflow === 'RTX' && !this.isLibraryPrepKnown(libraryPrep);

                const listItem = document.createElement('div');
                listItem.className = 'list-group-item';

                // Generate base command or empty command for unknown library prep
                let alignmentCmd = '';
                if (!isUnknownLibPrep) {
                    alignmentCmd = this.generateAlignmentCommand(sample);
                }

                // Create the interactive command builder
                const commandBuilder = this.createCommandBuilder(sample, 'alignment', alignmentCmd);

                // Create the list item content
                listItem.innerHTML = `
                    <h6 class="mb-1">${sample.fastq_name} <span class="badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span></h6>
                `;

                // Append the command builder
                listItem.appendChild(commandBuilder);

                // Add auto-proceed PostQC section if enabled
                if (autoProceed) {
                    const postQCCmd = this.generatePostQCCommand(sample);
                    const autoProceedDiv = document.createElement('div');
                    autoProceedDiv.className = 'mt-3';
                    autoProceedDiv.innerHTML = `
                        <span class="badge bg-success">Auto-proceed to Post-QC</span>
                    `;

                    // Create PostQC command builder for auto-proceed
                    const postQCBuilder = this.createCommandBuilder(sample, 'postqc', postQCCmd);
                    autoProceedDiv.appendChild(postQCBuilder);

                    // Append to the list item
                    listItem.appendChild(autoProceedDiv);
                }

                this.alignmentCommandsList.appendChild(listItem);
            });
        } else {
            this.alignmentCommandsList.innerHTML = `
                <div class="list-group-item text-center text-muted">No samples eligible for alignment</div>
            `;
        }

        // Populate post-QC commands list
        if (this.postQCSamples.length > 0) {
            this.postQCSamples.forEach(sample => {
                const workflow = sample.workflow || this.determineWorkflow(sample);
                const libraryPrep = sample.library_prep || '';
                const isUnknownLibPrep = workflow === 'RTX' && !this.isLibraryPrepKnown(libraryPrep);

                const listItem = document.createElement('div');
                listItem.className = 'list-group-item';

                // Generate base command or empty command for unknown library prep
                let postQCCmd = '';
                if (!isUnknownLibPrep) {
                    postQCCmd = this.generatePostQCCommand(sample);
                }

                // Create the list item content
                listItem.innerHTML = `
                    <h6 class="mb-1">${sample.fastq_name} <span class="badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span></h6>
                `;

                // Create the command builder
                const commandBuilder = this.createCommandBuilder(sample, 'postqc', postQCCmd);
                listItem.appendChild(commandBuilder);

                this.postQCCommandsList.appendChild(listItem);
            });
        } else {
            this.postQCCommandsList.innerHTML = `
                <div class="list-group-item text-center text-muted">No samples eligible for post-QC</div>
            `;
        }
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
        const libraryPrep = sample.library_prep || '';
        const notificationEmail = this.getNotificationEmail();

        // Get command template from config if available
        let commandTemplate = '';

        if (window.pipelineConfig && window.pipelineConfig.isLoaded) {
            commandTemplate = window.pipelineConfig.getCommandTemplate(workflow, 'alignment');
        }

        // Use template from config or fallback to hardcoded templates
        if (commandTemplate) {
            // Replace placeholders in the template
            return commandTemplate
                .replace('{reference}', reference)
                .replace('{load_name}', loadName)
                .replace('{chemistry}', this.getChemistry(libraryPrep))
                .replace('{notification_email}', notificationEmail);
        } else {
            // Fallback to hardcoded templates if config is not available
            if (workflow === 'MTX') {
                return `ocs fastqs align tenx-arc --reference-names "${reference}" --asset-name cellranger-arc --load-names "${loadName}" --notify-on FAILED --notify ${notificationEmail}`;
            } else {
                // RTX workflow
                // Get chemistry from config
                const chemistry = this.getChemistry(libraryPrep);

                // Determine cellranger-addopts based on library prep method
                let cellrangerAddopts = '';
                if (['10xV3.1D', '10xRseq_Mult_noATAC', '10xV3.1_HT', '10Xv3.1'].includes(libraryPrep)) {
                    cellrangerAddopts = `--chemistry ${chemistry} --include-introns`;
                } else if (libraryPrep === '10xV4') {
                    cellrangerAddopts = `--chemistry ${chemistry}`;
                }

                if (cellrangerAddopts) {
                    return `ocs fastqs align tenx-rnaseq --reference-names "${reference}" --asset-name cellranger-rnaseq --load-names "${loadName}" --cellranger-addopts "${cellrangerAddopts}"`;
                } else {
                    return `ocs fastqs align tenx-rnaseq --reference-names "${reference}" --asset-name cellranger-rnaseq --load-names "${loadName}"`;
                }
            }
        }
    }

    generatePostQCCommand(sample) {
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const loadName = sample.load_name || '';
        const notificationEmail = this.getNotificationEmail();

        // Get command template from config if available
        let commandTemplate = '';
        let assetTag = '25.03.27'; // Default asset tag

        if (window.pipelineConfig && window.pipelineConfig.isLoaded) {
            commandTemplate = window.pipelineConfig.getCommandTemplate(workflow, 'postqc');

            // Get asset tags from config
            const assetTags = window.pipelineConfig.getAssetTags(workflow, 'postqc');
            if (assetTags && assetTags.length > 0) {
                assetTag = assetTags[0]; // Use the first tag by default
            }
        }

        // Use template from config or fallback to hardcoded templates
        if (commandTemplate) {
            // Replace placeholders in the template
            let command = commandTemplate
                .replace('{load_name}', loadName)
                .replace('{notification_email}', notificationEmail);

            // Add asset tag if not in template
            if (!command.includes('--asset-tag') && assetTag !== 'latest') {
                command = command.replace(/--asset-name ([^ ]+)/, `--asset-name $1 --asset-tag ${assetTag}`);
            }

            // Add notification if not in template
            if (!command.includes('--notify-on')) {
                command += ` --notify-on FAILED --notify ${notificationEmail}`;
            }

            return command;
        } else {
            // Fallback to hardcoded templates if config is not available
            if (workflow === 'MTX') {
                return `ocs fastqs postalign tenx-arc --asset-name multi_gex_qc --asset-tag ${assetTag} --load-names "${loadName}" --notify-on FAILED --notify ${notificationEmail}`;
            } else {
                return `ocs fastqs postalign tenx-rnaseq --asset-name tenx_rnaseq_qc --asset-tag ${assetTag} --load-names "${loadName}" --notify-on FAILED --notify ${notificationEmail}`;
            }
        }
    }

    /**
     * Get notification email from config or use default
     * @returns {string} Email address
     */
    getNotificationEmail() {
        if (window.pipelineConfig && window.pipelineConfig.isLoaded) {
            return window.pipelineConfig.getNotificationEmail();
        }
        return '$USER@alleninstitute.org';
    }

    getReference(organism) {
        // Map organism to reference genome
        switch ((organism || '').toLowerCase()) {
            case 'human':
                return 'human_10x_grch38_genome_star2.7.1a';
            case 'mouse':
                return 'mouse_10x_mm10_genome_star2.7.1a';
            case 'rat':
                return 'rat_10x_rn6';
            case 'monkey':
            case 'macaque':
                return 'macaque_10x_mmul10';
            case 'armadillo':
                return 'armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a';
            default:
                return 'human_10x_grch38_genome_star2.7.1a'; // Default to human
        }
    }

    getChemistry(libraryPrep) {
        // Map library prep to chemistry
        switch (libraryPrep) {
            case '10xV3.1D':
                return 'SC3Pv3';
            case '10xRseq_Mult_noATAC':
                return 'ARC-v1';
            case '10xV3.1_HT':
                return 'SC3Pv3HT';
            case '10xV4':
                return 'SC3Pv4';
            case '10Xv2':
                return 'SC3Pv2';
            default:
                return 'SC3Pv3'; // Default to SC3Pv3
        }
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
        const alignmentBuilders = this.alignmentCommandsList.querySelectorAll('.command-builder');
        alignmentBuilders.forEach(builder => {
            const sample = builder.dataset.sample;
            const command = builder.dataset.command || builder.querySelector('.command-preview').textContent;

            commands.alignment.push({
                sample,
                command
            });

            // If auto-proceed is enabled, also collect post-QC commands
            if (this.autoProceedToggle.checked) {
                const postQCBuilder = builder.closest('.list-group-item').querySelector('.mt-3 .command-builder');
                if (postQCBuilder) {
                    const postQCCommand = postQCBuilder.dataset.command || postQCBuilder.querySelector('.command-preview').textContent;
                    commands.postqc.push({
                        sample,
                        command: postQCCommand
                    });
                }
            }
        });

        // Collect post-QC commands (excluding those already added from auto-proceed)
        const postQCBuilders = this.postQCCommandsList.querySelectorAll('.command-builder');
        postQCBuilders.forEach(builder => {
            const sample = builder.dataset.sample;
            const command = builder.dataset.command || builder.querySelector('.command-preview').textContent;

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

    /**
     * Create an interactive command builder UI
     * @param {Object} sample - Sample data
     * @param {string} stage - Pipeline stage ('alignment' or 'postqc')
     * @param {string} baseCommand - Initial command string
     * @returns {HTMLElement} The command builder element
     */
    createCommandBuilder(sample, stage, baseCommand) {
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const libraryPrep = sample.library_prep || '';

        // Check if this is an RTX sample with unknown library prep
        const isUnknownLibPrep = workflow === 'RTX' &&
            this.unknownLibPrepSamples[stage].has(libraryPrep);

        // Create container
        const container = document.createElement('div');
        container.className = 'command-builder';
        container.dataset.sample = sample.fastq_name;
        container.dataset.stage = stage;
        container.dataset.workflow = workflow;
        container.dataset.libraryPrep = libraryPrep;

        // Create header
        const header = document.createElement('div');
        header.className = 'command-header';
        header.innerHTML = `
            <span>${stage === 'alignment' ? 'Alignment Command' : 'Post-QC Command'}</span>
            <div>
                <button type="button" class="btn btn-sm btn-outline-secondary me-2 reset-command-btn">
                    <i class="bi bi-arrow-counterclockwise"></i> Reset
                </button>
                <button type="button" class="btn btn-sm btn-outline-primary edit-command-btn">
                    <i class="bi bi-pencil-square"></i> Edit
                </button>
            </div>
        `;

        // Create command preview section
        const preview = document.createElement('div');
        preview.className = 'command-preview' + (isUnknownLibPrep ? ' empty' : '');

        if (isUnknownLibPrep) {
            preview.textContent = 'Select an asset name to generate the command';
            container.dataset.command = '';
        } else {
            preview.textContent = baseCommand;
            container.dataset.command = baseCommand;
            container.dataset.originalCommand = baseCommand;
        }

        // Create command options section (initially hidden)
        const options = document.createElement('div');
        options.className = 'command-options d-none';

        // Parse the current command to get values
        const parts = this.parseCommand(baseCommand);
        const currentValues = {};
        parts.params.forEach(param => {
            currentValues[param.name] = param.value;
        });

        // Create editable options form
        const editForm = document.createElement('div');
        editForm.className = 'edit-form p-3';

        // Add reference names dropdown
        if (stage === 'alignment') {
            const referenceGroup = document.createElement('div');
            referenceGroup.className = 'mb-3';
            referenceGroup.innerHTML = `
                <label class="form-label">Reference Name</label>
                <select class="form-select" data-param="--reference-names">
                    <option value="human_10x_grch38_genome_star2.7.1a">human_10x_grch38_genome_star2.7.1a</option>
                    <option value="mouse_10x_mm10_genome_star2.7.1a">mouse_10x_mm10_genome_star2.7.1a</option>
                    <option value="rat_10x_rn6">rat_10x_rn6</option>
                    <option value="macaque_10x_mmul10">macaque_10x_mmul10</option>
                    <option value="armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a">armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a</option>
                </select>
            `;
            editForm.appendChild(referenceGroup);

            // Set current value
            const referenceSelect = referenceGroup.querySelector('select');
            referenceSelect.value = currentValues['--reference-names'] || this.getReference(sample.organism_common_name);
        }

        // Add asset name dropdown
        const assetGroup = document.createElement('div');
        assetGroup.className = 'mb-3';
        const assets = this.getAvailableAssets(stage);
        assetGroup.innerHTML = `
            <label class="form-label">Asset Name</label>
            <select class="form-select" data-param="--asset-name">
                ${assets.map(asset => `<option value="${asset}">${asset}</option>`).join('')}
            </select>
        `;
        editForm.appendChild(assetGroup);

        // Set current value
        const assetSelect = assetGroup.querySelector('select');
        assetSelect.value = currentValues['--asset-name'] || '';

        // Add chemistry options for RTX alignment
        if (workflow === 'RTX' && stage === 'alignment') {
            const chemistryGroup = document.createElement('div');
            chemistryGroup.className = 'mb-3';
            chemistryGroup.innerHTML = `
                <label class="form-label">Chemistry</label>
                <select class="form-select" data-param="chemistry">
                    <option value="SC3Pv3">SC3Pv3 (10xV3.1)</option>
                    <option value="SC3Pv3HT">SC3Pv3HT (10xV3.1_HT)</option>
                    <option value="SC3Pv4">SC3Pv4 (10xV4)</option>
                    <option value="SC3Pv2">SC3Pv2 (10Xv2)</option>
                </select>
                <div class="form-check mt-2">
                    <input class="form-check-input" type="checkbox" id="include-introns-${sample.fastq_name}" data-param="include-introns">
                    <label class="form-check-label" for="include-introns-${sample.fastq_name}">
                        Include introns
                    </label>
                </div>
            `;
            editForm.appendChild(chemistryGroup);

            // Set current values
            const chemistrySelect = chemistryGroup.querySelector('select');
            const includeIntronsCheck = chemistryGroup.querySelector('input[type="checkbox"]');

            // Parse current cellranger-addopts
            const cellrangerAddopts = currentValues['--cellranger-addopts'] || '';
            const chemistryMatch = cellrangerAddopts.match(/--chemistry\s+(\S+)/);
            if (chemistryMatch) {
                chemistrySelect.value = chemistryMatch[1];
            }
            includeIntronsCheck.checked = cellrangerAddopts.includes('--include-introns');
        }

        // Add notification options
        const notifyGroup = document.createElement('div');
        notifyGroup.className = 'mb-3';
        notifyGroup.innerHTML = `
            <label class="form-label">Notification Email</label>
            <input type="email" class="form-control" data-param="--notify" value="${currentValues['--notify'] || this.getNotificationEmail()}">
            <div class="form-check mt-2">
                <input class="form-check-input" type="checkbox" id="notify-failed-${sample.fastq_name}" data-param="notify-on" checked>
                <label class="form-check-label" for="notify-failed-${sample.fastq_name}">
                    Notify on failure
                </label>
            </div>
        `;
        editForm.appendChild(notifyGroup);

        // Add buttons
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'mt-3';
        buttonGroup.innerHTML = `
            <button type="button" class="btn btn-primary save-command-btn">Save Changes</button>
            <button type="button" class="btn btn-secondary ms-2 cancel-edit-btn">Cancel</button>
        `;
        editForm.appendChild(buttonGroup);

        options.appendChild(editForm);

        // Create command breakdown display
        const commandParts = document.createElement('div');
        commandParts.className = 'command-params mb-3';

        // Only parse and display command parts if we have a command
        if (!isUnknownLibPrep && baseCommand) {
            // Add base command line
            const baseLine = document.createElement('div');
            baseLine.className = 'command-line';
            baseLine.textContent = parts.base;
            commandParts.appendChild(baseLine);

            // Add parameters
            parts.params.forEach(param => {
                const paramLine = document.createElement('div');
                paramLine.className = 'command-part';
                paramLine.innerHTML = `<span class="param-name">${param.name}</span> <span class="param-value">${param.value}</span>`;
                commandParts.appendChild(paramLine);
            });
        }

        // Assemble the command builder
        container.appendChild(header);
        container.appendChild(preview);
        container.appendChild(options);
        container.appendChild(commandParts);

        // Add event listeners
        this.addCommandBuilderEventListeners(container);

        return container;
    }

    /**
     * Parse a command string into its component parts
     * @param {string} command - The command string to parse
     * @returns {Object} Object with base command and parameters
     */
    parseCommand(command) {
        // Split the command into parts
        const parts = command.split(' ');

        // Base command (ocs fastqs align tenx-rnaseq)
        const baseEndIndex = command.indexOf('--');
        const base = baseEndIndex > -1 ? command.substring(0, baseEndIndex).trim() : parts.slice(0, 3).join(' ');

        // Extract parameters
        const params = [];
        let currentParam = null;

        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];

            if (part.startsWith('--')) {
                // If we already have a parameter, add it to the list
                if (currentParam) {
                    params.push(currentParam);
                }

                // Start a new parameter
                currentParam = { name: part, value: '' };
            } else if (currentParam) {
                // Add to current parameter value
                if (currentParam.value) {
                    currentParam.value += ' ' + part;
                } else {
                    currentParam.value = part;
                }
            }
        }

        // Add the last parameter if there is one
        if (currentParam) {
            params.push(currentParam);
        }

        // Clean up parameter values (remove quotes)
        params.forEach(param => {
            if (param.value.startsWith('"') && param.value.endsWith('"')) {
                param.value = param.value.substring(1, param.value.length - 1);
            }
        });

        return { base, params };
    }

    /**
     * Add event listeners to the command builder
     * @param {HTMLElement} container - Command builder container
     */
    addCommandBuilderEventListeners(container) {
        // Toggle edit mode
        const editBtn = container.querySelector('.edit-command-btn');
        const options = container.querySelector('.command-options');
        const commandParams = container.querySelector('.command-params');
        const preview = container.querySelector('.command-preview');

        editBtn.addEventListener('click', () => {
            options.classList.toggle('d-none');
            if (options.classList.contains('d-none')) {
                editBtn.innerHTML = '<i class="bi bi-pencil-square"></i> Edit';
                editBtn.classList.remove('btn-outline-danger');
                editBtn.classList.add('btn-outline-primary');
            } else {
                editBtn.innerHTML = '<i class="bi bi-x"></i> Close';
                editBtn.classList.remove('btn-outline-primary');
                editBtn.classList.add('btn-outline-danger');
            }
        });

        // Reset button
        const resetBtn = container.querySelector('.reset-command-btn');
        resetBtn.addEventListener('click', () => {
            const originalCommand = container.dataset.originalCommand;
            if (originalCommand) {
                preview.textContent = originalCommand;
                container.dataset.command = originalCommand;
                this.updateCommandPartsDisplay(container, originalCommand);
            }
        });

        // Save changes
        const saveBtn = container.querySelector('.save-command-btn');
        saveBtn.addEventListener('click', () => {
            const newCommand = this.buildCommandFromInputs(container);
            preview.textContent = newCommand;
            container.dataset.command = newCommand;
            this.updateCommandPartsDisplay(container, newCommand);
            options.classList.add('d-none');
            editBtn.innerHTML = '<i class="bi bi-pencil-square"></i> Edit';
            editBtn.classList.remove('btn-outline-danger');
            editBtn.classList.add('btn-outline-primary');
        });

        // Cancel edit
        const cancelBtn = container.querySelector('.cancel-edit-btn');
        cancelBtn.addEventListener('click', () => {
            options.classList.add('d-none');
            editBtn.innerHTML = '<i class="bi bi-pencil-square"></i> Edit';
            editBtn.classList.remove('btn-outline-danger');
            editBtn.classList.add('btn-outline-primary');
        });

        // Handle input changes
        const inputs = container.querySelectorAll('select, input');
        inputs.forEach(input => {
            input.addEventListener('change', () => {
                const previewCommand = this.buildCommandFromInputs(container);
                preview.textContent = previewCommand;
            });
        });
    }

    buildCommandFromInputs(container) {
        const stage = container.dataset.stage;
        const workflow = container.dataset.workflow;

        // Start with base command
        let command = workflow === 'MTX' ?
            `ocs fastqs ${stage === 'alignment' ? 'align' : 'postalign'} tenx-arc` :
            `ocs fastqs ${stage === 'alignment' ? 'align' : 'postalign'} tenx-rnaseq`;

        // Get all inputs
        const inputs = container.querySelectorAll('[data-param]');
        const params = new Map();

        inputs.forEach(input => {
            const param = input.dataset.param;
            if (input.type === 'checkbox') {
                if (param === 'notify-on' && input.checked) {
                    params.set('--notify-on', 'FAILED');
                } else if (param === 'include-introns' && input.checked) {
                    // Handle in chemistry section
                }
            } else if (param === 'chemistry') {
                const includeIntrons = container.querySelector('[data-param="include-introns"]').checked;
                const chemistryOpts = `--chemistry ${input.value}${includeIntrons ? ' --include-introns' : ''}`;
                params.set('--cellranger-addopts', chemistryOpts);
            } else if (input.value) {
                params.set(`--${param}`, input.value);
            }
        });

        // Build command string
        params.forEach((value, param) => {
            if (value.includes(' ') && !value.startsWith('"')) {
                command += ` ${param} "${value}"`;
            } else {
                command += ` ${param} ${value}`;
            }
        });

        return command;
    }

    updateCommandPartsDisplay(container, command) {
        const parts = this.parseCommand(command);
        const commandParams = container.querySelector('.command-params');
        commandParams.innerHTML = '';

        // Add base command line
        const baseLine = document.createElement('div');
        baseLine.className = 'command-line';
        baseLine.textContent = parts.base;
        commandParams.appendChild(baseLine);

        // Add parameters
        parts.params.forEach(param => {
            const paramLine = document.createElement('div');
            paramLine.className = 'command-part';
            paramLine.innerHTML = `<span class="param-name">${param.name}</span> <span class="param-value">${param.value}</span>`;
            commandParams.appendChild(paramLine);
        });
    }

    isLibraryPrepKnown(libraryPrep) {
        if (!window.pipelineConfig || !window.pipelineConfig.isLoaded) {
            return false;
        }

        const rtxConfig = window.pipelineConfig.config.workflows.rtx;

        // Check alignment patterns
        for (const pattern of Object.keys(rtxConfig.alignment)) {
            const patterns = pattern.split('|');
            if (patterns.includes(libraryPrep)) {
                return true;
            }
        }

        return false;
    }

    addUnknownLibPrepWarnings() {
        // Create warning sections for both alignment and postqc
        const stages = ['alignment', 'postqc'];

        stages.forEach(stage => {
            const unknownSamples = this.unknownLibPrepSamples[stage];
            if (unknownSamples.size > 0) {
                const warningSection = document.createElement('div');
                warningSection.className = 'alert alert-warning mt-3';
                warningSection.innerHTML = `
                    <h5>Unknown Library Prep Methods for ${stage === 'alignment' ? 'Alignment' : 'Post-QC'}</h5>
                    <p>The following samples have library prep methods not defined in the configuration. Please select an asset name for each group:</p>
                `;

                const container = document.createElement('div');
                container.className = 'unknown-libprep-container';

                unknownSamples.forEach((samples, libPrep) => {
                    const libPrepSection = document.createElement('div');
                    libPrepSection.className = 'mb-4 library-prep-group';
                    libPrepSection.dataset.libprep = libPrep;
                    libPrepSection.dataset.stage = stage;

                    // Create asset name selector
                    const assetSelector = this.createAssetSelector(stage, libPrep);

                    libPrepSection.innerHTML = `
                        <div class="lib-prep-header">
                            <h6>Library Prep Method: ${libPrep}</h6>
                            <div class="mb-3">
                                <label class="form-label">Select Asset Name:</label>
                                ${assetSelector}
                            </div>
                        </div>
                        <div class="samples-list">
                            <strong>Affected Samples:</strong>
                            <ul class="list-unstyled">
                                ${samples.map(s => `<li>${s.fastq_name}</li>`).join('')}
                            </ul>
                        </div>
                    `;

                    container.appendChild(libPrepSection);
                });

                warningSection.appendChild(container);

                // Add to appropriate section
                const targetList = stage === 'alignment' ? this.alignmentCommandsList : this.postQCCommandsList;
                targetList.insertBefore(warningSection, targetList.firstChild);

                // Add event listeners for asset selectors
                container.querySelectorAll('.asset-selector').forEach(selector => {
                    selector.addEventListener('change', (event) => {
                        const libPrep = event.target.closest('.library-prep-group').dataset.libprep;
                        const stage = event.target.closest('.library-prep-group').dataset.stage;
                        const selectedAsset = event.target.value;
                        this.updateUnknownLibPrepCommands(stage, libPrep, selectedAsset);
                    });
                });
            }
        });
    }

    createAssetSelector(stage, libPrep) {
        const assets = this.getAvailableAssets(stage);
        return `
            <select class="form-select asset-selector">
                <option value="">Select an asset...</option>
                ${assets.map(asset => `<option value="${asset}">${asset}</option>`).join('')}
            </select>
        `;
    }

    getAvailableAssets(stage) {
        // Default assets if config is not available
        const defaultAssets = {
            alignment: ['cellranger-rnaseq', 'cellranger-multi'],
            postqc: ['tenx_rnaseq_qc']
        };

        // If no config is available, return default assets
        if (!window.pipelineConfig?.config?.workflows?.rtx?.[stage]) {
            return defaultAssets[stage] || [];
        }

        try {
            const rtxConfig = window.pipelineConfig.config.workflows.rtx[stage];
            const assets = new Set();

            // Extract unique asset names from the config
            for (const [pattern, config] of Object.entries(rtxConfig)) {
                if (config && typeof config === 'object' && config.asset_name) {
                    assets.add(config.asset_name);
                }
            }

            // If no assets found in config, use defaults
            if (assets.size === 0) {
                return defaultAssets[stage] || [];
            }

            return Array.from(assets);
        } catch (error) {
            console.warn('Error getting assets from config:', error);
            return defaultAssets[stage] || [];
        }
    }

    updateUnknownLibPrepCommands(stage, libPrep, selectedAsset) {
        const samples = this.unknownLibPrepSamples[stage].get(libPrep) || [];

        // Find the template for the selected asset from config
        const rtxConfig = window.pipelineConfig?.config?.workflows?.rtx?.[stage] || {};
        let selectedTemplate = '';
        let assetTag = '';

        // Look through all config entries to find matching asset name
        for (const [pattern, config] of Object.entries(rtxConfig)) {
            if (config && typeof config === 'object' && config.asset_name === selectedAsset) {
                selectedTemplate = config.command_template;
                assetTag = config.asset_tag || '';
                break;
            }
        }

        // If no template found in config, use default templates
        if (!selectedTemplate) {
            if (stage === 'alignment') {
                selectedTemplate = 'ocs fastqs align tenx-rnaseq --reference-names "{reference}" --asset-name ' +
                    selectedAsset + ' --load-names "{load_name}" --cellranger-addopts "--chemistry {chemistry} --include-introns"';
            } else {
                selectedTemplate = 'ocs fastqs postalign tenx-rnaseq --asset-name ' +
                    selectedAsset + ' --load-names "{load_name}"';
            }
        }

        samples.forEach(sample => {
            const existingBuilder = document.querySelector(`.command-builder[data-sample="${sample.fastq_name}"][data-stage="${stage}"]`);
            if (existingBuilder) {
                if (selectedAsset) {
                    // Generate command using the template
                    const command = this.generateCommandFromTemplate(selectedTemplate, sample);
                    existingBuilder.dataset.command = command;
                    existingBuilder.dataset.originalCommand = command;
                    existingBuilder.querySelector('.command-preview').textContent = command;

                    // Update the command breakdown
                    const parts = this.parseCommand(command);
                    const commandParams = existingBuilder.querySelector('.command-params');
                    commandParams.innerHTML = '';

                    // Add base command
                    const baseLine = document.createElement('div');
                    baseLine.className = 'command-line';
                    baseLine.textContent = parts.base;
                    commandParams.appendChild(baseLine);

                    // Add parameters
                    parts.params.forEach(param => {
                        const paramLine = document.createElement('div');
                        paramLine.className = 'command-part';
                        paramLine.innerHTML = `<span class="param-name">${param.name}</span> <span class="param-value">${param.value}</span>`;
                        commandParams.appendChild(paramLine);
                    });
                } else {
                    // Clear the command if no asset is selected
                    existingBuilder.dataset.command = '';
                    existingBuilder.dataset.originalCommand = '';
                    existingBuilder.querySelector('.command-preview').textContent = 'Select an asset name to generate the command';
                    existingBuilder.querySelector('.command-params').innerHTML = '';
                }
            }
        });
    }

    generateCommandFromTemplate(template, sample) {
        const reference = this.getReference(sample.organism_common_name || '');
        const chemistry = this.getChemistry(sample.library_prep || '');
        const loadName = sample.load_name || '';
        const notificationEmail = this.getNotificationEmail();

        return template
            .replace('{reference}', reference)
            .replace('{load_name}', loadName)
            .replace('{chemistry}', chemistry)
            .replace('{notification_email}', notificationEmail);
    }

    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .library-prep-group {
                border: 1px solid #ffeeba;
                border-radius: 4px;
                padding: 15px;
                margin-bottom: 15px;
                background-color: #fff;
            }

            .lib-prep-header {
                margin-bottom: 10px;
            }

            .lib-prep-header h6 {
                color: #856404;
                font-weight: 600;
                margin-bottom: 10px;
            }

            .samples-list {
                margin-top: 10px;
            }

            .samples-list ul {
                margin-top: 5px;
                padding-left: 20px;
            }

            .samples-list li {
                color: #666;
                font-size: 0.9rem;
                margin-bottom: 3px;
            }

            .command-preview.empty {
                color: #856404;
                font-style: italic;
                background-color: #fff3cd;
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