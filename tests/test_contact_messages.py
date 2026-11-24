"""Contact form messages are stored, not just emailed.

The form used to rely on the mail provider alone, so a message was lost whenever
CONTACT_EMAIL was unset or the provider refused the send. These tests pin the
stored row, the honest flash, and the admin screen that reads it.
"""
import pytest

from app.models import ContactMessage
from app.services.notification_service import notification_service

SUBMISSION = {
    'name': 'Maria Santos',
    'email': 'maria@example.test',
    'student_id': '0123-9999',
    'subject': 'Scholarship deadline',
    'message': 'When is the deadline for the athletic grant?',
}


@pytest.fixture()
def mail(monkeypatch):
    """Replace the provider call; returns the call counter for assertions."""
    calls = {'sent': 0}

    def _patch(outcome):
        def send(to, subject, html):
            calls['sent'] += 1
            if outcome == 'raise':
                raise RuntimeError('provider unreachable')
            return {'success': outcome == 'ok'}
        monkeypatch.setattr(notification_service, 'send_email', send)
        return calls

    return _patch


def test_message_is_stored_when_the_provider_refuses(app, mail):
    calls = mail('refused')

    response = app.test_client().post('/contact', data=SUBMISSION,
                                      follow_redirects=True)

    assert response.status_code == 200
    row = ContactMessage.query.one()
    assert (row.name, row.email, row.subject) == ('Maria Santos',
                                                  'maria@example.test',
                                                  'Scholarship deadline')
    assert row.student_id == '0123-9999'
    assert row.emailed is False
    assert row.is_read is False
    assert calls['sent'] == 1
    assert 'saved for the scholarship office' in response.get_data(as_text=True)


def test_message_is_stored_when_the_provider_raises(app, mail):
    mail('raise')

    app.test_client().post('/contact', data=SUBMISSION, follow_redirects=True)

    row = ContactMessage.query.one()
    assert row.email == 'maria@example.test'
    assert row.emailed is False


def test_message_is_marked_emailed_only_when_the_provider_accepted_it(app, mail):
    mail('ok')

    response = app.test_client().post('/contact', data=SUBMISSION,
                                      follow_redirects=True)

    assert ContactMessage.query.one().emailed is True
    assert 'Your message has been sent' in response.get_data(as_text=True)


def test_blank_fields_are_rejected_without_storing(app, mail):
    mail('ok')
    data = dict(SUBMISSION, message='   ')

    response = app.test_client().post('/contact', data=data, follow_redirects=True)

    assert ContactMessage.query.count() == 0
    assert 'Please fill in all required fields' in response.get_data(as_text=True)


def test_admin_can_read_stored_messages(app, seed, sign_in):
    from app import db
    db.session.add(ContactMessage(name='Maria Santos', email='maria@example.test',
                                  subject='Scholarship deadline',
                                  message='When is the deadline?'))
    db.session.commit()

    response = sign_in(seed.admin).get('/admin/contact-messages')

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Scholarship deadline' in body
    assert 'maria@example.test' in body


def test_students_cannot_read_contact_messages(app, seed, sign_in):
    response = sign_in(seed.student).get('/admin/contact-messages',
                                         follow_redirects=False)

    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_mark_read_toggles_the_stored_flag(app, seed, sign_in):
    from app import db
    row = ContactMessage(name='Maria Santos', email='maria@example.test',
                         subject='Deadline', message='Question')
    db.session.add(row)
    db.session.commit()
    msg_id = row.id

    sign_in(seed.admin).post(f'/admin/contact-messages/{msg_id}/read')

    assert db.session.get(ContactMessage, msg_id).is_read is True
