"""An approval that cannot be batched must warn the approver and stay visible.

Batch creation can fail or refuse a scholar; the approval must still land, the
approver must be told, and the office must find the scholar on the Batches page.
"""
import pytest

from app import db
from app.models import ScholarshipApplication
from app.models.scholarship import ApplicationStatus


@pytest.fixture()
def failing_batching(monkeypatch):
    """Make every auto-assignment attempt fail, as a broken batch would."""
    import app.services.batch_service as batch_service

    monkeypatch.setattr(batch_service, 'auto_assign_to_batch', lambda application: None)


def test_single_approval_warns_when_batching_fails(seed, approve, sign_in, unbatched_panel,
                                                   failing_batching):
    pending = approve(seed.student, seed.program, status=ApplicationStatus.PENDING)
    client = sign_in(seed.admin)

    response = client.post(f'/admin/applications/{pending.id}/review',
                           data={'action': 'approve', 'review_notes': 'probe'},
                           follow_redirects=True)

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'approved but not in a batch' in body

    db.session.expire_all()
    saved = db.session.get(ScholarshipApplication, pending.id)
    assert saved.status == ApplicationStatus.APPROVED
    assert saved.batch_id is None

    panel = unbatched_panel(client.get('/admin/batches').get_data(as_text=True))
    assert seed.student.get_full_name() in panel


def test_bulk_approval_warns_and_names_the_scholars(seed, approve, sign_in, failing_batching):
    pending = approve(seed.student, seed.program, status=ApplicationStatus.PENDING)
    client = sign_in(seed.admin)

    response = client.post('/admin/applications/batch',
                           data={'app_ids': [str(pending.id)], 'action': 'approve',
                                 'review_notes': 'bulk probe'},
                           follow_redirects=True)

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'are not in a batch' in body
    assert seed.student.get_full_name() in body

    db.session.expire_all()
    saved = db.session.get(ScholarshipApplication, pending.id)
    assert saved.status == ApplicationStatus.APPROVED
    assert saved.batch_id is None
