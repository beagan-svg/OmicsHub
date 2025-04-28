/**
 * pipeline-final-modal.js
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
        this.backButtonPressed = false;
        this.commands = null;
        this.debugMode = true; // Enable debug logging

        // Bootstrap modal instance
        this.bootstrapModal = new bootstrap.Modal(this.modal, {
            backdrop: 'static',
            keyboard: false
        });

        // Initialize
        this.injectStyles();
        this.setupEventListeners();

        this.log('PipelineFinalModal initialized');
    }

    /**
     * Log debug messages to console when debug mode is enabled
     * @param {string} message - The message to log
     * @param {*} data - Optional data to log
     */
    log(message, data = null) {
        if (this.debugMode) {
            if (data) {
                console.log(`[FinalModal] ${message}`, data);
            } else {
                console.log(`[FinalModal] ${message}`);
            }
        }
    }

    /**
     * Set up all event listeners for the modal
     */
    setupEventListeners() {
        // Back button (return to previous modal)
        const backButton = this.modal.querySelector('button[data-bs-dismiss="modal"].btn-secondary');
        if (backButton) {
            backButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.log('Back button clicked');
                this.backButtonPressed = true;
                this.hide();
                // Trigger event for parent to handle showing submit modal
                document.dispatchEvent(new CustomEvent('finalModalBack'));
            });
        }

        // Close button (X in the corner)
        const closeButton = this.modal.querySelector('.btn-close');
        if (closeButton) {
            closeButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.log('Close button clicked');
                this.backButtonPressed = false;
                this.hide();
            });
        }

        // Execute button (submit the commands)
        if (this.executeSubmitBtn) {
            this.executeSubmitBtn.addEventListener('click', () => {
                this.log('Execute button clicked');
                this.backButtonPressed = false;
                this.executeSubmission();
            });
        }

        // Modal hidden event - handle cleanup and dispatch appropriate events
        this.modal.addEventListener('hidden.bs.modal', () => {
            this.log('Modal hidden event triggered');
            // Only cleanup if no other modals are showing
            if (!document.querySelector('.modal.show')) {
                this.cleanup();

                if (!this.backButtonPressed) {
                    this.log('Dispatching finalModalClose event');
                    document.dispatchEvent(new CustomEvent('finalModalClose'));
                } else {
                    this.log('Resetting back button flag after back navigation');
                    // Reset the flag
                    this.backButtonPressed = false;
                }
            }
        });
    }

    /**
     * Display the modal with commands
     * @param {Object} data - The commands to display
     */
    show(data) {
        this.log('Showing final modal with commands', data);
        // Add debug log for commands
        if (data && Array.isArray(data.commands)) {
            console.log('[FinalModal][DEBUG] commands:', JSON.parse(JSON.stringify(data.commands)));
        }
        if (!this.modal.classList.contains('final-modal')) {
            this.modal.classList.add('final-modal');
        }

        // Look for and remove existing hardcoded tables from HTML structure
        // This will remove the "SAMPLE COMMAND" headers shown in the black box
        const existingTables = this.modal.querySelectorAll('.card-body table.table');
        existingTables.forEach(table => {
            // Replace table with a div that we'll fill with our new table
            const parentDiv = table.closest('.card-body');
            if (parentDiv) {
                parentDiv.innerHTML = '';
            }
        });

        // Clear our command containers
        this.clearContainers();

        // Store commands
        this.commands = data.commands;
        if (!data || !data.commands || !Array.isArray(data.commands)) {
            this.log('Invalid commands data structure', data);
            this.showErrorState('The command data is invalid or empty.');
            return;
        }

        // Separate alignment and post-QC commands
        const alignmentCommands = data.commands.filter(cmd => cmd.alignment);
        const postQCCommands = data.commands.filter(cmd => cmd.postqc);

        // Render our custom tables
        const alignmentContainer = this.modal.querySelector('.card-header.bg-primary').closest('.card').querySelector('.card-body');
        const postQCContainer = this.modal.querySelector('.card-header.bg-success').closest('.card').querySelector('.card-body');

        if (alignmentContainer) {
            alignmentContainer.innerHTML = '';
            this.renderUnifiedTable(alignmentContainer, alignmentCommands);
        }

        if (postQCContainer) {
            postQCContainer.innerHTML = '';
            this.renderUnifiedTable(postQCContainer, postQCCommands);
        }

        this.bootstrapModal.show();
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
     * @param {HTMLElement} container - The container to render into
     * @param {Array} commands - The commands to render
     */
    renderUnifiedTable(container, commands) {
        if (!container) return;
        if (!commands.length) {
            container.innerHTML = `
                <tr>
                    <td colspan="3" class="final-modal-empty-message">
                        No commands to display
                    </td>
                </tr>
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
        console.log('[FinalModal] Rendering Fastq Names:', commands.map(item => item.fastq_name));
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
        // Style the command text
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
     * Uses a different approach that doesn't insert class names in displayed text
     */
    applyCommandStyling(container) {
        console.log('[FinalModal] Starting command styling for container:', container);

        // Find all command box elements
        const codeElements = container.querySelectorAll('.final-modal-command-box');
        console.log(`[FinalModal] Found ${codeElements.length} command boxes to process`);

        codeElements.forEach((codeElement, index) => {
            const originalText = codeElement.textContent;
            console.log(`[FinalModal] Processing command ${index + 1}:`, originalText);

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
                    console.log(`[FinalModal] Found flag: ${part}`);
                }
                // If we have a current flag and this is not a flag, it's an argument value
                else if (currentFlag && !part.startsWith('--') && part.trim()) {
                    span.className = 'cmd-arg-value';
                    console.log(`[FinalModal] Highlighting argument for flag ${currentFlag}: ${part}`);
                    currentFlag = null; // Reset current flag after processing its argument
                }
                // Command name (ocs)
                else if (partIndex === 0 && part.startsWith('ocs')) {
                    span.className = 'cmd-name';
                    console.log(`[FinalModal] Found command name: ${part}`);
                }

                fragment.appendChild(span);
            });

            codeElement.textContent = '';
            codeElement.appendChild(fragment);
            console.log(`[FinalModal] Finished processing command ${index + 1}`);
        });
    }

    /**
     * Show error state in the modal
     * @param {string} message - Optional error message
     */
    showErrorState(message = 'Invalid data structure received. Please try again or contact support.') {
        this.log('Showing error state:', message);

        // Error message row
        const errorMessage = `
            <tr>
                <td colspan="3" class="final-modal-error-message">
                    <i class="bi bi-exclamation-triangle-fill"></i>
                    <span>${message}</span>
                </td>
            </tr>
        `;

        // Display in both containers
        if (this.alignmentCommandsContainer) {
            this.alignmentCommandsContainer.innerHTML = errorMessage;
        }

        if (this.postQCCommandsContainer) {
            this.postQCCommandsContainer.innerHTML = errorMessage;
        }

        // Show the modal
        this.bootstrapModal.show();
    }

    /**
     * Hide the modal
     */
    hide() {
        this.log('Hiding modal');
        this.bootstrapModal.hide();
    }

    /**
     * Clean up after modal is closed
     */
    cleanup() {
        this.log('Performing modal cleanup');
        document.body.classList.remove('modal-open');
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
            backdrop.remove();
        }
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }

    /**
     * Execute submission of commands
     */
    executeSubmission() {
        this.log('Executing submission with commands', this.commands);

        // Hide the modal
        this.hide();

        // Trigger event for parent to handle execution
        const event = new CustomEvent('finalModalExecute', {
            detail: { commands: this.commands }
        });
        document.dispatchEvent(event);
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
    window.pipelineFinalModal = new PipelineFinalModal();
}); 