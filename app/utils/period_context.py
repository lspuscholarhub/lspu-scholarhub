"""
Period context helper — returns the period being viewed (from session)
or falls back to the current active period.

Usage in any view:
    from app.utils.period_context import get_viewing_period
    current_period = get_viewing_period()
"""
from flask import session
from app.models.academic_period import AcademicPeriod


def get_viewing_period():
    """Return the period the user chose to view, or the current active period."""
    vid = session.get('viewing_period_id')
    if vid:
        p = AcademicPeriod.query.get(vid)
        if p:
            return p
    return AcademicPeriod.get_current()


def is_viewing_specific_period():
    """Return True only if the user explicitly selected a non-current period.
    When False, views should show all-time data (no period filter)."""
    vid = session.get('viewing_period_id')
    if not vid:
        return False
    current = AcademicPeriod.get_current()
    return current is None or vid != current.id
