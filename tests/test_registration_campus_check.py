"""Registration must compare campuses even when the COR has no readable campus.

The campus check reads the COR's campus and falls back to the Report of Grades.
That fallback used `grades_data` before the function had assigned it, so a COR
whose campus OCR missed crashed the request with a 500 instead of using the
grades document. This pins the order down.
"""
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


@pytest.fixture()
def registrar(seed, monkeypatch):
    """The registration view with uploads, OCR and email stubbed out."""
    from app.services import ocr_service, storage_service
    from app.views import auth as auth_view

    monkeypatch.setattr(auth_view, '_save_registration_file',
                        lambda *a, **k: ('/tmp/fake-cor.pdf', None))
    monkeypatch.setattr(auth_view, '_send_otp_email', lambda *a, **k: None)
    monkeypatch.setattr(storage_service, 'get_file_bytes', lambda *a, **k: b'%PDF-1.4')

    def fake_verify(**kwargs):
        # COR with no campus at all: the grades document must be consulted.
        return {'passed': True, 'gwa': 1.5,
                'cor_data': {'year_level': '1st Year', 'units_enrolled': 18},
                'grades_data': {'campus': 'Test Campus', 'units_enrolled': 18},
                'errors': []}

    monkeypatch.setattr(ocr_service, 'verify_documents', fake_verify)
    return dict(FORM, campus_id=seed.campus.id)


def test_registration_uses_grades_campus_when_cor_has_none(app, registrar):
    import io

    client = app.test_client()
    payload = dict(registrar, cor_file=(io.BytesIO(b'%PDF-1.4'), 'cor.pdf'))

    response = client.post('/auth/register', data=payload,
                           content_type='multipart/form-data',
                           follow_redirects=False)

    assert response.status_code != 500
    # The grades document supplied the campus, so registration proceeds to OTP.
    assert response.status_code == 302
    with client.session_transaction() as sess:
        assert sess['pending_registration']['student_id'] == '0123-9999'
