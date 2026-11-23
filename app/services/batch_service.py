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
    from app.models import ScholarshipBatch

    return query.filter(db.or_(
        ScholarshipBatch.campus_id == campus_id,
        db.and_(ScholarshipBatch.campus_id.is_(None),
                ScholarshipBatch.scholarship.has(campus_id=campus_id)),
    ))


def campus_application_filter(query, campus_id):
    """Restrict a ScholarshipApplication query to one campus.

    An application row without its own campus stamp is read through its
    applicant — the same fallback :func:`application_campus` uses — so such a
    scholar still appears on their campus's unbatched list.
    """
    from app.models import ScholarshipApplication

    return query.filter(db.or_(
        ScholarshipApplication.campus_id == campus_id,
        db.and_(ScholarshipApplication.campus_id.is_(None),
                ScholarshipApplication.applicant.has(campus_id=campus_id)),
    ))


def recalculate_batch_totals(*batch_ids):
    """Recompute the totals of the batches named; unknown ids are skipped.

    total_scholars / total_amount (and the male/female counts) are denormalised
    copies of a batch's approved applications, and the dashboards read them. Every
    place that changes an application's status or batch must call this once the
    change has been flushed — ``db.session.flush()`` first, or the recount reads
    the old rows. The cached collection is dropped first so an application that
    has just left or joined is counted where it now belongs.
    """
    from app.models import ScholarshipBatch

    ids = {int(i) for i in batch_ids if i}
    if not ids:
        return
    for batch in ScholarshipBatch.query.filter(ScholarshipBatch.id.in_(ids)).all():
        db.session.expire(batch, ['applications'])
        batch.recalculate_totals()


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

    if batch.status in ('closed', 'finalized'):
        # A settled batch is history: reopening it is a deliberate act, not a
        # side effect of posting a form that was still open in a tab.
        return [], [(raw, f'batch is {batch.status}') for raw in app_ids]

    assigned, skipped = [], []
    former_batches = set()
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
            continue
        if application.status != ApplicationStatus.APPROVED:
            skipped.append((app_id, 'not approved'))
            continue
        if application.scholarship_id != batch.scholarship_id:
            skipped.append((app_id, 'different scholarship'))
            continue

        app_campus = application_campus(application)
        if campus and app_campus and app_campus != campus:
            skipped.append((app_id, 'different campus'))
            continue
        if campus is None and app_campus:
            # University-wide program: the batch pays out where its first
            # scholar studies, and stays there for everyone after them.
            campus = app_campus
            batch.campus_id = app_campus
        if application.batch_id and application.batch_id != batch.id:
            former_batches.add(application.batch_id)
        application.batch_id = batch.id
        application.amount_received = batch.amount_per_scholar
        if batch.academic_period_id:
            # The batch's period is the payout's period, so the application moves
            # to it even when the scholar applied under an earlier one: the
            # alternative leaves a period that contradicts the batch, and the
            # scholar missing from that period's counts and exports. This is the
            # same rule auto_assign_to_batch() applies with the current period.
            application.academic_period_id = batch.academic_period_id
        assigned.append(application)

    if assigned:
        db.session.flush()          # the batch's own totals query must see the links
        batch.recalculate_totals()
        recalculate_batch_totals(*former_batches)   # batches this scholar left
    return assigned, skipped


def create_batch_or_reuse(scholarship, period_id, batch_name, batch_number,
                          amount_per_scholar, created_by=None, campus_id=None):
    """Create a batch, or return the one that already owns its number.

    A double-submitted form or two clicks racing each other hit the unique
    (scholarship, period, batch_number) rule. The caller gets the existing row
    and ``created=False`` so it can say so, instead of a database error.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models import ScholarshipBatch

    candidate = ScholarshipBatch(
        scholarship_id=scholarship.id,
        academic_period_id=period_id,
        batch_name=batch_name,
        batch_number=batch_number,
        amount_per_scholar=amount_per_scholar,
        campus_id=scholarship.campus_id if campus_id is None else campus_id,
        created_by=created_by,
    )
    try:
        with db.session.begin_nested():
            db.session.add(candidate)
            db.session.flush()
        return candidate, True
    except IntegrityError:
        existing = ScholarshipBatch.query.filter_by(
            scholarship_id=scholarship.id,
            academic_period_id=period_id,
            batch_number=batch_number,
        ).first()
        logger.info('Batch "%s" already exists (%s); reusing it.',
                    batch_name, getattr(existing, 'id', None))
        return existing, False


def _open_batches_for(scholarship_id, period_id, campus):
    """Open batches for a program/period, including unpinned campus-less ones."""
    from app.models import ScholarshipBatch

    query = ScholarshipBatch.query.filter_by(
        scholarship_id=scholarship_id,
        academic_period_id=period_id,
        status='open',
    )
    if campus:
        query = query.filter(db.or_(ScholarshipBatch.campus_id == campus,
                                    ScholarshipBatch.campus_id.is_(None)))
    return query.order_by(ScholarshipBatch.batch_number.desc())


def _create_open_batch(scholarship, period, campus):
    """Create the next open batch, or join the one a racing approval just made.

    The insert runs inside a SAVEPOINT so the unique (scholarship, period,
    batch_number) rule can reject a duplicate without discarding the approval the
    caller has not committed yet; the loser then re-reads and joins the winner.
    """
    from sqlalchemy.exc import IntegrityError

    from app.models import ScholarshipBatch

    for _attempt in range(2):
        batch_name, batch_number = ScholarshipBatch.suggest_next_batch_name(
            scholarship.id, period.id
        )
        candidate = ScholarshipBatch(
            scholarship_id=scholarship.id,
            academic_period_id=period.id,
            batch_name=batch_name,
            batch_number=batch_number,
            amount_per_scholar=scholarship.award_amount,
            status='open',
            campus_id=campus,
        )
        try:
            with db.session.begin_nested():
                db.session.add(candidate)
                db.session.flush()          # get batch.id, and hit the constraint
            logger.info('Auto-created batch "%s" for %s', batch_name, scholarship.title)
            return candidate
        except IntegrityError:
            winner = _open_batches_for(scholarship.id, period.id, campus).first()
            if winner:
                logger.info('Batch "%s" was created concurrently; joining it.',
                            winner.batch_name)
                return winner
    return None


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

        # A campus-scoped program binds its scholars: one from another campus is
        # left unbatched for an admin to place, exactly as the manual assignment
        # refuses them. A university-wide program has no such limit — its batches
        # are per campus, so each campus gets its own.
        if scholarship.campus_id and app_campus and app_campus != scholarship.campus_id:
            logger.warning(
                'Application %s is from campus %s but "%s" is a campus %s program; left unbatched.',
                getattr(application, 'id', None), app_campus,
                scholarship.title, scholarship.campus_id)
            return None
        campus = scholarship.campus_id or app_campus

        # Find an open batch for this scholarship in the current period, on this
        # campus — a batch not pinned to a campus yet is still a candidate.
        batch = _open_batches_for(scholarship.id, current_period.id, campus).first()

        # If no open batch exists, create one for this campus — or join the one a
        # racing approval created while this one was being placed.
        if not batch:
            batch = _create_open_batch(scholarship, current_period, campus)
            if batch is None:
                logger.warning('Could not create or find a batch for "%s".',
                               scholarship.title)
                return None

        if batch.campus_id is None and campus:
            batch.campus_id = campus

        # Assign the application to this batch
        previous_batch_id = application.batch_id
        application.batch_id = batch.id
        application.academic_period_id = current_period.id
        application.amount_received = batch.amount_per_scholar

        # Recalculate batch totals
        batch.recalculate_totals()
        if previous_batch_id and previous_batch_id != batch.id:
            recalculate_batch_totals(previous_batch_id)

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
