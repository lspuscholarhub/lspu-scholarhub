"""The admin and staff dashboards must count and total batches with no campus.

A batch for a program on the viewer's campus may have campus_id NULL (legacy
rows, university-wide programs). The Batches page already resolved that through
the scholarship; both dashboards used to compare campus_id directly and drop the
row, under-reporting the count and the fund total.
"""
import pytest

from app import db
from app.models import ScholarshipBatch


@pytest.fixture()
def batches(seed):
    """One batch on campus 1, one with no campus of its own, one on the other campus."""
    db.session.add_all([
        ScholarshipBatch(scholarship_id=seed.program.id,
                         academic_period_id=seed.period.id,
                         batch_name='Batch 1', campus_id=seed.campus.id,
                         status='open', total_amount=10000),
        # No campus of its own, but its program is on this campus.
        ScholarshipBatch(scholarship_id=seed.program.id,
                         academic_period_id=seed.period.id,
                         batch_name='Batch 2', campus_id=None,
                         status='open', total_amount=2500),
        # Pinned elsewhere: must stay out of this campus's figures.
        ScholarshipBatch(scholarship_id=seed.program.id,
                         academic_period_id=seed.period.id,
                         batch_name='Other campus batch', campus_id=seed.other_campus.id,
                         status='open', total_amount=9999),
    ])
    db.session.commit()


def test_admin_dashboard_counts_and_totals_a_campus_less_batch(batches, seed, sign_in,
                                                               monkeypatch):
    from app.views import admin as admin_views

    captured = {}
    monkeypatch.setattr(admin_views, 'render_template',
                        lambda template, **context: captured.update(context) or 'rendered')

    response = sign_in(seed.admin).get('/admin/')

    assert response.status_code == 200
    assert captured['active_batches'] == 2
    assert float(captured['total_funds']) == 12500


def test_staff_dashboard_counts_and_totals_a_campus_less_batch(batches, seed, sign_in,
                                                               monkeypatch):
    """The staff dashboard got the same campus fix and must agree with the admin one."""
    from app.views import staff as staff_views

    captured = {}
    monkeypatch.setattr(staff_views, 'render_template',
                        lambda template, **context: captured.update(context) or 'rendered')

    response = sign_in(seed.staff).get('/staff/')

    assert response.status_code == 200
    assert captured['active_batches'] == 2
    assert float(captured['total_funds']) == 12500
