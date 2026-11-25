"""Deleting a document must delete the file, not just the row.

Uploaded documents live on Cloudinary; both delete routes only dropped the
database row (and pointed the local-file removal at a URL), leaving the student's
file downloadable by its public address for good.
"""
import uuid

from app import db
from app.models import Document
from app.services import storage_service


def _cloudinary_document(owner):
    doc = Document(
        user_id=owner.id,
        original_filename='Essay.docx',
        stored_filename=f'essay-{uuid.uuid4().hex[:10]}.docx',
        file_path='https://res.cloudinary.com/demo/raw/upload/scholarhub/documents/essay.docx',
        file_size=10,
        category='general',
        file_type='docx',
        is_verified=True,
        cloudinary_url='https://res.cloudinary.com/demo/raw/upload/scholarhub/documents/essay.docx',
        cloudinary_public_id='scholarhub/documents/essay.docx',
    )
    db.session.add(doc)
    db.session.commit()
    return doc


def _record_deletions(monkeypatch):
    calls = []
    monkeypatch.setattr(storage_service, 'delete_file',
                        lambda **kwargs: calls.append(kwargs) or {'success': True})
    return calls


def test_student_delete_removes_the_cloudinary_object(app, seed, sign_in, monkeypatch):
    doc = _cloudinary_document(seed.student)
    doc_id = doc.id
    calls = _record_deletions(monkeypatch)

    response = sign_in(seed.student).post(f'/student/documents/{doc_id}/delete')
    assert response.status_code == 302

    assert calls and calls[0].get('public_id') == 'scholarhub/documents/essay.docx'
    assert calls[0].get('resource_type') == 'raw'
    assert db.session.get(Document, doc_id) is None


def test_admin_delete_removes_the_cloudinary_object(app, seed, sign_in, monkeypatch):
    doc = _cloudinary_document(seed.student)
    doc_id = doc.id
    calls = _record_deletions(monkeypatch)

    sign_in(seed.admin).post(f'/admin/documents/{doc_id}/delete')

    assert calls and calls[0].get('public_id') == 'scholarhub/documents/essay.docx'
    assert db.session.get(Document, doc_id) is None
