"""
Route decorators for LSPU ScholarHub.

Usage:
    from app.utils.decorators import login_required, role_required

    @student_bp.route('/dashboard')
    @login_required
    def dashboard():
        ...

    @admin_bp.route('/users')
    @role_required('admin')
    def manage_users():
        ...
"""

from functools import wraps
from flask import session, flash, redirect, url_for


def login_required(f):
    """Redirect to login if the user is not authenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """
    Restrict a route to one or more user roles.

    Example:
        @role_required('admin')
        @role_required('admin', 'staff')

    Role aliases:
        'admin' also matches 'university_admin' and 'campus_admin'
        'staff' also matches 'campus_admin'
    """
    # Expand role aliases
    expanded = set()
    for r in roles:
        expanded.add(r)
        if r == 'admin':
            expanded.update(('university_admin', 'campus_admin'))
        if r == 'staff':
            expanded.add('campus_admin')

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            if session.get('user_type') not in expanded:
                flash('Access denied. You do not have permission to view this page.', 'error')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)
        return decorated
    return decorator
