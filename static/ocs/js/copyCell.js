/*
 * copyCell.js — click-to-copy behavior for ".copy-cell" elements (ripple +
 * copied pulse + toast). One shared implementation; replaces the per-page
 * inline copies. Loaded app-wide; auto-binds on DOMContentLoaded and is safe to
 * call again (OCS.initCopyCells) after dynamic content changes. Uses event
 * delegation, so dynamically added cells work without re-binding.
 */
(function () {
    'use strict';

    const OCS = window.OCS || {};

    function addRipple(cell, event) {
        const rect = cell.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.className = 'ripple';
        ripple.style.left = (event.clientX - rect.left) + 'px';
        ripple.style.top = (event.clientY - rect.top) + 'px';
        cell.appendChild(ripple);
        setTimeout(() => ripple.remove(), 600);
    }

    function copy(cell) {
        const target = cell.querySelector('.text-monospace') || cell;
        const text = target.textContent.trim();
        if (!text) return;
        navigator.clipboard.writeText(text).then(() => {
            cell.classList.add('copied');
            if (OCS.toast) OCS.toast('Demand ID copied to clipboard', 'success');
            setTimeout(() => cell.classList.remove('copied'), 1500);
        }).catch(() => {
            if (OCS.toast) OCS.toast('Failed to copy to clipboard', 'error');
        });
    }

    /** Bind delegated handlers once. Idempotent. */
    OCS.initCopyCells = function () {
        if (document.body.dataset.copyCellsBound) return;
        document.body.dataset.copyCellsBound = '1';

        document.addEventListener('mousedown', (e) => {
            const cell = e.target.closest('.copy-cell');
            if (cell) addRipple(cell, e);
        });
        document.addEventListener('click', (e) => {
            const cell = e.target.closest('.copy-cell');
            if (cell) { e.stopPropagation(); copy(cell); }
        });
    };

    document.addEventListener('DOMContentLoaded', OCS.initCopyCells);
    window.OCS = OCS;
})();
