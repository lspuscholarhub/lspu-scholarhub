"""Editing a batch's rate changes what every approved scholar in it is owed.

The batch model's before/after_update listeners must rewrite total_scholars and
total_amount in the same flush - no explicit recalculate_totals() from the caller,
which is exactly how the batch edit screens looked before this was automatic.
"""
import pytest

from app import db
from app.models import ScholarshipBatch
from app.services.batch_service import assign_applications_to_batch


def _totals(batch_id):
    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch_id)
    return batch.total_scholars, float(batch.total_amount)


def test_changing_the_rate_refreshes_stored_totals(open_batch, seed, approve):
    first = approve(seed.student, seed.program)
    second = approve(seed.other_student, seed.program, campus_id=seed.campus.id)
    assign_applications_to_batch(open_batch, [str(first.id), str(second.id)])
    db.session.commit()
    assert _totals(open_batch.id) == (2, 20000.0)

    # A plain ORM edit, with no recalculate_totals() call: 2 x 5,000.
    batch = db.session.get(ScholarshipBatch, open_batch.id)
    batch.amount_per_scholar = 5000
    db.session.commit()
    assert _totals(open_batch.id) == (2, 10000.0)

    # Dropping the rate falls back to what each application was granted, which
    # is still the rate copied at assignment time (10,000 each).
    batch = db.session.get(ScholarshipBatch, open_batch.id)
    batch.amount_per_scholar = None
    db.session.commit()
    assert _totals(open_batch.id) == (2, 20000.0)

    batch = db.session.get(ScholarshipBatch, open_batch.id)
    batch.amount_per_scholar = 7500
    db.session.commit()
    assert _totals(open_batch.id) == (2, 15000.0)
