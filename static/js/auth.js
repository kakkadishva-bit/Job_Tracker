/* JobAgent - Authentication JavaScript
   Enterprise-grade auth UI with validation, password strength, and UX */

// ─── Password Strength Evaluator ────────────────────────────────────
function evaluatePasswordStrength(password) {
    let score = 0;
    const checks = {
        length: password.length >= 8,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        number: /\d/.test(password),
        special: /[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;~`]/.test(password),
    };

    if (checks.length) score += 20;
    if (checks.uppercase) score += 20;
    if (checks.lowercase) score += 20;
    if (checks.number) score += 20;
    if (checks.special) score += 20;

    let level = 'weak';
    let label = 'Weak';
    if (score >= 100) { level = 'very-strong'; label = 'Very Strong'; }
    else if (score >= 80) { level = 'strong'; label = 'Strong'; }
    else if (score >= 60) { level = 'medium'; label = 'Medium'; }

    return { score, level, label, checks };
}

function updatePasswordStrength(password) {
    const result = evaluatePasswordStrength(password);
    const segments = document.querySelectorAll('.strength-segment');
    const text = document.getElementById('strengthText');

    if (!segments.length || !text) return;

    segments.forEach((seg, i) => {
        seg.className = 'strength-segment';
        const threshold = (i + 1) * 20;
        if (result.score >= threshold) {
            seg.classList.add('active', result.level);
        }
    });

    text.textContent = result.label;
    text.className = 'strength-text ' + result.level;

    // Update requirement checks
    const reqs = {
        'req-length': result.checks.length,
        'req-upper': result.checks.uppercase,
        'req-lower': result.checks.lowercase,
        'req-number': result.checks.number,
        'req-special': result.checks.special,
    };

    Object.keys(reqs).forEach(function(id) {
        var el = document.getElementById(id);
        if (el) {
            el.className = 'requirement ' + (reqs[id] ? 'met' : 'unmet');
            el.innerHTML = (reqs[id] ? '<i class="fas fa-check-circle"></i>' : '<i class="fas fa-circle"></i>') + ' ' + el.getAttribute('data-label') || '';
        }
    });
}

// ─── Email Validation ──────────────────────────────────────────────
function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function validateEmailField(input) {
    var wrapper = input.closest('.form-group').querySelector('.input-wrapper');
    var errorEl = input.closest('.form-group').querySelector('.field-error');
    var successEl = input.closest('.form-group').querySelector('.field-success');
    var val = input.value.trim();

    if (!val) {
        wrapper.classList.remove('error', 'success');
        if (errorEl) errorEl.style.display = 'none';
        if (successEl) successEl.style.display = 'none';
        return false;
    }

    if (validateEmail(val)) {
        wrapper.classList.remove('error');
        wrapper.classList.add('success');
        if (errorEl) errorEl.style.display = 'none';
        if (successEl) successEl.style.display = 'flex';
        return true;
    } else {
        wrapper.classList.remove('success');
        wrapper.classList.add('error');
        if (errorEl) errorEl.style.display = 'flex';
        if (successEl) successEl.style.display = 'none';
        return false;
    }
}

// ─── Username Validation ────────────────────────────────────────────
function validateUsername(username) {
    return /^[a-zA-Z0-9_]{3,}$/.test(username);
}

function validateUsernameField(input) {
    var wrapper = input.closest('.form-group').querySelector('.input-wrapper');
    var errorEl = input.closest('.form-group').querySelector('.field-error');
    var val = input.value.trim();

    if (!val) {
        wrapper.classList.remove('error', 'success');
        if (errorEl) errorEl.style.display = 'none';
        return false;
    }

    if (validateUsername(val)) {
        wrapper.classList.remove('error');
        wrapper.classList.add('success');
        if (errorEl) errorEl.style.display = 'none';
        return true;
    } else {
        wrapper.classList.remove('success');
        wrapper.classList.add('error');
        if (errorEl) errorEl.style.display = 'flex';
        return false;
    }
}

// ─── Password Confirmation ─────────────────────────────────────────
function validatePasswordMatch() {
    var pw = document.getElementById('password');
    var confirm = document.getElementById('confirmPassword');
    if (!pw || !confirm) return true;

    var wrapper = confirm.closest('.form-group').querySelector('.input-wrapper');
    var errorEl = confirm.closest('.form-group').querySelector('.field-error');
    var val = confirm.value;

    if (!val) {
        wrapper.classList.remove('error', 'success');
        if (errorEl) errorEl.style.display = 'none';
        return false;
    }

    if (val === pw.value) {
        wrapper.classList.remove('error');
        wrapper.classList.add('success');
        if (errorEl) errorEl.style.display = 'none';
        return true;
    } else {
        wrapper.classList.remove('success');
        wrapper.classList.add('error');
        if (errorEl) errorEl.style.display = 'flex';
        return false;
    }
}

// ─── Toggle Password Visibility ────────────────────────────────────
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('toggle-password') || e.target.closest('.toggle-password')) {
        var btn = e.target.classList.contains('toggle-password') ? e.target : e.target.closest('.toggle-password');
        var input = btn.closest('.input-wrapper').querySelector('input');
        if (input.type === 'password') {
            input.type = 'text';
            btn.innerHTML = '<i class="fas fa-eye-slash"></i>';
        } else {
            input.type = 'password';
            btn.innerHTML = '<i class="fas fa-eye"></i>';
        }
    }
});

// ─── Form Submission with Loading States ────────────────────────────
function setupAuthForm(formId, apiEndpoint, redirectUrl) {
    var form = document.getElementById(formId);
    if (!form) return;

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        var btn = form.querySelector('.auth-btn');
        var alertContainer = form.querySelector('.auth-alert-container');

        // Validate all fields
        var valid = true;
        form.querySelectorAll('[required]').forEach(function(input) {
            if (!input.value.trim()) {
                valid = false;
                input.closest('.form-group').querySelector('.input-wrapper').classList.add('error');
            }
        });

        if (!valid) {
            showAuthAlert(alertContainer, 'Please fill in all required fields', 'error');
            return;
        }

        // Show loading
        btn.classList.add('loading');
        btn.disabled = true;

        var formData = new FormData(form);
        var data = {};
        formData.forEach(function(value, key) { data[key] = value; });

        fetch(apiEndpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(function(r) { return r.json(); })
        .then(function(resp) {
            btn.classList.remove('loading');
            btn.disabled = false;

            if (resp.success) {
                showAuthAlert(alertContainer, resp.message, 'success');
                if (redirectUrl) {
                    setTimeout(function() { window.location.href = redirectUrl; }, 1000);
                }
            } else {
                showAuthAlert(alertContainer, resp.message || 'An error occurred', 'error');
            }
        })
        .catch(function(err) {
            btn.classList.remove('loading');
            btn.disabled = false;
            showAuthAlert(alertContainer, 'Connection error. Please try again.', 'error');
        });
    });
}

function showAuthAlert(container, message, type) {
    if (!container) return;
    var icons = { error: 'fa-exclamation-circle', success: 'fa-check-circle', info: 'fa-info-circle' };
    container.innerHTML = '<div class="auth-alert auth-alert-' + type + '">' +
        '<i class="fas ' + (icons[type] || icons.info) + '"></i>' +
        '<span>' + message + '</span>' +
        '<button class="alert-close" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>' +
        '</div>';
}

// ─── User Dropdown ──────────────────────────────────────────────────
document.addEventListener('click', function(e) {
    var menu = document.querySelector('.user-menu');
    if (!menu) return;

    if (menu.contains(e.target)) {
        menu.classList.toggle('open');
    } else {
        menu.classList.remove('open');
    }
});

// ─── Logout Function ────────────────────────────────────────────────
function handleLogout() {
    fetch('/api/auth/logout', { method: 'POST' })
        .then(function(r) { return r.json(); })
        .then(function(resp) {
            if (resp.success) {
                window.location.href = '/login';
            }
        })
        .catch(function() {
            window.location.href = '/login';
        });
}

// ─── Auto-init on page load ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
    // Password strength listener
    var pwInput = document.getElementById('password');
    if (pwInput) {
        pwInput.addEventListener('input', function() {
            updatePasswordStrength(this.value);
        });
    }

    // Email validation
    var emailInput = document.getElementById('email');
    if (emailInput) {
        emailInput.addEventListener('blur', function() { validateEmailField(this); });
        emailInput.addEventListener('input', function() {
            if (this.value.trim()) validateEmailField(this);
        });
    }

    // Username validation
    var usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.addEventListener('blur', function() { validateUsernameField(this); });
        usernameInput.addEventListener('input', function() {
            if (this.value.trim()) validateUsernameField(this);
        });
    }

    // Password confirmation
    var confirmPw = document.getElementById('confirmPassword');
    if (confirmPw) {
        confirmPw.addEventListener('input', validatePasswordMatch);
        if (pwInput) {
            pwInput.addEventListener('input', function() {
                if (confirmPw.value) validatePasswordMatch();
            });
        }
    }

    // Setup form handlers
    setupAuthForm('loginForm', '/api/auth/login', '/dashboard');
    setupAuthForm('signupForm', '/api/auth/signup', '/dashboard');
    setupAuthForm('forgotForm', '/api/auth/forgot-password', null);
    setupAuthForm('resetForm', '/api/auth/reset-password', '/login');
});