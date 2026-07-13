/*
 * utils.js — small shared frontend helpers (no framework, no build step).
 * Loaded app-wide in base.html. Exposes window.OCS.
 */
(function () {
    'use strict';

    const OCS = window.OCS || {};

    /** Debounce: run fn after it stops being called for `wait` ms. */
    OCS.debounce = function (fn, wait) {
        let t;
        return function (...args) {
            clearTimeout(t);
            t = setTimeout(() => fn.apply(this, args), wait);
        };
    };

    /**
     * Show a dismissible toast (top-right). Uses the shared .c-toast class.
     * type: 'success' | 'error' | 'info' (default 'info').
     */
    OCS.toast = function (message, type) {
        const cls = type === 'success' ? 'alert-success'
            : type === 'error' ? 'alert-danger' : 'alert-info';
        const icon = type === 'success' ? 'bi-clipboard-check'
            : type === 'error' ? 'bi-x-circle' : 'bi-info-circle';
        const el = document.createElement('div');
        el.className = `c-toast alert ${cls} alert-dismissible fade show`;
        el.setAttribute('role', 'alert');
        el.innerHTML = `<i class="bi ${icon} me-2"></i>${message}` +
            '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>';
        document.body.appendChild(el);
        setTimeout(() => {
            if (window.bootstrap && bootstrap.Alert) {
                bootstrap.Alert.getOrCreateInstance(el).close();
            } else {
                el.remove();
            }
        }, 3000);
    };

    window.OCS = OCS;
})();
