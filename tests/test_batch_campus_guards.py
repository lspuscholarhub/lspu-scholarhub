"""Campus guards around manual and automatic batch assignment.

An id posted to the assign form, or an approved application reaching
auto-assignment, is a claim about the batch and campus it belongs to. These tests
pin what the service refuses and what it must never move.
"""
import pytest

from app import db
from app.models import Scholarship, ScholarshipApplication, ScholarshipBatch
from app.models.scholarship import ApplicationStatus
from app.services.batch_service import assign_applications_to_batch, auto_assign_to_batch


@pytest.fixture()
def other_program(seed):
    program = Scholarship(title='Other Grant', description='d',
                          eligibility_criteria='e', benefits='b',
                          created_by=seed.admin.id, campus_id=seed.campus.id,
                          funding_type='private', award_amount=2500)
    db.session.add(program)
    db.session.commit()
    return program


def test_assign_route_only_takes_approved_apps_from_its_own_program(open_batch, other_program,
                                                                     seed, approve, sign_in):
    """Sections 1-3: junk, pending and foreign-program ids are refused, a real one lands."""
    pending = approve(seed.student, seed.program, status=ApplicationStatus.PENDING)
    foreign = approve(seed.student, other_program)
    good = approve(seed.student, seed.program)

    client = sign_in(seed.admin)
    response = client.post(f'/admin/batches/{open_batch.id}/assign',
                           data={'app_ids': ['abc', str(pending.id), str(foreign.id)]})
    assert response.status_code == 302

    db.session.expire_all()
    assert db.session.get(ScholarshipApplication, pending.id).batch_id is None
    assert db.session.get(ScholarshipApplication, foreign.id).batch_id is None

    response = client.post(f'/admin/batches/{open_batch.id}/assign',
                           data={'app_ids': [str(good.id)]})
    assert response.status_code == 302

    db.session.expire_all()
    assigned = db.session.get(ScholarshipApplication, good.id)
    assert assigned.batch_id == open_batch.id
    assert float(assigned.amount_received) == 10000
    refreshed = db.session.get(ScholarshipBatch, open_batch.id)
    assert (refreshed.total_scholars, float(refreshed.total_amount)) == (1, 10000.0)


def test_campus_less_batch_reads_its_program_campus(seed, approve):
    """Section 4: an unpinned batch still refuses a scholar from another campus."""
    row = ScholarshipBatch(scholarship_id=seed.program.id,
                           academic_period_id=seed.period.id,
                           batch_name='Batch 1', batch_number=1,
                           amount_per_scholar=10000, status='open', campus_id=None)
    db.session.add(row)
    db.session.commit()

    outsider = approve(seed.other_student, seed.program, campus_id=None)

    assigned, skipped = assign_applications_to_batch(row, [str(outsider.id)])

    assert assigned == []
    assert [reason for _, reason in skipped] == ['different campus']
    assert db.session.get(ScholarshipApplication, outsider.id).batch_id is None
    assert db.session.get(ScholarshipBatch, row.id).campus_id is None


def test_auto_assignment_leaves_a_cross_campus_scholar_alone(seed, approve):
    """Section 6: no batch is created, and the application stays unbatched."""
    scholar = approve(seed.other_student, seed.program, campus_id=None)
    batches_before = ScholarshipBatch.query.count()

    assert auto_assign_to_batch(scholar) is None
    db.session.commit()

    assert db.session.get(ScholarshipApplication, scholar.id).batch_id is None
    assert ScholarshipBatch.query.count() == batches_before


def test_university_wide_program_batches_per_campus(seed, approve):
    """Section 5: each campus gets its own pinned batch, and the first one stays put."""
    university_wide = Scholarship(title='University-Wide Grant', description='d',
                                  eligibility_criteria='e', benefits='b',
                                  created_by=seed.admin.id, campus_id=None,
                                  scope='university', funding_type='private',
                                  award_amount=5000)
    db.session.add(university_wide)
    db.session.commit()

    first_batch = ScholarshipBatch(scholarship_id=university_wide.id,
                                   academic_period_id=seed.period.id,
                                   batch_name='Batch 1', batch_number=1,
                                   amount_per_scholar=5000, status='open',
                                   campus_id=None)
    db.session.add(first_batch)
    db.session.commit()

    campus_one = approve(seed.student, university_wide, campus_id=seed.campus.id)
    assigned, _ = assign_applications_to_batch(first_batch, [str(campus_one.id)])
    db.session.commit()
    assert len(assigned) == 1
    assert db.session.get(ScholarshipBatch, first_batch.id).campus_id == seed.campus.id

    campus_two = approve(seed.other_student, university_wide, campus_id=None)
    own_batch = auto_assign_to_batch(campus_two)
    db.session.commit()

    assert own_batch is not None
    assert own_batch.id != first_batch.id
    assert own_batch.campus_id == seed.other_campus.id
    assert db.session.get(ScholarshipBatch, first_batch.id).campus_id == seed.campus.id

    assigned, skipped = assign_applications_to_batch(first_batch, [str(campus_two.id)])
    assert assigned == []
    assert [reason for _, reason in skipped] == ['different campus']
    assert db.session.get(ScholarshipApplication, campus_two.id).batch_id == own_batch.id


@pytest.mark.parametrize('status', ['closed', 'finalized'])
def test_settled_batch_refuses_assignment(status, open_batch, seed, approve, sign_in):
    """A closed or finalized batch is history: the form must not add scholars to it."""
    open_batch.status = status
    db.session.commit()
    scholar = approve(seed.student, seed.program)

    client = sign_in(seed.admin)
    response = client.post(f'/admin/batches/{open_batch.id}/assign',
                           data={'app_ids': [str(scholar.id)]})
    assert response.status_code == 302

    db.session.expire_all()
    assert db.session.get(ScholarshipApplication, scholar.id).batch_id is None
    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 0


def test_settled_batch_is_refused_by_the_service_too(open_batch, seed, approve):
    """The guard lives in the service, so every caller gets it, not only the route."""
    open_batch.status = 'finalized'
    db.session.commit()
    scholar = approve(seed.student, seed.program)

    assigned, skipped = assign_applications_to_batch(open_batch, [str(scholar.id)])

    assert assigned == []
    assert [reason for _, reason in skipped] == ['batch is finalized']
    assert db.session.get(ScholarshipApplication, scholar.id).batch_id is None


def test_manual_assignment_stamps_the_batch_period(open_batch, seed, approve):
    """A manually assigned scholar joins the batch's period, not a null one."""
    scholar = approve(seed.student, seed.program)
    assert scholar.academic_period_id is None

    assigned, skipped = assign_applications_to_batch(open_batch, [str(scholar.id)])
    db.session.commit()

    assert [a.id for a in assigned] == [scholar.id]
    assert skipped == []
    saved = db.session.get(ScholarshipApplication, scholar.id)
    assert saved.academic_period_id == seed.period.id
    assert saved.batch_id == open_batch.id


def test_failed_auto_assignment_leaves_the_approval_commitable(seed, approve):
    """A broken auto-assignment returns None, keeps the session usable and keeps
    the approval row, so the caller's own commit still lands."""
    orphan = approve(seed.student, scholarship_id=9999, campus_id=None)
    batches_before = ScholarshipBatch.query.count()

    assert auto_assign_to_batch(orphan) is None        # its program row does not exist
    assert db.session.is_active

    db.session.commit()                                # what the caller does next

    saved = db.session.get(ScholarshipApplication, orphan.id)
    assert saved is not None
    assert saved.status == ApplicationStatus.APPROVED
    assert saved.batch_id is None
    assert ScholarshipBatch.query.count() == batches_before
