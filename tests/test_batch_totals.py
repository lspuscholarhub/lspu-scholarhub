"""A batch's total_scholars and total_amount must always describe its approved
applications: the dashboards' money figures are these columns, not a live sum.

The model watches the session for application changes, so these tests exercise
plain ORM paths (status edit, unlink, delete) rather than the routes that already
called recalculate_totals() explicitly.
"""
import pytest

from app import db
from app.models import ScholarshipApplication, ScholarshipBatch
from app.models.scholarship import ApplicationStatus
from app.services.batch_service import assign_applications_to_batch


def _expected(batch):
    apps = [a for a in batch.applications if a.status == ApplicationStatus.APPROVED]
    if batch.amount_per_scholar:
        total = float(batch.amount_per_scholar) * len(apps)
    else:
        total = sum(float(a.amount_received or 0) for a in apps)
    return len(apps), total


def _assert_totals_match(batch):
    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    expected_count, expected_total = _expected(batch)
    assert (batch.total_scholars, float(batch.total_amount)) == (expected_count, expected_total)


def _assert_every_batch_matches():
    db.session.expire_all()
    for batch in ScholarshipBatch.query.all():
        expected_count, expected_total = _expected(batch)
        assert (batch.total_scholars, float(batch.total_amount)) == (expected_count, expected_total), \
            f'batch {batch.id} ({batch.batch_name}) drifted'


def test_totals_follow_status_batch_and_deletion_changes(open_batch, seed, approve):
    first = approve(seed.student, seed.program)
    second = approve(seed.other_student, seed.program, campus_id=seed.campus.id)

    assign_applications_to_batch(open_batch, [str(first.id), str(second.id)])
    db.session.commit()
    _assert_totals_match(open_batch)
    assert open_batch.total_scholars == 2

    first.status = ApplicationStatus.REJECTED        # status change only
    db.session.commit()
    _assert_totals_match(open_batch)
    assert open_batch.total_scholars == 1

    second.batch_id = None                            # unlink from the batch
    db.session.commit()
    _assert_totals_match(open_batch)
    assert open_batch.total_scholars == 0

    second.batch_id = open_batch.id                   # link it again
    db.session.commit()
    _assert_totals_match(open_batch)
    assert open_batch.total_scholars == 1

    db.session.delete(second)                         # deletion
    db.session.commit()
    _assert_totals_match(open_batch)
    assert open_batch.total_scholars == 0
    _assert_every_batch_matches()


def test_totals_hold_across_two_batches_and_a_move(open_batch, seed, approve):
    from app.models import ScholarshipBatch

    other = ScholarshipBatch(scholarship_id=seed.program.id,
                             academic_period_id=seed.period.id,
                             batch_name='Batch 2', batch_number=2,
                             amount_per_scholar=4000, status='open',
                             campus_id=seed.campus.id)
    db.session.add(other)
    db.session.commit()

    scholar = approve(seed.student, seed.program)
    assign_applications_to_batch(open_batch, [str(scholar.id)])
    assign_applications_to_batch(other, [str(scholar.id)])     # moves it
    db.session.commit()

    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 0
    assert db.session.get(ScholarshipBatch, other.id).total_scholars == 1
    _assert_every_batch_matches()
