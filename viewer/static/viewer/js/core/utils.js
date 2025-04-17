/**
 * utils.js
 * Core utility functions used across the application
 */

// CSRF token handling for AJAX requests
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Show toast notification
function showToastNotification(message, type = 'success', duration = 2000) {
    // Remove any existing toasts to prevent duplicates
    const existingToasts = document.querySelectorAll('.toast');
    existingToasts.forEach(toast => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    });

    // Create toast container if it doesn't exist
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'position-fixed bottom-0 start-50 translate-middle-x p-3';
        toastContainer.style.zIndex = '11'; // Above most content
        document.body.appendChild(toastContainer);
    }

    // Set background color based on type
    let bgColor = '#1976D2'; // Default blue
    if (type === 'error' || type === 'danger') {
        bgColor = '#dc3545'; // Red
    } else if (type === 'warning') {
        bgColor = '#ffc107'; // Yellow
    } else if (type === 'success') {
        bgColor = '#28a745'; // Green
    }

    // Create the toast element
    const toastDiv = document.createElement('div');
    toastDiv.className = 'toast align-items-center text-white border-0';
    toastDiv.style.backgroundColor = bgColor;
    toastDiv.setAttribute('role', 'alert');
    toastDiv.setAttribute('aria-live', 'assertive');
    toastDiv.setAttribute('aria-atomic', 'true');

    // Set inner HTML for toast with icon
    const icon = type === 'success' ? 'bi-check-circle' :
        type === 'warning' ? 'bi-exclamation-triangle' :
            type === 'error' || type === 'danger' ? 'bi-x-circle' : 'bi-info-circle';

    toastDiv.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi ${icon} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

    // Add to container
    toastContainer.appendChild(toastDiv);

    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toastDiv, { delay: duration });
    bsToast.show();

    // Remove after hiding
    toastDiv.addEventListener('hidden.bs.toast', () => {
        if (toastDiv.parentNode) {
            toastDiv.parentNode.removeChild(toastDiv);
        }
    });
}

// Format date/time strings
function formatDateTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleString();
}

// Helper to check if string is empty
function isEmpty(str) {
    return !str || str.trim() === '';
}

// Export utilities
window.AppUtils = {
    getCookie,
    showToastNotification,
    formatDateTime,
    isEmpty
}; 