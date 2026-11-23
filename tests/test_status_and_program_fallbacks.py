"""Regression tests for the status enum query and the removed-program fallbacks."""
import pytest

from app import db
from app.models import ScholarshipApplication, User
from app.models.scholarship import ApplicationStatus
from app.services import chatbot_service, export_service
from app.services.performance_service import performance_service


@pytest.fixture()
def applications(seed, approve):
    """One real award plus an application whose program row does not exist."""
    award = approve(seed.student, seed.program)
    orphan = approve(seed.student, scholarship_id=9999, campus_id=None)
    orphan.is_active = False        # keep the report's first() on the real award
    db.session.commit()
    return award, orphan


def _student():
    return User.query.filter_by(student_id='TEST-0001').one()


def test_approved_applications_match_the_status_enum(applications):
    """The column stores enum names, so this query must compare enum to enum."""
    approved = ScholarshipApplication.query.filter(
        ScholarshipApplication.status == ApplicationStatus.APPROVED).count()
    assert approved == 2


def test_performance_report_finds_the_award(applications):
    """It used to return 'No active scholarship found' for every scholar."""
    report = performance_service.generate_performance_report(scholar_id=_student().id)

    assert report['success'] is True, report.get('message')
    assert report['report']['scholarship_info']['title'] == 'Test Grant'


def test_deleted_program_falls_back_to_a_label(applications):
    rows = export_service._build_applications_data()
    assert 'Program removed' in {row['Scholarship'] for row in rows}

    context = chatbot_service._user_context(_student().id)
    assert 'Application Summary' in context
    assert 'removed program' in context


def test_alert_email_names_a_removed_program(monkeypatch):
    """The performance alert must not dereference a scholarship row that is gone."""
    from types import SimpleNamespace

    import app.services.performance_service as perf_module

    mail = {}

    class _StubNotifier:
        def send_email(self, to, subject, message):
            mail['body'] = message

        def create_in_app_notification(self, *args, **kwargs):
            pass

    monkeypatch.setattr(perf_module, 'notification_service', _StubNotifier())

    performance_service._send_performance_notifications(
        SimpleNamespace(first_name='Ana', last_name='Cruz', email='ana@example.test'),
        SimpleNamespace(scholarship=None),
        [{'message': 'GWA dropped below the retention mark'}], 2.10)

    assert mail.get('body'), 'the alert email was not sent'
    assert 'Program removed' in mail['body']
