"""Report exports follow the campus scoping of the reports pages they mirror.

The page a campus admin sees is filtered to their campus; the file they download
has to be the same data, or the export quietly becomes a way around the scoping.
"""
import pytest

from app import db
from app.models import AcademicPeriod, Scholarship, User
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
    approve(seed.student, seed.program, period=seed.period)
    approve(seed.other_student, seed.program, campus_id=seed.other_campus.id,
            period=seed.period)

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
    approve(seed.other_student, seed.program, campus_id=seed.other_campus.id,
            period=seed.period)

    body = _export(sign_in(seed.admin), 'applications',
                   extra=f'&campus_id={seed.other_campus.id}')
    assert 'Other Student' not in body


def test_super_admin_export_still_spans_every_campus(seed, approve, sign_in):
    super_admin = User(username='t-super', email='super@example.test', password_hash='x',
                       first_name='Super', last_name='Admin', user_type='super_admin')
    db.session.add(super_admin)
    db.session.commit()
    approve(seed.student, seed.program, period=seed.period)
    approve(seed.other_student, seed.program, campus_id=seed.other_campus.id,
            period=seed.period)

    body = _export(sign_in(super_admin), 'applications')
    assert 'Test Student' in body
    assert 'Other Student' in body


def test_roster_export_follows_a_selected_past_period(seed, approve, sign_in):
    """The student roster is period-filtered only once a past period is picked."""
    past = AcademicPeriod(academic_year='2024-2025', semester='1st Semester',
                          is_current=False)
    older = User(username='t-older', email='older@example.test', password_hash='x',
                 first_name='Past', last_name='Student', user_type='student',
                 student_id='TEST-0004', campus_id=seed.campus.id)
    idle = User(username='t-idle', email='idle@example.test', password_hash='x',
                first_name='Idle', last_name='Student', user_type='student',
                student_id='TEST-0005', campus_id=seed.campus.id)
    db.session.add_all([past, older, idle])
    db.session.commit()
    approve(older, seed.program, period=past)
    approve(seed.student, seed.program, period=seed.period)

    client = sign_in(seed.admin)
    everyone = _export(client, 'students')            # no past period picked
    assert 'Past Student' in everyone
    assert 'Test Student' in everyone
    assert 'Idle Student' in everyone

    with client.session_transaction() as sess:
        sess['viewing_period_id'] = past.id
    scoped = _export(client, 'students')
    assert 'Past Student' in scoped
    assert 'Test Student' not in scoped
    assert 'Idle Student' not in scoped


def test_exports_keep_applications_without_a_period(seed, approve, sign_in):
    """An unrecorded period is unknown, not elsewhere: the row stays in the file."""
    past = AcademicPeriod(academic_year='2024-2025', semester='1st Semester',
                          is_current=False)
    unset = User(username='t-unset', email='unset@example.test', password_hash='x',
                 first_name='No', last_name='Period', user_type='student',
                 student_id='TEST-0006', campus_id=seed.campus.id)
    db.session.add_all([past, unset])
    db.session.commit()
    approve(seed.student, seed.program, period=seed.period)
    approve(unset, seed.program)                      # academic_period_id stays NULL

    client = sign_in(seed.admin)
    current = _export(client, 'applications')
    assert 'Test Student' in current
    assert 'No Period' in current

    with client.session_transaction() as sess:
        sess['viewing_period_id'] = past.id
    earlier = _export(client, 'applications')
    assert 'Test Student' not in earlier
    assert 'No Period' in earlier


def test_export_follows_the_viewing_period(seed, approve, sign_in):
    """A past period picked on the reports page limits the export the same way."""
    past = AcademicPeriod(academic_year='2025-2026', semester='2nd Semester',
                          is_current=False)
    peer = User(username='t-peer', email='peer@example.test', password_hash='x',
                first_name='Peer', last_name='Student', user_type='student',
                student_id='TEST-0003', campus_id=seed.campus.id)
    db.session.add_all([past, peer])
    db.session.commit()
    approve(seed.student, seed.program, period=past)
    approve(peer, seed.program, period=seed.period)

    client = sign_in(seed.admin)
    current = _export(client, 'applications')       # nothing selected: current period
    assert 'Peer Student' in current
    assert 'Test Student' not in current

    with client.session_transaction() as sess:
        sess['viewing_period_id'] = past.id
    earlier = _export(client, 'applications')
    assert 'Test Student' in earlier
    assert 'Peer Student' not in earlier
