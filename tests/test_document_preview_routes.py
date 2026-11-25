"""Word documents must reach the viewer, and the viewer must be able to fetch them.

Uploaded files live on Cloudinary, and the viewer routes used to redirect those
straight to the raw proxy — so a .docx never reached the page that previews it
(or explains why it cannot). Google's viewer also fetches the file from its own
servers, without our session, so the preview needs a signed, expiring link
instead of a login-protected one.
"""
import uuid

import pytest

from app import db
from app.models import Document
from app.services import document_service


def _document(owner, tmp_path, *, file_type='docx', cloudinary=True):
    source = tmp_path / f'sample.{file_type}'
    source.write_bytes(b'PK\x03\x04 fake word document bytes')
    doc = Document(
        user_id=owner.id,
        original_filename=f'Beloved Essay.{file_type}',
        stored_filename=f'sample-{uuid.uuid4().hex[:10]}.{file_type}',
        file_path=str(source),
        file_size=source.stat().st_size,
        category='general',
        file_type=file_type,
        is_verified=True,
        cloudinary_url='https://res.cloudinary.com/demo/raw/upload/sample.docx' if cloudinary else None,
        cloudinary_public_id='scholarhub/documents/sample.docx' if cloudinary else None,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


def test_student_viewer_renders_the_shared_page_for_a_word_document(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path)
    body = sign_in(seed.student).get(f'/student/documents/{doc.id}/view').get_data(as_text=True)

    assert 'id="gviewFallback"' in body, 'the student viewer must be the page with the fallback'
    assert 'docs.google.com/gview' in body
    assert f'/documents/{doc.id}/preview/' in body, 'the preview must use a session-free link'


def test_the_my_documents_page_opens_each_uploaded_file_in_the_viewer(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path, file_type='pdf')
    body = sign_in(seed.student).get('/student/upload-gwa').get_data(as_text=True)

    assert f'/student/documents/{doc.id}/view' in body, \
        'a file on the student record must have a View action that opens the viewer'


def test_admin_and_staff_see_the_viewer_page_instead_of_a_raw_redirect(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path)

    for user, url in ((seed.admin, f'/admin/documents/{doc.id}/view'),
                      (seed.staff, f'/staff/documents/{doc.id}/view')):
        response = sign_in(user).get(url)
        assert response.status_code == 200, f'{url} redirected to the raw file'
        body = response.get_data(as_text=True)
        assert 'id="gviewFallback"' in body and 'docs.google.com/gview' in body


def test_inline_view_links_hand_word_documents_to_the_viewer(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path)

    admin = sign_in(seed.admin).get(f'/admin/document/{doc.id}/view')
    assert admin.status_code == 302
    assert admin.headers['Location'].endswith(f'/admin/documents/{doc.id}/view')

    staff = sign_in(seed.staff).get(f'/staff/document/{doc.id}/view')
    assert staff.status_code == 302
    assert staff.headers['Location'].endswith(f'/staff/documents/{doc.id}/view')


def test_pdf_preview_is_untouched_by_the_word_route(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path, file_type='pdf')

    assert sign_in(seed.admin).get(f'/admin/documents/{doc.id}/view').status_code == 200
    # the pdf path of the inline route still serves the file itself
    assert sign_in(seed.admin).get(f'/admin/document/{doc.id}/view').status_code in (200, 302)


def test_the_preview_link_serves_one_file_without_a_session(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path)
    token = document_service.preview_token(doc.id)
    path = f'/documents/{doc.id}/preview/{token}'

    response = app.test_client().get(path)  # no session at all — what Google has
    assert response.status_code == 200
    assert response.data == b'PK\x03\x04 fake word document bytes'
    assert 'wordprocessingml' in response.headers['Content-Type']
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'


def test_the_preview_link_refuses_a_wrong_expired_or_foreign_token(app, seed, sign_in, tmp_path):
    doc = _document(seed.student, tmp_path)
    other = _document(seed.student, tmp_path)
    client = app.test_client()

    assert client.get(f'/documents/{doc.id}/preview/not-a-token').status_code == 403
    # a valid token for a different document opens nothing
    assert client.get(f'/documents/{doc.id}/preview/'
                      f'{document_service.preview_token(other.id)}').status_code == 403

    token = document_service.preview_token(doc.id)
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(document_service, 'PREVIEW_TOKEN_MAX_AGE', -1)
    try:
        assert client.get(f'/documents/{doc.id}/preview/{token}').status_code == 403
    finally:
        monkeypatch.undo()


def test_only_word_documents_get_a_preview_source(seed, tmp_path, app):
    word = _document(seed.student, tmp_path)
    pdf = _document(seed.student, tmp_path, file_type='pdf')

    with app.test_request_context('/'):
        assert document_service.preview_source_url(word).startswith('http')
        assert document_service.preview_source_url(pdf) is None
