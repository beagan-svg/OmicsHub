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

        this.setupEventListeners();
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

        // Get selected samples from PipelineLocalData
        const selectedSamples = window.pipelineLocalData.selectedSamples;

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
            const postQCStatus = sample.post_qc_status || 'Not Started';

            // Categorize the sample
            if (ingestStatus.toLowerCase() === 'not started') {
                this.incompleteSamples.push({ ...sample, fastqName });
            } else if (alignmentStatus.toLowerCase() === 'completed' && postQCStatus.toLowerCase() !== 'completed') {
                this.postQCSamples.push({ ...sample, fastqName });
            } else if (ingestStatus.toLowerCase() === 'completed' && alignmentStatus.toLowerCase() !== 'completed') {
                this.alignmentSamples.push({ ...sample, fastqName });
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
                li.textContent = sample.fastqName;
                this.incompleteList.appendChild(li);
            });
        }

        // Update the command lists
        this.updateCommandLists();
    }

    updateCommandLists() {
        // Clear existing command lists
        this.alignmentCommandsList.innerHTML = '';
        this.postQCCommandsList.innerHTML = '';

        const autoProceed = this.autoProceedToggle.checked;

        // Populate alignment commands list
        if (this.alignmentSamples.length > 0) {
            this.alignmentSamples.forEach(sample => {
                const listItem = document.createElement('div');
                listItem.className = 'list-group-item';

                const alignmentCmd = this.generateAlignmentCommand(sample);
                listItem.innerHTML = `
                    <h6 class="mb-1">${sample.fastqName} <span class="badge ${sample.workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${sample.workflow || this.determineWorkflow(sample)}</span></h6>
                    <div class="bg-light p-2 rounded mb-2 code-block">
                        <small><code>${alignmentCmd}</code></small>
                    </div>
                    ${autoProceed ? `
                    <div class="mt-2">
                        <span class="badge bg-success">Auto-proceed to Post-QC</span>
                        <div class="bg-light p-2 rounded mt-1 code-block">
                            <small><code>${this.generatePostQCCommand(sample)}</code></small>
                        </div>
                    </div>
                    ` : ''}
                `;
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
                const listItem = document.createElement('div');
                listItem.className = 'list-group-item';

                const postQCCmd = this.generatePostQCCommand(sample);
                listItem.innerHTML = `
                    <h6 class="mb-1">${sample.fastqName} <span class="badge ${sample.workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${sample.workflow || this.determineWorkflow(sample)}</span></h6>
                    <div class="bg-light p-2 rounded code-block">
                        <small><code>${postQCCmd}</code></small>
                    </div>
                `;
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
        const fastqName = sample.fastq_name || sample.fastqName;
        const loadName = sample.load_name || '';
        const organism = sample.organism_common_name || '';
        const reference = this.getReference(organism);
        const libraryPrep = sample.library_prep || '';

        // Generate command according to workflow type
        if (workflow === 'MTX') {
            return `ocs fastqs align tenx-arc --reference-names "${reference}" --asset-name cellranger-arc --load-names "${loadName}" --notify-on FAILED --notify beagan.nguy@alleninstitute.org`;
        } else {
            // RTX workflow
            const chemistry = this.getChemistry(libraryPrep);

            // Determine command based on library prep method
            if (['10xV3.1D', '10xRseq_Mult_noATAC', '10xV3.1_HT', '10Xv3.1'].includes(libraryPrep)) {
                return `ocs fastqs align tenx-rnaseq --reference-names "${reference}" --asset-name cellranger-rnaseq --load-names "${loadName}" --cellranger-addopts "--chemistry ${chemistry} --include-introns"`;
            } else if (['10xV3.1_HT_CP', '10xV3.1_HT_CP-BC'].includes(libraryPrep)) {
                return `ocs fastqs align tenx-rnaseq-multi --asset-name cellranger-multi --reference-names "${reference}" --cellranger-addopts "--include-introns" --execution-priority HIGH --load-names "${loadName}"`;
            } else if (libraryPrep === '10xV4') {
                return `ocs fastqs align tenx-rnaseq --reference-names "${reference}" --asset-name cellranger-rnaseq --load-names "${loadName}" --asset-tag 8.0.1 --cellranger-addopts "--chemistry ${chemistry}"`;
            } else {
                return `ocs fastqs align tenx-rnaseq --reference-names "${reference}" --asset-name cellranger-rnaseq --load-names "${loadName}" --cellranger-addopts "--chemistry ${chemistry} --include-introns"`;
            }
        }
    }

    generatePostQCCommand(sample) {
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const fastqName = sample.fastq_name || sample.fastqName;

        if (workflow === 'MTX') {
            return `python run_mtx_postqc.py --config=pipeline_config.yaml --fastq=${fastqName}`;
        } else {
            return `python run_rtx_postqc.py --config=pipeline_config.yaml --fastq=${fastqName}`;
        }
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
}

// Add CSS for code blocks and rainbow badge
document.addEventListener('DOMContentLoaded', () => {
    const style = document.createElement('style');
    style.textContent = `
        .code-block {
            max-height: 80px;
            overflow-y: auto;
            font-family: monospace;
            white-space: pre-wrap;
            word-break: break-all;
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
    `;
    document.head.appendChild(style);

    // Initialize the modal handler
    window.pipelineSubmitModal = new PipelineSubmitModal();
}); 