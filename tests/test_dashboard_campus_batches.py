"""The admin dashboard must count and total batches that carry no campus.

A batch for a program on the admin's campus may have campus_id NULL (legacy rows,
university-wide programs). The Batches page already resolved that through the
scholarship; the dashboard used to compare campus_id directly and drop the row.
"""
import pytest

from config.config import TestingConfig, config as config_map

from app import create_app, db
from app.models import AcademicPeriod, Campus, Scholarship, ScholarshipBatch, User
from app.models.scholarship import ScholarshipStatus


@pytest.fixture()
def app(tmp_path):
    """A throwaway SQLite copy, seeded with two campuses and three batches."""
    uri = f"sqlite:///{tmp_path / 'copy.sqlite'}"
    config_map['testing_copy'] = type('CopyConfig', (TestingConfig,),
                                      {'SQLALCHEMY_DATABASE_URI': uri})
    application = create_app('testing_copy')
    with application.app_context():
        db.create_all()

        period = AcademicPeriod(academic_year='2026-2027', semester='1st Semester')
        mine = Campus(name='Test Campus')
        elsewhere = Campus(name='Other Campus')
        db.session.add_all([period, mine, elsewhere])
        db.session.commit()

        admin = User(username='t-admin', email='admin@example.test', password_hash='x',
                     first_name='Test', last_name='Admin', user_type='admin',
                     campus_id=mine.id)
        db.session.add(admin)
        db.session.commit()

        program = Scholarship(title='Test Grant', description='d',
                              eligibility_criteria='e', benefits='b',
                              created_by=admin.id, campus_id=mine.id,
                              funding_type='private',
                              status=ScholarshipStatus.ACTIVE)
        db.session.add(program)
        db.session.commit()

        db.session.add_all([
            ScholarshipBatch(scholarship_id=program.id, academic_period_id=period.id,
                             batch_name='Batch 1', campus_id=mine.id,
                             status='open', total_amount=10000),
            # No campus of its own, but its program is on this campus.
            ScholarshipBatch(scholarship_id=program.id, academic_period_id=period.id,
                             batch_name='Batch 2', campus_id=None,
                             status='open', total_amount=2500),
            # Pinned elsewhere: must stay out of this campus's figures.
            ScholarshipBatch(scholarship_id=program.id, academic_period_id=period.id,
                             batch_name='Other campus batch', campus_id=elsewhere.id,
                             status='open', total_amount=9999),
        ])
        db.session.commit()
        try:
            yield application
        finally:
            db.session.remove()
            db.drop_all()


def test_dashboard_counts_and_totals_a_campus_less_batch(app, monkeypatch):
    from app.views import admin as admin_views

    captured = {}
    monkeypatch.setattr(admin_views, 'render_template',
                        lambda template, **context: captured.update(context) or 'rendered')

    admin = User.query.filter_by(username='t-admin').one()
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = admin.id
        sess['username'] = admin.username
        sess['user_type'] = 'admin'

    response = client.get('/admin/')

    assert response.status_code == 200
    assert captured['active_batches'] == 2
    assert float(captured['total_funds']) == 12500
