"""Student-facing application flow: apply, withdraw, reapply, status display.

The list page keeps the most recent application per program; the detail page now
does the same, so a reapply never resurrects the old withdrawn row or its
"Re-apply" button.
"""
import pytest

from app import db
from app.models import ScholarshipApplication
from app.models.scholarship import ApplicationStatus

APPLY_FORM = {'terms': 'on', 'privacy': 'on', 'units_enrolled': '18'}


@pytest.fixture()
def student_client(seed, sign_in):
    """A verified student signed in, with their own program open for applications."""
    seed.student.is_verified = True
    db.session.commit()
    return sign_in(seed.student)


def _apply(client, program):
    return client.post(f'/scholarship/apply/{program.id}', data=APPLY_FORM)


def test_apply_creates_a_pending_application(student_client, seed):
    response = _apply(student_client, seed.program)
    assert response.status_code == 302

    rows = ScholarshipApplication.query.filter_by(applicant_id=seed.student.id).all()
    assert len(rows) == 1
    assert rows[0].status is ApplicationStatus.PENDING
    assert rows[0].academic_period_id == seed.period.id


def test_duplicate_application_is_blocked(student_client, seed, approve):
    existing = approve(seed.student, seed.program, status=ApplicationStatus.PENDING,
                       period=seed.period)

    response = _apply(student_client, seed.program)

    assert response.status_code == 302
    rows = ScholarshipApplication.query.filter_by(applicant_id=seed.student.id).all()
    assert [row.id for row in rows] == [existing.id]


def test_withdraw_marks_the_application_withdrawn(student_client, seed, approve):
    application = approve(seed.student, seed.program, status=ApplicationStatus.PENDING,
                          period=seed.period)

    response = student_client.post(
        f'/scholarship/application/{application.id}/withdraw',
        data={'withdraw_reason': 'Schedule conflict'},
    )

    assert response.status_code == 302
    db.session.expire_all()
    withdrawn = db.session.get(ScholarshipApplication, application.id)
    assert withdrawn.status is ApplicationStatus.WITHDRAWN
    assert 'Schedule conflict' in withdrawn.review_notes


def test_reapply_shows_the_new_application_on_the_detail_page(student_client, seed, approve):
    old = approve(seed.student, seed.program, status=ApplicationStatus.WITHDRAWN,
                  period=seed.period)

    assert _apply(student_client, seed.program).status_code == 302

    rows = ScholarshipApplication.query.filter_by(applicant_id=seed.student.id).all()
    assert len(rows) == 2
    newest = max(rows, key=lambda row: row.id)
    assert newest.id != old.id
    assert newest.status is ApplicationStatus.PENDING

    detail = student_client.get(f'/scholarship/{seed.program.id}')
    assert detail.status_code == 200
    body = detail.data
    assert b'Already applied' in body
    assert b'Re-apply' not in body
    assert b'Apply again' not in body


def test_withdrawn_status_appears_on_both_pages(student_client, seed, approve):
    application = approve(seed.student, seed.program, status=ApplicationStatus.PENDING,
                          period=seed.period)
    student_client.post(f'/scholarship/application/{application.id}/withdraw',
                        data={'withdraw_reason': 'Changed my mind'})

    detail = student_client.get(f'/scholarship/{seed.program.id}')
    assert detail.status_code == 200
    assert b'Re-apply' in detail.data            # withdrawn may apply again

    listing = student_client.get('/scholarship/?view=mine')
    assert listing.status_code == 200
    assert b'Withdrawn' in listing.data
    assert f'Application #{application.id}'.encode() in listing.data
