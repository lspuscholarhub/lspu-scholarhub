"""
Batch Service — handles auto-assignment of approved scholars to batches.

When a student is approved, this service:
1. Finds the scholarship they applied to
2. Looks for an open batch for that scholarship in the current semester
3. If no open batch exists, creates one automatically
4. Assigns the student to that batch
"""
import logging
from datetime import datetime
from app import db

logger = logging.getLogger(__name__)


def _get_or_create_current_period():
    """
    Return the current academic period, or create one automatically based on the current date.
    This ensures auto-batching works even if no periods have been set up yet.
    """
    from app.models import AcademicPeriod

    period = AcademicPeriod.get_current()
    if period:
        return period

    # Auto-create a period based on current date
    now = datetime.utcnow()
    year = now.year
    month = now.month

    if month >= 8 and month <= 12:
        semester = '1st Semester'
        academic_year = f'{year}-{year + 1}'
    elif month >= 1 and month <= 5:
        semester = '2nd Semester'
        academic_year = f'{year - 1}-{year}'
    else:
        semester = 'Inter-Semester'
        academic_year = f'{year - 1}-{year}'

    # Check if this period already exists (just not marked current)
    period = AcademicPeriod.query.filter_by(
        academic_year=academic_year,
        semester=semester,
    ).first()

    if not period:
        period = AcademicPeriod(
            academic_year=academic_year,
            semester=semester,
            is_current=True,
        )
        db.session.add(period)
        db.session.flush()
        logger.info(f'Auto-created academic period: {period.display_name}')
    else:
        # Mark it as current
        AcademicPeriod.query.update({'is_current': False})
        period.is_current = True
        db.session.flush()

    return period


def auto_assign_to_batch(application):
    """
    Automatically assign an approved application to the appropriate batch.
    Creates a new batch if none exists for the scholarship + current period.

    Args:
        application: ScholarshipApplication object (must be approved)

    Returns:
        The ScholarshipBatch the application was assigned to, or None on failure.
    """
    from app.models import ScholarshipBatch
    from app.models.scholarship import ApplicationStatus

    if application.status != ApplicationStatus.APPROVED:
        return None

    try:
        # Get or create current academic period
        current_period = _get_or_create_current_period()
        if not current_period:
            logger.warning('Could not determine or create academic period.')
            return None

        scholarship = application.scholarship

        # Find an open batch for this scholarship in the current period
        batch = ScholarshipBatch.query.filter_by(
            scholarship_id=scholarship.id,
            academic_period_id=current_period.id,
            status='open',
        ).order_by(ScholarshipBatch.batch_number.desc()).first()

        # If no open batch exists, create one
        if not batch:
            batch_name, batch_number = ScholarshipBatch.suggest_next_batch_name(
                scholarship.id, current_period.id
            )
            batch = ScholarshipBatch(
                scholarship_id=scholarship.id,
                academic_period_id=current_period.id,
                batch_name=batch_name,
                batch_number=batch_number,
                amount_per_scholar=scholarship.award_amount,
                status='open',
            )
            db.session.add(batch)
            db.session.flush()  # get batch.id
            logger.info(f'Auto-created batch "{batch_name}" for {scholarship.title}')

        # Assign the application to this batch
        application.batch_id = batch.id
        application.academic_period_id = current_period.id
        application.amount_received = batch.amount_per_scholar

        # Recalculate batch totals
        batch.recalculate_totals()

        return batch

    except Exception as e:
        logger.error(f'Auto-batch assignment failed: {e}')
        return None


def auto_assign_multiple(applications):
    """
    Auto-assign multiple approved applications to batches.
    Groups by scholarship so each scholarship gets its own batch.

    Returns dict: {scholarship_title: batch_name}
    """
    results = {}
    for app in applications:
        batch = auto_assign_to_batch(app)
        if batch:
            results[app.scholarship.title] = batch.batch_name
    return results
