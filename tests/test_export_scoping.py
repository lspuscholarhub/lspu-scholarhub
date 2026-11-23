"""Report exports follow the campus scoping of the reports pages they mirror.

The page a campus admin sees is filtered to their campus; the file they download
has to be the same data, or the export quietly becomes a way around the scoping.
"""
import pytest

from app import db
from app.models import Scholarship, User
from app.models.scholarship import ScholarshipStatus


@pytest.fixture()
def other_program(seed):
    program = Scholarship(title='Other Campus Grant', description='d',
                          eligibility_criteria='e', benefits='b',
                          created_by=seed.admin.id, campus_id=seed.other_campus.id,
                          funding_type='private', award_amount=3000,
                          status=ScholarshipStatus.ACTIVE)
    db.session.add(program)
    db.session.commit()
    return program


def _export(client, report_type, path='/admin/reports/export', extra=''):
    response = client.get(f'{path}?type={report_type}&format=csv{extra}')
    assert response.status_code == 200
    assert response.mimetype == 'text/csv'
    return response.get_data(as_text=True)


@pytest.mark.parametrize('report_type', ['applications', 'approved', 'students'])
def test_campus_admin_export_leaves_out_other_campuses(report_type, seed, approve, sign_in):
    approve(seed.student, seed.program)
    approve(seed.other_student, seed.program, campus_id=seed.other_campus.id)

    for path, user in (('/admin/reports/export', seed.admin),
                       ('/staff/reports/export', seed.staff)):
        body = _export(sign_in(user), report_type, path)
        assert 'Test Student' in body
        assert 'Other Student' not in body


def test_campus_admin_program_export_is_scoped_too(seed, other_program, sign_in):
    body = _export(sign_in(seed.admin), 'scholarships')
    assert 'Test Grant' in body
    assert 'Other Campus Grant' not in body


def test_campus_cannot_be_requested_from_the_query_string(seed, approve, sign_in):
    """Scoping comes from the session, so appending campus_id must not widen it."""
    approve(seed.other_student, seed.program, campus_id=seed.other_campus.id)

    body = _export(sign_in(seed.admin), 'applications',
                   extra=f'&campus_id={seed.other_campus.id}')
    assert 'Other Student' not in body


def test_super_admin_export_still_spans_every_campus(seed, approve, sign_in):
    super_admin = User(username='t-super', email='super@example.test', password_hash='x',
                       first_name='Super', last_name='Admin', user_type='super_admin')
    db.session.add(super_admin)
    db.session.commit()
    approve(seed.student, seed.program)
    approve(seed.other_student, seed.program, campus_id=seed.other_campus.id)

    body = _export(sign_in(super_admin), 'applications')
    assert 'Test Student' in body
    assert 'Other Student' in body
