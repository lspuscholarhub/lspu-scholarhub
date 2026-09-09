"""
Campus context service — centralizes campus filtering logic.

Every query that lists students, scholarships, applications, batches,
announcements, or notifications uses this to determine which campus's
data to show.
"""
from flask import session, g


def get_current_user():
    """Get the current user from the session."""
    from app.models import User
    uid = session.get('user_id')
    if not uid:
        return None
    return User.query.get(uid)


def get_campus_context():
    """Return the campus_id to filter queries by.

    - University admin: reads from session['campus_context'] (can be None = all)
    - Campus admin/staff/student: returns their own campus_id
    - None: no campus filter (show all — used by university admin default)
    """
    user = get_current_user()
    if not user:
        return None

    user_type = user.user_type

    # University admin can switch campus context
    if user_type == 'super_admin':
        return session.get('campus_context')   # None means "show all campuses"

    # Everyone else is scoped to their own campus
    return user.campus_id


def is_super_admin():
    """Check if the current user is a university admin."""
    user = get_current_user()
    return user and user.user_type == 'super_admin'


def get_all_campuses():
    """Return all active campuses."""
    from app.models import Campus
    return Campus.query.filter_by(is_active=True).order_by(Campus.id).all()


def filter_by_campus(query, model_class, campus_id=None):
    """Apply campus filter to a SQLAlchemy query.

    If campus_id is None, no filter is applied (show all — university admin view).
    If campus_id is set, filter by that campus.
    """
    if campus_id is None:
        return query
    return query.filter(model_class.campus_id == campus_id)
