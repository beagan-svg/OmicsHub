/**
 * commands.js
 * Handles generation of pipeline commands for different workflows
 */

class PipelineCommands {
    /**
     * Generate alignment command for a sample
     * @param {Object} sample - Sample data
     * @returns {string} Command string
     */
    static generateAlignmentCommand(sample) {
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

    /**
     * Generate post-QC command for a sample
     * @param {Object} sample - Sample data
     * @returns {string} Command string
     */
    static generatePostQCCommand(sample) {
        const workflow = sample.workflow || this.determineWorkflow(sample);
        const fastqName = sample.fastq_name || sample.fastqName;

        if (workflow === 'MTX') {
            return `python run_mtx_postqc.py --config=pipeline_config.yaml --fastq=${fastqName}`;
        } else {
            return `python run_rtx_postqc.py --config=pipeline_config.yaml --fastq=${fastqName}`;
        }
    }

    /**
     * Determine workflow based on batch name
     * @param {Object} sample - Sample data
     * @returns {string} Workflow type (MTX or RTX)
     */
    static determineWorkflow(sample) {
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

    /**
     * Get reference genome name for an organism
     * @param {string} organism - Organism common name
     * @returns {string} Reference genome name
     */
    static getReference(organism) {
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

    /**
     * Get chemistry value for a library prep method
     * @param {string} libraryPrep - Library prep method
     * @returns {string} Chemistry value
     */
    static getChemistry(libraryPrep) {
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
}

// Expose the commands module
window.PipelineCommands = PipelineCommands; 