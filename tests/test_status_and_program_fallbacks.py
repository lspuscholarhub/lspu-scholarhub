"""Regression tests for the status enum query and the removed-program fallbacks.

Everything here runs on a throwaway SQLite database created in pytest's temp
directory, so the preview database is never opened, copied or written to.
"""
import pytest

from config.config import TestingConfig, config as config_map

from app import create_app, db
from app.models import Scholarship, ScholarshipApplication, User
from app.models.scholarship import ApplicationStatus
from app.services import chatbot_service, export_service
from app.services.performance_service import performance_service


@pytest.fixture()
def app(tmp_path):
    """A fresh app whose database is a private temp-file copy, not the preview DB."""
    uri = f"sqlite:///{tmp_path / 'copy.sqlite'}"
    copy_config = type('CopyConfig', (TestingConfig,), {'SQLALCHEMY_DATABASE_URI': uri})
    config_map['testing_copy'] = copy_config

    application = create_app('testing_copy')
    with application.app_context():
        db.create_all()

        admin = User(username='t-admin', email='admin@example.test', password_hash='x',
                     first_name='Test', last_name='Admin', user_type='admin')
        student = User(username='t-student', email='student@example.test', password_hash='x',
                       first_name='Test', last_name='Student', user_type='student',
                       student_id='TEST-0001')
        db.session.add_all([admin, student])
        db.session.commit()

        grant = Scholarship(title='Test Grant', description='d',
                            eligibility_criteria='e', benefits='b',
                            created_by=admin.id, award_amount=5000,
                            funding_type='private')
        db.session.add(grant)
        db.session.commit()

        db.session.add_all([
            ScholarshipApplication(scholarship_id=grant.id, applicant_id=student.id,
                                  status=ApplicationStatus.APPROVED,
                                  scholar_status='active'),
            # Its scholarship row does not exist: the deleted-program cases.
            ScholarshipApplication(scholarship_id=9999, applicant_id=student.id,
                                  status=ApplicationStatus.APPROVED,
                                  scholar_status='active', is_active=False),
        ])
        db.session.commit()
        try:
            yield application
        finally:
            db.session.remove()
            db.drop_all()


def _student():
    return User.query.filter_by(student_id='TEST-0001').one()


def test_approved_applications_match_the_status_enum(app):
    """The column stores enum names, so this query must compare enum to enum."""
    approved = ScholarshipApplication.query.filter(
        ScholarshipApplication.status == ApplicationStatus.APPROVED).count()
    assert approved == 2


def test_performance_report_finds_the_award(app):
    """It used to return 'No active scholarship found' for every scholar."""
    report = performance_service.generate_performance_report(scholar_id=_student().id)

    assert report['success'] is True, report.get('message')
    assert report['report']['scholarship_info']['title'] == 'Test Grant'


def test_deleted_program_falls_back_to_a_label(app):
    rows = export_service._build_applications_data()
    assert 'Program removed' in {row['Scholarship'] for row in rows}

    context = chatbot_service._user_context(_student().id)
    assert 'Application Summary' in context
    assert 'removed program' in context
