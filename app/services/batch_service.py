"""
Batch Service — handles auto-assignment of approved scholars to batches.

When a student is approved, this service:
1. Finds the scholarship they applied to
2. Looks for an open batch for that scholarship + campus in the current semester
3. If no open batch exists, creates one automatically
4. Assigns the student to that batch

A failure here never loses the approval: the application stays approved with
no batch, which the Batches page lists as an unbatched scholar.
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


def application_campus(application):
    """The campus an application is really for.

    Applications are stamped with the applicant's campus when they are filed; a
    row without one falls back to the applicant's current campus instead of
    counting as campus-less and slipping past every campus check.
    """
    campus_id = application.campus_id
    if campus_id is None and application.applicant is not None:
        campus_id = application.applicant.campus_id
    return campus_id


def batch_campus(batch):
    """The campus a batch pays out on: its own, else its program's.

    Batches created before campus stamping — and every auto-created batch — carry
    no campus of their own, so a batch for a campus-scoped program is pinned by
    that program rather than reading as "all campuses". Only a university-wide
    program leaves the batch campus open, and the first scholar assigned fixes it.
    """
    if batch.campus_id:
        return batch.campus_id
    scholarship = batch.scholarship
    return scholarship.campus_id if scholarship else None


def campus_batch_filter(query, campus_id):
    """Restrict a ScholarshipBatch query to the batches that pay out on a campus.

    An unpinned batch is read through its program, exactly as
    :func:`batch_campus` does, so a batch created before campus stamping is
    listed for the campus its program belongs to instead of disappearing from
    that campus's Batches page.
    """
    from app.models import Scholarship, ScholarshipBatch

    return query.filter(db.or_(
        ScholarshipBatch.campus_id == campus_id,
        db.and_(ScholarshipBatch.campus_id.is_(None),
                ScholarshipBatch.scholarship.has(Scholarship.campus_id == campus_id)),
    ))


def campus_application_filter(query, campus_id):
    """Restrict a ScholarshipApplication query to one campus.

    An application row without its own campus stamp is read through its
    applicant — the same fallback :func:`application_campus` uses — so such a
    scholar still appears on their campus's unbatched list.
    """
    from app.models import ScholarshipApplication, User

    return query.filter(db.or_(
        ScholarshipApplication.campus_id == campus_id,
        db.and_(ScholarshipApplication.campus_id.is_(None),
                ScholarshipApplication.applicant.has(User.campus_id == campus_id)),
    ))


def assign_applications_to_batch(batch, app_ids):
    """Attach posted applications to a batch, refusing everything that does not
    belong to it.

    A form can be hand-crafted, so an id arriving here is a claim, not a fact:
    only approved applications for this batch's scholarship — and from the
    batch's campus, as resolved by :func:`batch_campus` — are attached. Everything
    else comes back as ``skipped`` with a reason, so the caller can say what it
    refused instead of quietly moving a stranger into the batch.

    Returns (assigned_applications, skipped) where skipped is [(app_id, reason)].
    """
    from app.models import ScholarshipApplication
    from app.models.scholarship import ApplicationStatus

    assigned, skipped = [], []
    campus = batch_campus(batch)
    for raw in app_ids:
        try:
            app_id = int(raw)
        except (TypeError, ValueError):
            skipped.append((raw, 'not an application id'))
            continue

        application = db.session.get(ScholarshipApplication, app_id)
        if not application:
            skipped.append((app_id, 'no such application'))
        elif application.status != ApplicationStatus.APPROVED:
            skipped.append((app_id, 'not approved'))
        elif application.scholarship_id != batch.scholarship_id:
            skipped.append((app_id, 'different scholarship'))
        elif (campus and application_campus(application)
              and application_campus(application) != campus):
            skipped.append((app_id, 'different campus'))
        else:
            if campus is None:
                # University-wide program: the batch pays out where its first
                # scholar studies, and stays there for everyone after them.
                campus = application_campus(application)
                if campus:
                    batch.campus_id = campus
            application.batch_id = batch.id
            application.amount_received = batch.amount_per_scholar
            assigned.append(application)

    if assigned:
        db.session.flush()          # the batch's own totals query must see the links
        batch.recalculate_totals()
    return assigned, skipped


def auto_assign_to_batch(application):
    """
    Automatically assign an approved application to the appropriate batch.
    Creates a new batch if none exists for the scholarship + campus + period.

    Args:
        application: ScholarshipApplication object (must be approved)

    Returns:
        The ScholarshipBatch the application was assigned to, or None when it
        could not be batched (cross-campus, or a failure).
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
        app_campus = application_campus(application)

        # Find an open batch for this scholarship in the current period, on the
        # scholar's campus — a batch that has not been pinned to a campus yet is
        # still a candidate.
        batch_q = ScholarshipBatch.query.filter_by(
            scholarship_id=scholarship.id,
            academic_period_id=current_period.id,
            status='open',
        )
        if app_campus:
            batch_q = batch_q.filter(db.or_(ScholarshipBatch.campus_id == app_campus,
                                            ScholarshipBatch.campus_id.is_(None)))
        batch = batch_q.order_by(ScholarshipBatch.batch_number.desc()).first()

        # If no open batch exists, create one for this campus
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
                campus_id=app_campus or scholarship.campus_id,
            )
            db.session.add(batch)
            db.session.flush()  # get batch.id
            logger.info(f'Auto-created batch "{batch_name}" for {scholarship.title}')

        # The batch's campus (its own, or its program's) is binding: a scholar
        # from another campus is left unbatched for an admin to place, never
        # folded into a batch that pays out somewhere else.
        batch_campus_id = batch_campus(batch)
        if batch_campus_id and app_campus and batch_campus_id != app_campus:
            logger.warning(
                'Application %s is from campus %s but batch %s (%s) pays out on campus %s; left unbatched.',
                getattr(application, 'id', None), app_campus, batch.id,
                batch.batch_name, batch_campus_id)
            return None
        if batch.campus_id is None and app_campus:
            batch.campus_id = app_campus

        # Assign the application to this batch
        application.batch_id = batch.id
        application.academic_period_id = current_period.id
        application.amount_received = batch.amount_per_scholar

        # Recalculate batch totals
        batch.recalculate_totals()

        return batch

    except Exception:
        # A broken auto-assignment must not take the approval down with it, and it
        # must not be invisible either: the traceback goes to the log, the
        # application keeps batch_id NULL, and the approving screen warns and
        # points at the Batches page, where the scholar is listed. No rollback
        # here — that would throw away the approval the caller has not committed
        # yet; only a session the failure already broke is cleaned up.
        logger.exception('Auto-batch assignment failed for application %s',
                         getattr(application, 'id', None))
        if not db.session.is_active:
            db.session.rollback()
        return None


def auto_assign_multiple(applications):
    """
    Auto-assign multiple approved applications to batches.
    Groups by scholarship so each scholarship gets its own batch.

    Returns (results, unbatched): ``results`` maps scholarship title →
    batch name for the ones that landed, and ``unbatched`` lists the
    applications still approved with no batch, so the caller can put them in
    front of an admin instead of dropping them.
    """
    results, unbatched = {}, []
    for app in applications:
        batch = auto_assign_to_batch(app)
        if batch:
            results[app.scholarship.title] = batch.batch_name
        else:
            unbatched.append(app)
    return results, unbatched
