/**
 * api.js
 * API client for making AJAX requests to the backend
 */

class ApiClient {
    constructor() {
        this.csrfToken = window.AppUtils ? window.AppUtils.getCookie('csrftoken') : null;
    }

    /**
     * Make a GET request
     * @param {string} url - The URL to request
     * @param {Object} params - Query parameters
     * @returns {Promise} Promise resolving to the response data
     */
    async get(url, params = {}) {
        // Add query params if provided
        const queryString = Object.keys(params).length > 0
            ? '?' + new URLSearchParams(params).toString()
            : '';

        const response = await fetch(`${url}${queryString}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
            }
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Make a POST request
     * @param {string} url - The URL to post to
     * @param {Object} data - The data to send
     * @returns {Promise} Promise resolving to the response data
     */
    async post(url, data = {}) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': this.csrfToken
            },
            body: JSON.stringify(data)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Submit form data
     * @param {string} url - The URL to post to
     * @param {FormData} formData - The form data to send
     * @returns {Promise} Promise resolving to the response data
     */
    async submitForm(url, formData) {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': this.csrfToken
            },
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }

        return response.json();
    }

    /**
     * Get pipeline job data
     * @returns {Promise} Promise resolving to the job data
     */
    async getJobData() {
        return this.get('/api/pipeline/get-job-data/');
    }

    /**
     * Get queue data
     * @returns {Promise} Promise resolving to the queue data
     */
    async getQueueData() {
        return this.get('/api/pipeline/get-queue-data/');
    }

    /**
     * Submit samples for alignment
     * @param {Array} samples - Array of sample data
     * @param {boolean} force - Whether to force submission
     * @returns {Promise} Promise resolving to the submission result
     */
    async submitSamples(samples, force = false) {
        return this.post('/api/pipeline/submit-samples/', {
            samples,
            force
        });
    }
}

// Initialize and expose API client
window.API = new ApiClient(); 