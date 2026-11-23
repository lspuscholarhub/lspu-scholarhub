"""Behaviour only the MySQL dialect can show; the CI pytest-mysql job runs these.

SQLite skips them, so the same file stays in the local suite.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app, db
from app.models import ScholarshipApplication
from app.models.scholarship import ApplicationStatus


def _mysql_only():
    if db.engine.dialect.name != 'mysql':
        pytest.skip('MySQL-only: the CI pytest-mysql job runs this')


def test_dangling_foreign_key_is_rejected_on_mysql(app, seed):
    """Outside the deliberate orphan helper, MySQL still enforces the FK."""
    _mysql_only()

    bad = ScholarshipApplication(scholarship_id=9999,
                                 applicant_id=seed.student.id,
                                 status=ApplicationStatus.PENDING,
                                 scholar_status='active',
                                 application_data={})
    db.session.add(bad)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert ScholarshipApplication.query.filter_by(scholarship_id=9999).count() == 0


def test_startup_migration_recreates_the_batch_index_on_mysql(app, seed):
    """The migration in create_app restores the unique index if a database lost it."""
    _mysql_only()
    from sqlalchemy import inspect, text

    index = 'uq_scholarship_batches_number'
    helper = 'ix_test_batch_scholarship'

    # InnoDB refuses to drop the unique index while it is the only index backing
    # the scholarship_id foreign key, so give that FK an index of its own first.
    db.session.execute(text(f'CREATE INDEX {helper} ON scholarship_batches (scholarship_id)'))
    db.session.execute(text(f'DROP INDEX {index} ON scholarship_batches'))
    db.session.commit()
    assert index not in {i['name'] for i in inspect(db.engine).get_indexes('scholarship_batches')}

    create_app('testing_copy')          # boots again against the same database

    names = {i['name'] for i in inspect(db.engine).get_indexes('scholarship_batches')}
    assert index in names

    db.session.execute(text(f'DROP INDEX {helper} ON scholarship_batches'))
    db.session.commit()
