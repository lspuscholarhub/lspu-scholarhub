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


def batch_in_campus_context(batch, campus_id):
    """Whether a campus-scoped viewer may see and act on this batch.

    No campus context (super admin showing every campus) allows anything. A
    batch with no campus of its own and no campus-scoped program is open to every
    campus — a university-wide batch before its first scholar pins it — which is
    the same rule the Batches page lists by.
    """
    if not campus_id:
        return True
    from app.services.batch_service import batch_campus

    campus = batch_campus(batch)
    return campus is None or campus == campus_id


def campus_scoped_batch_or_404(batch_id):
    """Load a batch, treating another campus's batch as non-existent.

    404 rather than 403 on purpose: an id from another campus should look exactly
    like an id that was never issued.
    """
    from flask import abort

    from app.models import ScholarshipBatch

    batch = ScholarshipBatch.query.get_or_404(batch_id)
    if not batch_in_campus_context(batch, current_campus_context()):
        abort(404)
    return batch


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
