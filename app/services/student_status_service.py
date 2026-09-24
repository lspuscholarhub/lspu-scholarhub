"""Student lifecycle status: active / graduated / dropped_out.

Single write-point for status changes so the future ICTS / LSPU-portal sync
can reuse exactly the same rules (auto-closing active scholarships +
audit trail).  Statuses are intentionally simple strings on User so an
external import can set them directly as well.

Rules:
  - graduated / dropped_out  -> every ACTIVE scholarship application of the
    student is closed (scholar_status + is_active) so batches, monitoring,
    dashboards and reports stop counting them as active scholars.
  - active                   -> the status tag only; scholarships already
    closed are NOT reopened (history is preserved).
"""
from datetime import date

from app import db

VALID_STATUSES = ('active', 'graduated', 'dropped_out')

# student status -> scholar_status written onto active applications
_SCHOLAR_STATUS = {
    'graduated':   'graduated',
    'dropped_out': 'dropped_out',
}


def set_student_status(user, new_status, actor_id=None):
    """Set a student's status and auto-close active scholarships when they
    leave (graduated / dropped_out).

    Returns (ok, error_message).  Exactly one is truthy.
    """
    if new_status not in VALID_STATUSES:
        return False, 'Invalid student status.'
    if user.user_type != 'student':
        return False, 'Status can only be set on students.'

    changed = (user.student_status or 'active') != new_status
    user.student_status = new_status
    user.status_date = date.today() if new_status != 'active' else None

    closed = 0
    if new_status in _SCHOLAR_STATUS:
        from app.models import ScholarshipApplication
        active_apps = ScholarshipApplication.query.filter_by(
            applicant_id=user.id, is_active=True).filter(
            ScholarshipApplication.scholar_status != 'graduated',
            ScholarshipApplication.scholar_status != 'dropped_out',
        ).all()
        for a in active_apps:
            a.scholar_status = _SCHOLAR_STATUS[new_status]
            a.is_active = False
            closed += 1

    db.session.commit()

    if changed:
        try:
            from app.services.audit_service import log_action
            log_action(
                'user.status_change',
                f'{user.get_full_name()} ({user.student_id}) marked as '
                f'{new_status.replace("_", " ")}'
                + (f' — {closed} active scholarship(s) closed' if closed else ''),
                category='user', target_type='user', target_id=user.id,
                user_id=actor_id)
        except Exception:
            pass  # audit must never break the status change

    return True, None
