/**
 * pipeline-final-modal.js
 * Handles the final commands modal functionality for the RNA-seq pipeline
 */

class PipelineFinalModal {
    constructor() {
        this.modal = document.getElementById('final-commands-modal');
        this.executeSubmitBtn = document.getElementById('execute-submit');
        this.alignmentCommandsContainer = document.getElementById('final-alignment-commands');
        this.postQCCommandsContainer = document.getElementById('final-postqc-commands');

        // Flag to track if back button was pressed
        this.backButtonPressed = false;

        // Initialize Bootstrap modal
        this.bootstrapModal = new bootstrap.Modal(this.modal, {
            backdrop: 'static',
            keyboard: false
        });

        this.setupEventListeners();
    }

    setupEventListeners() {
        // Get the back button
        const backButton = this.modal.querySelector('button[data-bs-dismiss="modal"].btn-secondary');
        if (backButton) {
            backButton.onclick = (e) => {
                e.preventDefault();
                console.log('Back button clicked in final modal, about to dispatch finalModalBack event');
                // Set flag before hiding modal
                this.backButtonPressed = true;
                this.hide();
                // Trigger event for parent to handle showing submit modal
                const event = new CustomEvent('finalModalBack');
                document.dispatchEvent(event);
                console.log('finalModalBack event dispatched from final modal');
            };
        }

        // Handle close button
        const closeButton = this.modal.querySelector('.btn-close');
        if (closeButton) {
            closeButton.onclick = (e) => {
                e.preventDefault();
                // Make sure flag is false for close button
                this.backButtonPressed = false;
                this.hide();
            };
        }

        // Handle execute button
        if (this.executeSubmitBtn) {
            this.executeSubmitBtn.addEventListener('click', () => {
                // Make sure flag is false for execute button
                this.backButtonPressed = false;
                this.executeSubmission();
            });
        }

        // Handle modal hidden event - centralize cleanup here
        this.modal.addEventListener('hidden.bs.modal', () => {
            // Only cleanup if no other modals are showing
            if (!document.querySelector('.modal.show')) {
                this.cleanup();

                // Only dispatch finalModalClose if back button was NOT pressed
                if (!this.backButtonPressed) {
                    console.log('Final modal closed (not from back button), dispatching finalModalClose');
                    const event = new CustomEvent('finalModalClose');
                    document.dispatchEvent(event);
                } else {
                    console.log('Final modal closed from back button, not dispatching finalModalClose');
                    // Reset the flag
                    this.backButtonPressed = false;
                }
            }
        });
    }

    show(commands) {
        // Clear previous commands
        if (this.alignmentCommandsContainer) {
            this.alignmentCommandsContainer.innerHTML = '';
        }
        if (this.postQCCommandsContainer) {
            this.postQCCommandsContainer.innerHTML = '';
        }

        // Store commands for later use
        this.commands = commands;

        // Add alignment commands
        if (commands.alignment.length > 0) {
            commands.alignment.forEach((item) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.sampleId}</td>
                    <td>${item.command}</td>
                `;
                this.alignmentCommandsContainer?.appendChild(row);
            });
        } else {
            this.alignmentCommandsContainer.innerHTML = '<tr><td colspan="2" class="text-center">No alignment commands to display</td></tr>';
        }

        // Add post-QC commands
        if (commands.postQC.length > 0) {
            commands.postQC.forEach((item) => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${item.sampleId}</td>
                    <td>${item.command}</td>
                `;
                this.postQCCommandsContainer?.appendChild(row);
            });
        } else {
            this.postQCCommandsContainer.innerHTML = '<tr><td colspan="2" class="text-center">No post-QC commands to display</td></tr>';
        }

        // Show the modal
        this.bootstrapModal.show();
    }

    hide() {
        this.bootstrapModal.hide();
    }

    cleanup() {
        document.body.classList.remove('modal-open');
        const backdrop = document.querySelector('.modal-backdrop');
        if (backdrop) {
            backdrop.remove();
        }
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }

    executeSubmission() {
        // Hide the modal
        this.hide();

        // Trigger event for parent to handle execution
        const event = new CustomEvent('finalModalExecute', {
            detail: { commands: this.commands }
        });
        document.dispatchEvent(event);
    }

    addStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .command-item {
                display: block;
                white-space: pre-wrap;
                word-break: break-all;
                background-color: #f8f9fa;
                padding: 0.5rem;
                border-radius: 0.25rem;
                font-size: 0.875rem;
                color: #212529;
                margin-bottom: 1rem;
            }

            .command-item:last-child {
                margin-bottom: 0;
            }

            .command-item strong {
                display: block;
                margin-bottom: 0.5rem;
                color: #495057;
            }

            #final-alignment-commands,
            #final-postqc-commands {
                margin-bottom: 2rem;
            }

            #final-postqc-commands:empty,
            #final-alignment-commands:empty {
                margin-bottom: 0;
            }
        `;
        document.head.appendChild(style);
    }
}

// Initialize styles when the document is ready
document.addEventListener('DOMContentLoaded', () => {
    const finalModal = new PipelineFinalModal();
    finalModal.addStyles();
    // Make the instance available globally
    window.pipelineFinalModal = finalModal;
}); 