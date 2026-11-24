"""The mail sender and the public contact address come from the environment.

Both were hardcoded to lspu.scholarhub@gmail.com in every send path and in the
UI. That inbox was disabled, so sends failed and the address shown to students
was dead; neither could be fixed without editing code.
"""
import json

from app.services import notification_service as ns
from app.utils import contact


def test_contact_email_defaults_and_can_be_overridden(monkeypatch):
    monkeypatch.delenv('CONTACT_EMAIL', raising=False)
    assert contact.contact_email() == 'lspu.scholarhub@gmail.com'

    monkeypatch.setenv('CONTACT_EMAIL', 'scholarships@lspu.test')
    assert contact.contact_email() == 'scholarships@lspu.test'


def test_sender_email_falls_back_to_the_smtp_user(monkeypatch):
    monkeypatch.delenv('MAIL_FROM_EMAIL', raising=False)
    monkeypatch.setenv('MAIL_USERNAME', 'smtp-user@lspu.test')
    assert contact.sender_email() == 'smtp-user@lspu.test'

    monkeypatch.setenv('MAIL_FROM_EMAIL', 'no-reply@lspu.test')
    assert contact.sender_email() == 'no-reply@lspu.test'


class _FakeSMTP:
    """Records the message instead of opening a connection."""

    sent = []

    def __init__(self, *args, **kwargs):
        pass

    def starttls(self):
        pass

    def login(self, username, password):
        pass

    def send_message(self, message):
        type(self).sent.append(message)

    def quit(self):
        pass


def _no_api_keys(monkeypatch):
    monkeypatch.delenv('RESEND_API_KEY', raising=False)
    monkeypatch.delenv('BREVO_API_KEY', raising=False)


def test_smtp_uses_the_configured_sender(monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr(ns.smtplib, 'SMTP', _FakeSMTP)
    _no_api_keys(monkeypatch)
    monkeypatch.setenv('MAIL_USERNAME', 'smtp-user@lspu.test')
    monkeypatch.setenv('MAIL_PASSWORD', 'app-password')
    monkeypatch.setenv('MAIL_FROM_EMAIL', 'no-reply@lspu.test')
    monkeypatch.setenv('MAIL_FROM_NAME', 'LSPU Scholarships')

    result = ns.NotificationService().send_email('student@lspu.test', 'Hi', '<p>hi</p>')

    assert result['success'] is True
    assert _FakeSMTP.sent[0]['From'] == 'LSPU Scholarships <no-reply@lspu.test>'


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture_http(monkeypatch, payload):
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured['url'] = request.full_url
        captured['body'] = json.loads(request.data.decode('utf-8'))
        return _FakeResponse(payload)

    monkeypatch.setattr('urllib.request.urlopen', fake_urlopen)
    return captured


def test_resend_sends_from_the_configured_address(monkeypatch):
    captured = _capture_http(monkeypatch, b'{"id": "abc"}')
    _no_api_keys(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY', 're_test_key')
    monkeypatch.setenv('MAIL_FROM_EMAIL', 'no-reply@lspu.test')

    result = ns.NotificationService().send_email('student@lspu.test', 'Hi', '<p>hi</p>')

    assert result['success'] is True
    assert captured['body']['from'] == 'LSPU ScholarHub <no-reply@lspu.test>'


def test_resend_without_a_sender_uses_its_sandbox_address(monkeypatch):
    captured = _capture_http(monkeypatch, b'{"id": "abc"}')
    _no_api_keys(monkeypatch)
    monkeypatch.setenv('RESEND_API_KEY', 're_test_key')
    monkeypatch.delenv('MAIL_FROM_EMAIL', raising=False)
    monkeypatch.delenv('MAIL_USERNAME', raising=False)

    ns.NotificationService().send_email('student@lspu.test', 'Hi', '<p>hi</p>')

    assert captured['body']['from'] == 'LSPU ScholarHub <onboarding@resend.dev>'


def test_brevo_requires_a_sender_then_uses_it(monkeypatch):
    captured = _capture_http(monkeypatch, b'{"messageId": "m1"}')
    _no_api_keys(monkeypatch)
    monkeypatch.setenv('BREVO_API_KEY', 'xkeysib-test')
    monkeypatch.delenv('MAIL_FROM_EMAIL', raising=False)
    monkeypatch.delenv('MAIL_USERNAME', raising=False)
    service = ns.NotificationService()

    refused = service.send_email('student@lspu.test', 'Hi', '<p>hi</p>')
    assert refused['success'] is False
    assert 'MAIL_FROM_EMAIL' in refused['message']

    monkeypatch.setenv('MAIL_FROM_EMAIL', 'no-reply@lspu.test')
    result = service.send_email('student@lspu.test', 'Hi', '<p>hi</p>')

    assert result['success'] is True
    assert captured['body']['sender']['email'] == 'no-reply@lspu.test'


def test_pages_show_the_configured_contact_address(app, monkeypatch):
    monkeypatch.setenv('CONTACT_EMAIL', 'scholarships@lspu.test')
    body = app.test_client().get('/contact').get_data(as_text=True)

    assert 'scholarships@lspu.test' in body
    assert 'lspu.scholarhub@gmail.com' not in body
