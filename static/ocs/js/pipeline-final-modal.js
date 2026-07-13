/**
 * pipeline-final-modal.js
 * Integrated with ModalManager for modern modal handling
 */

class PipelineFinalModal {
    /**
     * Initialize the final commands modal
     */
    constructor() {

        // DOM elements
        this.modal = document.getElementById('final-commands-modal');
        this.executeSubmitBtn = document.getElementById('execute-submit');
        this.alignmentCommandsContainer = document.getElementById('final-alignment-commands');
        this.postQCCommandsContainer = document.getElementById('final-postqc-commands');

        // State tracking
        this.commands = null;
        this.debugMode = true; // Enable debug logging

        // Initialize
        this.injectStyles();
        this.setupEventListeners();

    }

    /**
     * Log debug messages to console when debug mode is enabled
     */
    log(message, data = null) {
        if (this.debugMode) {
            const timestamp = new Date().toISOString().substr(11, 12);
            if (data) {
            } else {
            }
        }
    }

    /**
     * Set up all event listeners for the modal
     */
    setupEventListeners() {
        this.log('Setting up event listeners');

        // Back button (return to previous modal)
        const backButton = this.modal?.querySelector('button[data-bs-dismiss="modal"].btn-secondary');
        if (backButton) {
            backButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.log('Back button clicked');

                // Dispatch event for modal manager to handle
                document.dispatchEvent(new CustomEvent('finalModalBack'));
            });
        }

        // Close button (X in the corner)
        const closeButton = this.modal?.querySelector('.btn-close');
        if (closeButton) {
            closeButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.log('Close button clicked');

                // Close modal using modal manager
                if (window.modalManager) {
                    window.modalManager.closeModal('final-commands-modal');
                }
            });
        }

        // Execute button (submit the commands)
        if (this.executeSubmitBtn) {
            this.executeSubmitBtn.addEventListener('click', () => {
                this.log('Execute button clicked');
                this.executeSubmission();
            });
        }

        this.log('Event listeners setup complete');
    }

    /**
     * Display the modal with commands
     */
    show(data) {
        this.log('Showing final modal with commands', data);

        if (!this.modal) {
            this.log('Modal element not found');
            return;
        }

        // Add final-modal class for identification
        if (!this.modal.classList.contains('final-modal')) {
            this.modal.classList.add('final-modal');
        }

        // Clear containers
        this.clearContainers();

        // Store commands
        this.commands = data?.commands || [];
        if (!Array.isArray(this.commands)) {
            this.log('Invalid commands data structure', data);
            this.showErrorState('The command data is invalid or empty.');
            return;
        }

        this.log(`Processing ${this.commands.length} commands`);

        // Separate alignment and post-QC commands
        const alignmentCommands = this.commands.filter(cmd => cmd.alignment);
        const postQCCommands = this.commands.filter(cmd => cmd.postqc);

        this.log(`Separated commands: ${alignmentCommands.length} alignment, ${postQCCommands.length} post-QC`);

        // Render custom tables
        const alignmentContainer = this.modal.querySelector('.card-header.bg-primary')?.closest('.card')?.querySelector('.card-body');
        const postQCContainer = this.modal.querySelector('.card-header.bg-success')?.closest('.card')?.querySelector('.card-body');

        if (alignmentContainer) {
            alignmentContainer.innerHTML = '';
            this.renderUnifiedTable(alignmentContainer, alignmentCommands);
        }

        if (postQCContainer) {
            postQCContainer.innerHTML = '';
            this.renderUnifiedTable(postQCContainer, postQCCommands);
        }

        // Modal manager will handle the display
        this.log('Final modal content prepared and ready for display');
    }

    /**
     * Clear command containers
     */
    clearContainers() {
        if (this.alignmentCommandsContainer) {
            this.alignmentCommandsContainer.innerHTML = '';
        }
        if (this.postQCCommandsContainer) {
            this.postQCCommandsContainer.innerHTML = '';
        }
    }

    /**
     * Render commands in the specified container
     */
    renderUnifiedTable(container, commands) {
        if (!container) return;

        if (!commands.length) {
            container.innerHTML = `
                <div class="final-modal-empty-message">
                    No commands to display
                </div>
            `;
            return;
        }

        // Table header
        let html = `
            <table class="final-modal-table">
                <thead>
                    <tr>
                        <th>Fastq Name</th>
                        <th>Workflow</th>
                        <th>Command</th>
                    </tr>
                </thead>
                <tbody>
        `;

        // Table rows
        this.log('Rendering Fastq Names:', commands.map(item => item.fastq_name));
        html += commands.map(item => {
            const workflow = (item.workflow || '').toUpperCase();
            // Add auto-proceed badge if autoToggle is true AND it's a post-QC command
            const autoProceedBadge = item.autoToggle && item.postqc ? `
                <div class="final-modal-auto-proceed-badge">
                    <i class="bi bi-play-fill"></i> Auto Proceed
                </div>
            ` : '';

            return `
                <tr>
                    <td class="final-modal-fastq-cell">${item.fastq_name || ''}</td>
                    <td class="final-modal-workflow-cell">
                        <span class="final-modal-workflow-badge ${workflow === 'MTX' ? 'rainbow-badge' : 'bg-primary'}">${workflow}</span>
                    </td>
                    <td class="final-modal-command-cell">
                        <div class="final-modal-command-wrapper">
                            <div class="final-modal-command-box">${this.escapeHtml(item.command || '')}</div>
                            ${autoProceedBadge}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        html += '</tbody></table>';
        container.innerHTML = html;

        // Apply command styling
        this.applyCommandStyling(container);
    }

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    /**
     * Apply syntax highlighting after rendering
     */
    applyCommandStyling(container) {
        this.log('Starting command styling for container:', container);

        // Find all command box elements
        const codeElements = container.querySelectorAll('.final-modal-command-box');
        this.log(`Found ${codeElements.length} command boxes to process`);

        codeElements.forEach((codeElement, index) => {
            const originalText = codeElement.textContent;
            this.log(`Processing command ${index + 1}:`, originalText);

            const fragment = document.createDocumentFragment();
            const parts = originalText.split(/(\s+)/);
            let currentFlag = null;

            parts.forEach((part, partIndex) => {
                const span = document.createElement('span');
                span.textContent = part;

                // Check if this part is a flag
                if (part.startsWith('--')) {
                    currentFlag = part;
                    span.className = 'cmd-param';
                    this.log(`Found flag: ${part}`);
                }
                // If we have a current flag and this is not a flag, it's an argument value
                else if (currentFlag && !part.startsWith('--') && part.trim()) {
                    span.className = 'cmd-arg-value';
                    this.log(`Highlighting argument for flag ${currentFlag}: ${part}`);
                    currentFlag = null; // Reset current flag after processing its argument
                }
                // Command name (ocs)
                else if (partIndex === 0 && part.startsWith('ocs')) {
                    span.className = 'cmd-name';
                    this.log(`Found command name: ${part}`);
                }

                fragment.appendChild(span);
            });

            codeElement.textContent = '';
            codeElement.appendChild(fragment);
            this.log(`Finished processing command ${index + 1}`);
        });
    }

    /**
     * Show error state in the modal
     */
    showErrorState(message = 'Invalid data structure received. Please try again or contact support.') {
        this.log('Showing error state:', message);

        // Error message
        const errorMessage = `
            <div class="final-modal-error-message">
                <i class="bi bi-exclamation-triangle-fill"></i>
                <span>${message}</span>
            </div>
        `;

        // Display in both containers
        if (this.alignmentCommandsContainer) {
            this.alignmentCommandsContainer.innerHTML = errorMessage;
        }

        if (this.postQCCommandsContainer) {
            this.postQCCommandsContainer.innerHTML = errorMessage;
        }
    }

    /**
     * Execute submission of commands
     */
    executeSubmission() {
        this.log('Executing submission with commands', this.commands);

        if (!this.commands || !Array.isArray(this.commands)) {
            this.log('No valid commands to execute');
            return;
        }

        // Build the requested data structure
        const alignmentMap = new Map();
        const postqcMap = new Map();

        this.commands.forEach(cmd => {
            if (cmd.alignment) alignmentMap.set(cmd.fastq_name, cmd.command);
            if (cmd.postqc) postqcMap.set(cmd.fastq_name, cmd.command);
        });

        // Union of all fastq_names
        const allFastqNames = Array.from(new Set([
            ...alignmentMap.keys(),
            ...postqcMap.keys()
        ]));

        // Build array
        const now = new Date();
        const nowStr = now.toLocaleString();
        const result = allFastqNames.map(fastq_name => {
            const hasAlignment = alignmentMap.has(fastq_name);
            const hasPostQC = postqcMap.has(fastq_name);
            const status = (hasAlignment && hasPostQC) ? 'Pending' : 'Ready';

            return {
                'Fastq Name': fastq_name,
                'Alignment Command': alignmentMap.get(fastq_name) || '',
                'PostQC Command': postqcMap.get(fastq_name) || '',
                'Current Day and Time': nowStr,
                'Status': status
            };
        });

        this.log('Submission Data Structure:', result);

        // Show loading state
        if (this.executeSubmitBtn) {
            this.executeSubmitBtn.disabled = true;
            this.executeSubmitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';
        }

        // Send to backend API
        fetch('/api/queue/import/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken()
            },
            body: JSON.stringify({ queue: result })
        })
            .then(response => response.json())
            .then(data => {
                this.log('Queue import response:', data);

                // Reset button state
                if (this.executeSubmitBtn) {
                    this.executeSubmitBtn.disabled = false;
                    this.executeSubmitBtn.innerHTML = 'Execute Commands';
                }

                // Only clear samples that were successfully queued
                if (data.status === 'success' && window.pipelineLocalData) {
                    // Check if removeSubmittedSamples exists and use it to remove specific samples
                    if (typeof window.pipelineLocalData.removeSubmittedSamples === 'function') {
                        window.pipelineLocalData.removeSubmittedSamples(allFastqNames);
                    } else {
                        // Fall back to clearing all data if precise removal isn't available
                        window.pipelineLocalData.clearStoredData();
                    }

                    // Show success notification if available
                    if (typeof window.pipelineLocalData.showToastNotification === 'function') {
                        window.pipelineLocalData.showToastNotification('Samples successfully queued for processing', 'success');
                    }

                    // Close modal and redirect
                    if (window.modalManager) {
                        window.modalManager.closeModal('final-commands-modal');
                    }

                    // Redirect to queue management page
                    setTimeout(() => {
                        window.location.href = '/pipeline/queue/';
                    }, 500);
                } else {
                    // Show error message
                    if (window.pipelineLocalData && typeof window.pipelineLocalData.showToastNotification === 'function') {
                        window.pipelineLocalData.showToastNotification(`Error: ${data.message || 'Failed to queue samples'}`, 'danger');
                    }
                }
            })
            .catch(error => {
                this.log('Queue import failed:', error);

                // Reset button state
                if (this.executeSubmitBtn) {
                    this.executeSubmitBtn.disabled = false;
                    this.executeSubmitBtn.innerHTML = 'Execute Commands';
                }

                // Show error notification if available
                if (window.pipelineLocalData && typeof window.pipelineLocalData.showToastNotification === 'function') {
                    window.pipelineLocalData.showToastNotification('Failed to queue samples for processing', 'danger');
                }
            });

        // Trigger event for parent to handle execution
        const event = new CustomEvent('finalModalExecute', {
            detail: { commands: this.commands }
        });
        document.dispatchEvent(event);
    }

    /**
     * Get the CSRF token from the cookie
     */
    getCsrfToken() {
        const name = 'csrftoken';
        const match = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return match ? match[2] : '';
    }

    /**
     * Inject required CSS styles
     */
    injectStyles() {
        if (document.getElementById('final-modal-styles')) return;

        this.log('Injecting styles');
        const style = document.createElement('style');
        style.id = 'final-modal-styles';
        style.textContent = `
            .final-modal-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
                font-size: 16px;
                background: #fff;
                border-radius: 12px;
                overflow: hidden;
                margin-bottom: 0;
            }
            .final-modal-table th {
                background: #f8fafc;
                color: #222b45;
                font-weight: 600;
                font-size: 15px;
                padding: 16px 20px;
                border-bottom: 2px solid #e0e4ea;
                text-align: left;
            }
            .final-modal-table td {
                padding: 18px 20px;
                vertical-align: middle;
                font-size: 15px;
                border-bottom: 1px solid #f0f1f3;
            }
            .final-modal-table tr:last-child td {
                border-bottom: none;
            }
            .final-modal-fastq-cell {
                font-weight: 500;
                color: #2c3e50;
                letter-spacing: 0.01em;
            }
            .final-modal-workflow-cell {
                width: 90px;
            }
            /* Use standard Bootstrap classes for badges */
            .bg-primary {
                background-color: #0d6efd !important;
                color: white;
                font-weight: 500;
                padding: 0.35em 0.65em;
                border-radius: 0.375rem;
                font-size: 0.875rem;
            }
            /* Rainbow badge for MTX workflow */
            .rainbow-badge {
                background: linear-gradient(124deg, #ff2400, #e81d1d, #e8b71d, #e3e81d, #1de840, #1ddde8, #2b1de8, #dd00f3, #dd00f3);
                background-size: 1800% 1800%;
                animation: rainbow 8s ease infinite;
                color: white;
                font-weight: 500;
                padding: 0.35em 0.65em;
                border-radius: 0.375rem;
                font-size: 0.875rem;
            }
            @keyframes rainbow {
                0% { background-position: 0% 80% }
                50% { background-position: 100% 20% }
                100% { background-position: 0% 80% }
            }
            .final-modal-command-cell {
                font-family: 'JetBrains Mono', 'SFMono-Regular', 'Consolas', 'Liberation Mono', 'Menlo', monospace;
                font-size: 15px;
                background: #f8f9fb;
                border-radius: 8px;
                padding: 0 !important;
            }
            .final-modal-command-wrapper {
                display: flex;
                align-items: center;
                justify-content: space-between;
                position: relative;
                padding: 0;
            }
            .final-modal-command-box {
                padding: 14px 18px;
                background: none;
                border: none;
                border-radius: 8px;
                white-space: pre-wrap;
                word-break: break-word;
                color: #24292e;
                font-size: 15px;
                font-family: inherit;
                flex: 1;
                min-width: 0;
            }
            .final-modal-command-box .cmd-name {
                color: #24292e;
                font-weight: 500;
            }
            .final-modal-command-box .cmd-param {
                color: #24292e;
                font-weight: 500;
            }
            .final-modal-command-box .cmd-arg-value {
                color: #A31515;
                font-weight: 500;
            }
            .final-modal-auto-proceed-badge {
                display: flex;
                align-items: center;
                background-color: #2E7D32;
                color: white;
                font-size: 13px;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 16px;
                margin-left: 16px;
                box-shadow: 0 2px 8px rgba(46, 125, 50, 0.2);
                animation: finalModalPulse 2s infinite;
                white-space: nowrap;
                flex-shrink: 0;
            }
            .final-modal-auto-proceed-badge i {
                font-size: 14px;
                margin-right: 6px;
            }
            @keyframes finalModalPulse {
                0% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0.4); }
                70% { box-shadow: 0 0 0 10px rgba(46, 125, 50, 0); }
                100% { box-shadow: 0 0 0 0 rgba(46, 125, 50, 0); }
            }
            .final-modal-empty-message {
                padding: 20px;
                text-align: center;
                font-style: italic;
                color: #6c757d;
                font-size: 15px;
            }
            .final-modal-error-message {
                padding: 20px;
                text-align: center;
                color: #D32F2F;
                font-size: 15px;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }
            .final-modal-error-message i {
                font-size: 20px;
                color: #D32F2F;
            }
            /* Card header styling */
            .final-modal .card-header {
                padding: 1rem 1.5rem;
                font-size: 1.25rem;
                font-weight: 600;
                color: #2c3e50;
                border-bottom: 1px solid #dee2e6;
                background-color: #f8f9fa;
            }
            
            /* Ensure both alignment and post-QC headers have the same size */
            .final-modal .card-header.bg-primary,
            .final-modal .card-header.bg-success {
                font-size: 1.25rem;
                font-weight: 600;
                padding: 1rem 1.5rem;
                color: white;
            }
        `;
        document.head.appendChild(style);
    }
}

// Initialize on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit to ensure other scripts are loaded
    setTimeout(() => {
        window.pipelineFinalModal = new PipelineFinalModal();
    }, 150);
}); 