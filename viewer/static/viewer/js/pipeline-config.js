/**
 * pipeline-config.js
 * Handles loading and parsing of pipeline configuration from YAML files
 */

class PipelineConfig {
    constructor() {
        this.config = null;
        this.isLoaded = false;
    }

    /**
     * Load the configuration from the YAML file
     * @returns {Promise} A promise that resolves when the config is loaded
     */
    async loadConfig() {
        try {
            const response = await fetch('/api/pipeline/config');
            if (!response.ok) {
                throw new Error(`Failed to fetch config: ${response.statusText}`);
            }
            this.config = await response.json();
            this.isLoaded = true;
            return this.config;
        } catch (error) {
            console.error('Error loading pipeline config:', error);
            // Fallback to default config if fetch fails
            this.config = this.getDefaultConfig();
            this.isLoaded = true;
            return this.config;
        }
    }

    /**
     * Get the reference options for dropdowns
     * @returns {Object} Object with reference values and labels
     */
    getReferences() {
        if (!this.isLoaded) {
            return {};
        }
        return this.config.references || {};
    }

    /**
     * Get the chemistry options for dropdowns
     * @returns {Object} Object with chemistry values and labels
     */
    getChemistries() {
        if (!this.isLoaded) {
            return {};
        }
        return this.config.chemistries || {};
    }

    /**
     * Get execution priority options
     * @returns {Array} Array of priority options
     */
    getExecutionPriorities() {
        return ['LOW', 'NORMAL', 'HIGH'];
    }

    /**
     * Get asset tags for a specific workflow and asset
     * @param {string} workflow - The workflow (mtx or rtx)
     * @param {string} stage - The pipeline stage (alignment or postqc)
     * @returns {Array} Array of asset tags
     */
    getAssetTags(workflow, stage) {
        if (!this.isLoaded || !workflow || !stage) {
            return [];
        }

        try {
            const workflowConfig = this.config.workflows[workflow.toLowerCase()];
            if (!workflowConfig) return [];

            const stageConfig = workflowConfig[stage];
            if (!stageConfig) return [];

            // For postqc, handle default and specific configurations
            if (stage === 'postqc') {
                // Gather all available tags
                const tags = [];

                // Add default tag if available
                if (stageConfig.asset_tag) {
                    tags.push(stageConfig.asset_tag);
                }

                // Add specific config tags
                for (const key in stageConfig) {
                    if (typeof stageConfig[key] === 'object' && stageConfig[key].asset_tag) {
                        tags.push(stageConfig[key].asset_tag);
                    }
                }

                // Add the latest tag if no others exist
                if (tags.length === 0) {
                    tags.push('latest');
                }

                return tags;
            } else {
                // For other stages like alignment
                return stageConfig.asset_tag ? [stageConfig.asset_tag] : ['latest'];
            }
        } catch (error) {
            console.error(`Error getting asset tags for ${workflow}/${stage}:`, error);
            return ['latest'];
        }
    }

    /**
     * Get the command template for a specific workflow and stage
     * @param {string} workflow - The workflow (mtx or rtx)
     * @param {string} stage - The pipeline stage (alignment or postqc)
     * @returns {string} The command template string
     */
    getCommandTemplate(workflow, stage) {
        if (!this.isLoaded || !workflow || !stage) {
            return '';
        }

        try {
            const workflowConfig = this.config.workflows[workflow.toLowerCase()];
            if (!workflowConfig) return '';

            const stageConfig = workflowConfig[stage];
            if (!stageConfig) return '';

            // For postqc with sub-configurations, use default
            if (stage === 'postqc' && typeof stageConfig === 'object' && !stageConfig.command_template) {
                if (stageConfig.default && stageConfig.default.command_template) {
                    return stageConfig.default.command_template;
                }
                // If no default is specified, collect first available template
                for (const key in stageConfig) {
                    if (typeof stageConfig[key] === 'object' && stageConfig[key].command_template) {
                        return stageConfig[key].command_template;
                    }
                }
                return '';
            }

            return stageConfig.command_template || '';
        } catch (error) {
            console.error(`Error getting command template for ${workflow}/${stage}:`, error);
            return '';
        }
    }

    /**
     * Get asset name for a specific workflow and stage
     * @param {string} workflow - The workflow (mtx or rtx)
     * @param {string} stage - The pipeline stage (alignment or postqc)
     * @returns {string} The asset name
     */
    getAssetName(workflow, stage) {
        if (!this.isLoaded || !workflow || !stage) {
            return '';
        }

        try {
            const workflowConfig = this.config.workflows[workflow.toLowerCase()];
            if (!workflowConfig) return '';

            const stageConfig = workflowConfig[stage];
            if (!stageConfig) return '';

            // For postqc with sub-configurations, use default
            if (stage === 'postqc' && typeof stageConfig === 'object' && !stageConfig.asset_name) {
                if (stageConfig.default && stageConfig.default.asset_name) {
                    return stageConfig.default.asset_name;
                }
                // If no default is specified, collect first available
                for (const key in stageConfig) {
                    if (typeof stageConfig[key] === 'object' && stageConfig[key].asset_name) {
                        return stageConfig[key].asset_name;
                    }
                }
                return '';
            }

            return stageConfig.asset_name || '';
        } catch (error) {
            console.error(`Error getting asset name for ${workflow}/${stage}:`, error);
            return '';
        }
    }

    /**
     * Get notification email from settings
     * @returns {string} The notification email address
     */
    getNotificationEmail() {
        if (!this.isLoaded || !this.config.settings || !this.config.settings.notifications) {
            return '$USER@alleninstitute.org';
        }

        const notifications = this.config.settings.notifications;
        if (notifications.email && notifications.email.recipients && notifications.email.recipients.length > 0) {
            return notifications.email.recipients[0];
        }

        return '$USER@alleninstitute.org';
    }

    /**
     * Create a default config as fallback
     * @returns {Object} Default configuration object
     */
    getDefaultConfig() {
        return {
            references: {
                human: "human_10x_grch38_genome_star2.7.1a",
                mouse: "mouse_10x_mm10_genome_star2.7.1a",
                rat: "rat_ncbi_mratbn7.2_genome_star2.7.1a",
                macaque: "macaque_ncbi_mmul10_genome_star2.7.1a",
                armadillo: "armadillo_ncbi_mdasnov1-hap2_genome_star2-7-1a"
            },
            chemistries: {
                "10xV3.1D": "SC3Pv3",
                "10xRseq_Mult_noATAC": "ARC-v1",
                "10xV3.1_HT": "SC3Pv3HT",
                "10xV4": "SC3Pv4",
                "10Xv2": "SC3Pv2"
            },
            workflows: {
                mtx: {
                    alignment: {
                        asset_name: "cellranger-arc",
                        command_template: "ocs fastqs align tenx-arc --reference-names \"{reference}\" --asset-name cellranger-arc --load-names \"{load_name}\" --notify-on FAILED --notify {notification_email}"
                    },
                    postqc: {
                        asset_name: "multi_gex_qc",
                        asset_tag: "latest",
                        command_template: "ocs fastqs postalign tenx-arc --asset-name multi_gex_qc --asset-tag latest --load-names \"{load_name}\""
                    }
                },
                rtx: {
                    alignment: {
                        asset_name: "cellranger-rnaseq",
                        command_template: "ocs fastqs align tenx-rnaseq --reference-names \"{reference}\" --asset-name cellranger-rnaseq --load-names \"{load_name}\" --cellranger-addopts \"--chemistry {chemistry} --include-introns\""
                    },
                    postqc: {
                        default: {
                            asset_name: "tenx_rnaseq_qc",
                            command_template: "ocs fastqs postalign tenx-rnaseq --asset-name tenx_rnaseq_qc --load-names \"{load_name}\""
                        },
                        tenxv4: {
                            asset_tag: "25.01.14",
                            command_template: "ocs fastqs postalign tenx-rnaseq --asset-name tenx_rnaseq_qc --asset-tag 25.01.14 --load-names \"{load_name}\""
                        }
                    }
                }
            },
            settings: {
                notifications: {
                    email: {
                        enabled: true,
                        recipients: ["$USER@alleninstitute.org"],
                        events: ["FAILED", "COMPLETED"]
                    }
                }
            }
        };
    }
}

// Create global instance
window.pipelineConfig = new PipelineConfig();

// Auto-load config when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await window.pipelineConfig.loadConfig();
        console.log('Pipeline configuration loaded successfully');

        // Dispatch an event to notify other components
        const event = new CustomEvent('pipeline-config-loaded');
        document.dispatchEvent(event);
    } catch (error) {
        console.error('Failed to load pipeline configuration:', error);
    }
}); 