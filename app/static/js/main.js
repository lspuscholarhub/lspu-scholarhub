// LSPU ScholarHub — Main JavaScript
// NOTE: The chatbot widget has been removed from all pages.
//       The full chatbot lives at /chatbot/chatbot (dedicated page).

// ── CSRF token helper ─────────────────────────────────────────────────────────
// Reads the token from the <meta name="csrf-token"> tag injected by base.html.
// Attach to every AJAX POST/PUT/PATCH/DELETE so Flask-WTF accepts the request.
(function () {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = metaTag ? metaTag.getAttribute('content') : '';

    // Patch fetch() globally
    const _origFetch = window.fetch;
    window.fetch = function (input, init) {
        init = init || {};
        const method = (init.method || 'GET').toUpperCase();
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
            init.headers = Object.assign({ 'X-CSRFToken': csrfToken }, init.headers || {});
        }
        return _origFetch.call(this, input, init);
    };

    // Patch XMLHttpRequest globally
    const _origOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function (method) {
        this._method = method.toUpperCase();
        return _origOpen.apply(this, arguments);
    };
    const _origSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(this._method)) {
            this.setRequestHeader('X-CSRFToken', csrfToken);
        }
        return _origSend.apply(this, arguments);
    };
})();
// ─────────────────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', function () {

    // ── Bootstrap tooltips ────────────────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });

    // ── Bootstrap popovers ────────────────────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="popover"]').forEach(el => {
        new bootstrap.Popover(el);
    });

    // ── Auto-dismiss toast notifications after 5s ───────────────────────────
    document.querySelectorAll('.toast.show').forEach(function (toast) {
        const bsToast = new bootstrap.Toast(toast, { delay: 5000 });
        bsToast.show();
    });

    // ── Smooth scroll for in-page anchor links ────────────────────────────
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        });
    });

    // ── HTML5 form validation ─────────────────────────────────────────────
    document.querySelectorAll('.needs-validation').forEach(form => {
        form.addEventListener('submit', function (e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // ── Loading-state buttons ─────────────────────────────────────────────
    document.querySelectorAll('.btn-loading').forEach(btn => {
        btn.addEventListener('click', function () {
            const orig = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading…';
            this.disabled = true;
            setTimeout(() => { this.innerHTML = orig; this.disabled = false; }, 3000);
        });
    });

});

// ── Utility helpers (available globally) ─────────────────────────────────────

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString(undefined,
        { year: 'numeric', month: 'long', day: 'numeric' });
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-PH', {
        style: 'currency', currency: 'PHP'
    }).format(amount);
}

window.ScholarHub = { formatDate, formatCurrency };