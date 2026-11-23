"""Shared fixtures: one throwaway app per test plus a baseline campus seed.

Every fixture builds its SQLite database under pytest's tmp_path, so the preview
database is never opened, copied or written to.
"""
import re
from datetime import datetime
from types import SimpleNamespace

import pytest

from config.config import TestingConfig, config as config_map

from app import create_app, db
from app.models import (AcademicPeriod, Campus, Scholarship, ScholarshipApplication,
                        ScholarshipBatch, User)
from app.models.scholarship import ApplicationStatus, ScholarshipStatus


@pytest.fixture()
def app(tmp_path):
    """A fresh app whose database is a private temp file, not the preview DB."""
    uri = f"sqlite:///{tmp_path / 'copy.sqlite'}"
    config_map['testing_copy'] = type('CopyConfig', (TestingConfig,),
                                      {'SQLALCHEMY_DATABASE_URI': uri})
    application = create_app('testing_copy')
    with application.app_context():
        db.create_all()
        try:
            yield application
        finally:
            db.session.remove()
            db.drop_all()


@pytest.fixture()
def seed(app):
    """Two campuses, the current period, an admin and staff on campus 1, a student
    on each campus, and one private program on campus 1."""
    campus = Campus(name='Test Campus')
    other = Campus(name='Other Campus')
    period = AcademicPeriod(academic_year='2026-2027', semester='1st Semester',
                            is_current=True)
    db.session.add_all([campus, other, period])
    db.session.commit()

    admin = User(username='t-admin', email='admin@example.test', password_hash='x',
                 first_name='Test', last_name='Admin', user_type='admin',
                 campus_id=campus.id)
    staff = User(username='t-staff', email='staff@example.test', password_hash='x',
                 first_name='Test', last_name='Staff', user_type='staff',
                 campus_id=campus.id)
    student = User(username='t-student', email='student@example.test', password_hash='x',
                   first_name='Test', last_name='Student', user_type='student',
                   student_id='TEST-0001', campus_id=campus.id)
    other_student = User(username='t-other', email='other@example.test', password_hash='x',
                         first_name='Other', last_name='Student', user_type='student',
                         student_id='TEST-0002', campus_id=other.id)
    db.session.add_all([admin, staff, student, other_student])
    db.session.commit()

    program = Scholarship(title='Test Grant', description='d',
                          eligibility_criteria='e', benefits='b',
                          created_by=admin.id, campus_id=campus.id,
                          funding_type='private', award_amount=5000,
                          status=ScholarshipStatus.ACTIVE)
    db.session.add(program)
    db.session.commit()

    return SimpleNamespace(campus=campus, other_campus=other, period=period,
                           admin=admin, staff=staff, student=student,
                           other_student=other_student, program=program)


@pytest.fixture()
def open_batch(seed):
    """An open batch for the campus-1 program, pinned to campus 1."""
    row = ScholarshipBatch(scholarship_id=seed.program.id,
                           academic_period_id=seed.period.id,
                           batch_name='Batch 1', batch_number=1,
                           amount_per_scholar=10000, status='open',
                           campus_id=seed.campus.id)
    db.session.add(row)
    db.session.commit()
    return row


@pytest.fixture()
def approve(app):
    """Create an application; campus_id defaults to the applicant's own campus."""
    def _approve(applicant, program=None, *, scholarship_id=None,
                 campus_id='applicant', status=ApplicationStatus.APPROVED):
        application = ScholarshipApplication(
            scholarship_id=scholarship_id if scholarship_id is not None else program.id,
            applicant_id=applicant.id,
            status=status,
            scholar_status='active',
            application_data={},
            submitted_at=datetime.utcnow(),
            campus_id=applicant.campus_id if campus_id == 'applicant' else campus_id,
        )
        db.session.add(application)
        db.session.commit()
        return application

    return _approve


@pytest.fixture()
def unbatched_panel():
    """Read the unbatched panel out of a Batches page; '' when none is rendered."""
    pattern = re.compile(r'aria-labelledby="unbatched-title".*?</section>', re.S)

    def _panel(body):
        match = pattern.search(body)
        return match.group(0) if match else ''

    return _panel


@pytest.fixture()
def sign_in(app):
    """A test client whose session is already that user."""
    def _sign_in(user):
        client = app.test_client()
        with client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['username'] = user.username
            sess['user_type'] = user.user_type
        return client

    return _sign_in
