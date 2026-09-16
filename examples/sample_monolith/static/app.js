/**
 * Monolith App — Client-side JavaScript
 * ========================================
 * Minimal AJAX utilities for interacting with the monolith API.
 * All API calls go through fetch() to /api/* endpoints.
 */

const api = {
    /**
     * GET request to an API endpoint.
     * @param {string} url - API path, e.g. '/api/users'
     * @returns {Promise<Object>} Parsed JSON response
     */
    async get(url) {
        const resp = await fetch(url);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `Request failed: ${resp.status}`);
        }
        return resp.json();
    },

    /**
     * POST request to an API endpoint.
     * @param {string} url - API path
     * @param {Object} data - Request body (JSON)
     * @returns {Promise<Object>} Parsed JSON response
     */
    async post(url, data) {
        const resp = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `Request failed: ${resp.status}`);
        }
        return resp.json();
    },

    /**
     * PUT request to an API endpoint.
     * @param {string} url - API path
     * @param {Object} data - Request body (JSON)
     * @returns {Promise<Object>} Parsed JSON response
     */
    async put(url, data) {
        const resp = await fetch(url, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `Request failed: ${resp.status}`);
        }
        return resp.json();
    },

    /**
     * DELETE request to an API endpoint.
     * @param {string} url - API path
     * @returns {Promise<Object>} Parsed JSON response
     */
    async delete(url) {
        const resp = await fetch(url, { method: 'DELETE' });
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `Request failed: ${resp.status}`);
        }
        return resp.json();
    },
};


/**
 * Show a temporary alert banner at the top of the page.
 * @param {string} message - Alert text
 * @param {string} type - 'success' | 'error'
 */
function showAlert(message, type) {
    // Remove any existing alert
    const existing = document.querySelector('.js-alert');
    if (existing) existing.remove();

    const div = document.createElement('div');
    div.className = `alert alert-${type} js-alert`;
    div.textContent = message;

    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(div, container.querySelector('.card'));
    }

    // Auto-dismiss after 4 seconds
    setTimeout(() => div.remove(), 4000);
}
