"""Registration must report a failed verification or credentials email.

Production ran without mail credentials, so `send_email` returned
`{'success': False, 'message': 'Email not configured'}` — but the views ignored
the result and flashed "code sent" / "credentials sent". The student was left
on the OTP screen with no code, or locked out with no temporary password.
"""
import io

import pytest

FORM = {
    'first_name': 'Test',
    'last_name': 'Registrant',
    'email': 'registrant@example.test',
    'student_id': '0123-9999',
    'phone_number': '09171234567',
    'course': 'Bachelor of Science in Information Technology',
    'year_level': '1st Year',
    'birthday': '2004-05-09',
}

EMAIL_NOT_CONFIGURED = {'success': False, 'message': 'Email not configured'}


@pytest.fixture()
def registrar(seed, monkeypatch):
    """The registration view with uploads/OCR stubbed; email set per test."""
    from app.services import ocr_service, storage_service
    from app.views import auth as auth_view

    monkeypatch.setattr(auth_view, '_save_registration_file',
                        lambda *a, **k: ('/tmp/fake-cor.pdf', None))
    monkeypatch.setattr(storage_service, 'get_file_bytes', lambda *a, **k: b'%PDF-1.4')

    def fake_verify(**kwargs):
        return {'passed': True, 'gwa': 1.5,
                'cor_data': {'year_level': '1st Year', 'units_enrolled': 18,
                             'campus': 'Test Campus'},
                'grades_data': {},
                'errors': []}

    monkeypatch.setattr(ocr_service, 'verify_documents', fake_verify)
    return dict(FORM, campus_id=seed.campus.id)


def _register(client, form):
    return client.post('/auth/register',
                       data=dict(form, cor_file=(io.BytesIO(b'%PDF-1.4'), 'cor.pdf')),
                       content_type='multipart/form-data',
                       follow_redirects=False)


def test_failed_otp_email_reports_error_instead_of_claiming_it_was_sent(
        app, registrar, monkeypatch):
    from app.views import auth as auth_view
    monkeypatch.setattr(auth_view, '_send_otp_email', lambda *a, **k: EMAIL_NOT_CONFIGURED)

    client = app.test_client()
    response = _register(client, registrar)

    assert response.status_code == 200          # back on the form, not on /verify-otp
    body = response.get_data(as_text=True)
    assert 'could not send the verification code' in body.lower()
    with client.session_transaction() as sess:
        assert 'pending_registration' not in sess


def test_failed_credentials_email_tells_student_to_contact_the_office(
        app, registrar, monkeypatch):
    from app.models import User
    from app.views import auth as auth_view

    monkeypatch.setattr(auth_view, '_send_otp_email',
                        lambda *a, **k: {'success': True, 'message': 'sent'})
    monkeypatch.setattr(auth_view, '_send_credentials_email',
                        lambda *a, **k: EMAIL_NOT_CONFIGURED)

    client = app.test_client()
    assert _register(client, registrar).status_code == 302

    with client.session_transaction() as sess:
        otp = sess['pending_registration']['otp']

    response = client.post('/auth/verify-otp', data={'otp': otp}, follow_redirects=True)

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'could not send your login credentials' in body.lower()
    # The account itself is still usable once the office hands over the password.
    assert User.query.filter_by(student_id='0123-9999').first() is not None
