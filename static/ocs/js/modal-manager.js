/**
 * Simple Modal Manager
 * Handles opening/closing modals with backdrop while considering navbar
 */

class ModalManager {
    constructor() {
        this.activeModal = null;
        this.backdrop = null;
        this.init();
    }

    init() {
        this.createBackdrop();
        this.setupEventListeners();
    }

    /**
     * Create a reusable backdrop element
     */
    createBackdrop() {
        this.backdrop = document.createElement('div');
        this.backdrop.className = 'modal-backdrop modal-manager-backdrop';
        this.backdrop.style.cssText = `
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background-color: rgba(0, 0, 0, 0.5) !important;
            z-index: 10000 !important;
            display: none !important;
            opacity: 0 !important;
            transition: opacity 0.15s ease !important;
            pointer-events: auto !important;
        `;

        // Close modal when backdrop is clicked
        this.backdrop.addEventListener('click', () => {
            if (this.activeModal) {
                this.closeModal();
            }
        });

        document.body.appendChild(this.backdrop);
    }

    /**
     * Setup global event listeners
     */
    setupEventListeners() {
        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal) {
                this.closeModal();
            }
        });

        // Handle Bootstrap modal events
        document.addEventListener('show.bs.modal', (e) => {
            this.handleBootstrapModalShow(e.target);
        });

        document.addEventListener('hidden.bs.modal', (e) => {
            this.handleBootstrapModalHide(e);
        });
    }

    /**
     * Open a modal
     */
    openModal(modalElement) {
        if (typeof modalElement === 'string') {
            modalElement = document.getElementById(modalElement);
        }

        if (!modalElement) {
            console.error('[ModalManager] Modal element not found');
            return;
        }

        // Close any existing modal first
        if (this.activeModal) {
            this.closeModal();
        }

        this.activeModal = modalElement;

        // Ensure modal appears above backdrop
        modalElement.style.setProperty('z-index', '10001', 'important');

        // Show backdrop
        this.showBackdrop();

        // Adjust navbar z-index
        this.adjustNavbar(true);

        // Show modal using Bootstrap
        const bsModal = new bootstrap.Modal(modalElement, {
            backdrop: false, // We handle our own backdrop
            keyboard: false  // We handle escape key ourselves
        });

        bsModal.show();

    }

    /**
     * Close the active modal
     */
    closeModal() {
        if (!this.activeModal) {
            return;
        }

        const modalElement = this.activeModal;

        // Hide modal using Bootstrap
        const bsModal = bootstrap.Modal.getInstance(modalElement);
        if (bsModal) {
            bsModal.hide();
        }

        // Remove any z-index overrides from the modal
        modalElement.style.removeProperty('z-index');

        // Hide backdrop
        this.hideBackdrop();

        // Adjust navbar z-index
        this.adjustNavbar(false);

        this.activeModal = null;

        // Additional cleanup - ensure no pointer event blocking
        setTimeout(() => {
            // Double-check backdrop is not blocking
            if (this.backdrop) {
                this.backdrop.style.pointerEvents = 'none';
                this.backdrop.style.display = 'none';
            }
        }, 200);

    }

    /**
     * Switch between modals smoothly
     */
    switchModal(fromModalId, toModalId, options = {}) {

        return new Promise((resolve) => {
            // Get the modals
            const fromModal = typeof fromModalId === 'string' ? document.getElementById(fromModalId) : fromModalId;
            const toModal = typeof toModalId === 'string' ? document.getElementById(toModalId) : toModalId;

            if (!fromModal || !toModal) {
                console.error('[ModalManager] One or both modals not found for switching');
                resolve();
                return;
            }

            // Store focus management
            const activeElement = document.activeElement;
            if (activeElement && fromModal.contains(activeElement)) {
                activeElement.blur(); // Remove focus to prevent ARIA issues
            }

            // Don't hide the backdrop during switching - keep it visible
            const fromBsModal = bootstrap.Modal.getInstance(fromModal);
            if (fromBsModal) {
                fromBsModal.hide();
            }

            // Update active modal immediately to prevent backdrop hiding
            this.activeModal = toModal;

            // Small delay to allow the first modal to hide, then show the new one
            setTimeout(() => {
                // Show the new modal
                const toBsModal = new bootstrap.Modal(toModal, {
                    backdrop: false, // We handle our own backdrop
                    keyboard: false  // We handle escape key ourselves
                });

                toBsModal.show();

                // Set focus to the new modal after it's shown
                setTimeout(() => {
                    const firstFocusable = toModal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
                    if (firstFocusable) {
                        firstFocusable.focus();
                    }
                }, 50);

                // Call completion callback if provided
                if (options.onComplete && typeof options.onComplete === 'function') {
                    options.onComplete();
                }

                resolve();
            }, 100);
        });
    }

    /**
     * Show the backdrop
     */
    showBackdrop() {
        if (!this.backdrop) {
            console.error('[ModalManager] Backdrop element not found!');
            return;
        }

        this.backdrop.style.display = 'block';
        this.backdrop.style.pointerEvents = 'auto';

        // Force reflow then show
        requestAnimationFrame(() => {
            this.backdrop.style.opacity = '1';

            // Debug: check backdrop visibility
            const rect = this.backdrop.getBoundingClientRect();
            const computed = window.getComputedStyle(this.backdrop);
            console.log('[ModalManager] Backdrop debug:', {
                display: computed.display,
                opacity: computed.opacity,
                zIndex: computed.zIndex,
                position: computed.position,
                pointerEvents: computed.pointerEvents,
                width: rect.width,
                height: rect.height,
                visible: rect.width > 0 && rect.height > 0
            });
        });
    }

    /**
     * Hide the backdrop
     */
    hideBackdrop() {
        if (!this.backdrop) return;

        this.backdrop.style.opacity = '0';

        // Hide after transition and ensure pointer events are disabled
        setTimeout(() => {
            this.backdrop.style.display = 'none';
            this.backdrop.style.pointerEvents = 'none';
        }, 150);
    }

    /**
     * Adjust navbar z-index when modal is open/closed
     */
    adjustNavbar(modalOpen) {
        const navbar = document.querySelector('.navbar');
        if (!navbar) return;

        // Our backdrop is now at z-index 10000, which is higher than navbar's 9998
        // So we don't need to adjust the navbar z-index anymore
        if (modalOpen) {
        } else {
        }
    }

    /**
     * Handle Bootstrap modal show event
     */
    handleBootstrapModalShow(modalElement) {

        // Ensure our manager is aware of Bootstrap-triggered modals
        if (!this.activeModal) {
            this.activeModal = modalElement;
            this.showBackdrop();
            this.adjustNavbar(true);
        } else if (this.activeModal !== modalElement) {
            // If switching modals, update the active modal but don't change backdrop
            this.activeModal = modalElement;
        }
    }

    /**
     * Handle Bootstrap modal hide event
     */
    handleBootstrapModalHide(event) {
        const modalElement = event.target;

        // Only clean up if this was the active modal and no other modal is opening
        if (this.activeModal === modalElement) {
            // Small delay to check if another modal is opening
            setTimeout(() => {
                // If no other modal became active, clean up
                if (this.activeModal === modalElement) {
                    this.hideBackdrop();
                    this.adjustNavbar(false);
                    this.activeModal = null;

                    // Ensure backdrop doesn't block interactions
                    if (this.backdrop) {
                        this.backdrop.style.pointerEvents = 'none';
                        this.backdrop.style.display = 'none';
                    }

                }
            }, 50);
        }
    }

    /**
     * Check if a modal is currently open
     */
    isModalOpen() {
        return this.activeModal !== null;
    }

    /**
     * Get the currently active modal
     */
    getActiveModal() {
        return this.activeModal;
    }

    /**
     * Utility method to open a modal by ID
     */
    open(modalId) {
        this.openModal(modalId);
    }

    /**
     * Utility method to close the current modal
     */
    close() {
        this.closeModal();
    }

    /**
     * Close all modals (for compatibility)
     */
    closeAllModals() {
        this.closeModal();
    }

    /**
     * Force cleanup - use this if page becomes unresponsive
     */
    forceCleanup() {

        // Force hide backdrop
        if (this.backdrop) {
            this.backdrop.style.display = 'none';
            this.backdrop.style.opacity = '0';
            this.backdrop.style.pointerEvents = 'none';
        }

        // Close any open Bootstrap modals
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) {
                bsModal.hide();
            }
            modal.style.removeProperty('z-index');
        });

        // Reset state
        this.activeModal = null;
        this.adjustNavbar(false);

        // Remove any residual Bootstrap backdrops
        const bootstrapBackdrops = document.querySelectorAll('.modal-backdrop:not(.modal-manager-backdrop)');
        bootstrapBackdrops.forEach(backdrop => backdrop.remove());

    }

    /**
     * Clean up the modal manager
     */
    destroy() {
        this.forceCleanup();

        if (this.backdrop && this.backdrop.parentNode) {
            this.backdrop.parentNode.removeChild(this.backdrop);
        }

        this.adjustNavbar(false);
        this.activeModal = null;

    }

    /**
     * Debug method to test modal manager functionality
     */
    test() {

        // Check if modal manager is working
        console.log('Modal manager state:', {
            hasBackdrop: !!this.backdrop,
            activeModal: this.activeModal ? this.activeModal.id : null,
            backdropInDOM: this.backdrop ? document.body.contains(this.backdrop) : false
        });

        // Test backdrop visibility
        if (this.backdrop) {
            const computed = window.getComputedStyle(this.backdrop);
            console.log('Backdrop computed styles:', {
                display: computed.display,
                opacity: computed.opacity,
                zIndex: computed.zIndex,
                position: computed.position,
                className: this.backdrop.className
            });

            // Check navbar z-index for comparison
            const navbar = document.querySelector('.navbar');
            if (navbar) {
                const navbarComputed = window.getComputedStyle(navbar);
            }
        }

        // Check for conflicting elements
        const conflictingBackdrops = document.querySelectorAll('.modal-backdrop:not(.modal-manager-backdrop)');

        // Check if submit modal exists
        const submitModal = document.getElementById('submit-modal');
        const finalModal = document.getElementById('final-commands-modal');

        // Test modal switching if both modals exist
        if (submitModal && finalModal) {
            this.openModal('submit-modal');

            setTimeout(() => {
                this.switchModal('submit-modal', 'final-commands-modal').then(() => {

                    setTimeout(() => {
                        this.closeModal();
                    }, 2000);
                });
            }, 1000);
        }

        return {
            modalManagerReady: true,
            backdropReady: !!this.backdrop,
            submitModalExists: !!submitModal,
            finalModalExists: !!finalModal,
            conflictingBackdrops: conflictingBackdrops.length,
            forceCleanupAvailable: 'Use window.modalManager.forceCleanup() if page becomes unresponsive'
        };
    }
}

// Create global instance
const modalManager = new ModalManager();

// Export for use in other scripts
window.modalManager = modalManager;

// Add global helper functions for debugging
window.fixFrozenPage = () => {
    if (window.modalManager && typeof window.modalManager.forceCleanup === 'function') {
        window.modalManager.forceCleanup();
        return 'Page should now be interactive. Try clicking on elements.';
    } else {
        console.error('Modal manager not available');
        return 'Modal manager not available';
    }
};

window.debugModal = () => {
    if (window.modalManager && typeof window.modalManager.test === 'function') {
        return window.modalManager.test();
    } else {
        console.error('Modal manager not available');
        return null;
    }
};

// Dispatch ready event
document.dispatchEvent(new CustomEvent('modalManagerReady', {
    detail: { modalManager }
}));

