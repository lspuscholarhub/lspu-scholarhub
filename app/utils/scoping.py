"""The campus and period a request's data is limited to.

The reports pages and the exports they offer must resolve both the same way, or
the file a campus admin downloads disagrees with the page that produced it. Keep
the rules here so there is one place to change them.
"""


def current_campus_context():
    """The campus the viewer is scoped to; None means every campus.

    A super admin follows the campus selector in the session; everyone else is
    pinned to their own campus.
    """
    from flask import session

    from app import db
    from app.models import User

    if session.get('user_type') == 'super_admin':
        return session.get('campus_context')          # None = all campuses
    me = db.session.get(User, session.get('user_id'))
    return me.campus_id if me else None


def current_period_filters():
    """Filters describing the period the viewer is looking at.

    ``period_id`` is the period itself (chosen, or the current one when nothing
    is selected); ``period_is_specific`` says whether the viewer picked a past
    period on purpose, which is when student rosters get period-filtered.
    """
    from app.utils.period_context import (get_viewing_period,
                                          is_viewing_specific_period)

    period = get_viewing_period()
    if not period:
        return {}
    return {'period_id': period.id,
            'period_is_specific': is_viewing_specific_period()}
