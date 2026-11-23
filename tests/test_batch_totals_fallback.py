"""Batch totals when the batch has no fixed rate.

``recalculate_totals()`` pays out ``amount_per_scholar x approved`` when the batch
sets a rate, and otherwise sums what each approved application was actually
granted. The fallback also lives in the model's mapper events (which write the
columns with SQL during a flush), so it needs its own pin: a rate-less batch must
track status changes just as a rated one does.
"""
import pytest

from app import db
from app.models import ScholarshipApplication, ScholarshipBatch
from app.models.scholarship import ApplicationStatus
from app.services.batch_service import assign_applications_to_batch


def test_totals_fall_back_to_amount_received_without_a_rate(seed, approve):
    batch = ScholarshipBatch(scholarship_id=seed.program.id,
                             academic_period_id=seed.period.id,
                             batch_name='Batch 1', batch_number=1,
                             amount_per_scholar=None, status='open',
                             campus_id=seed.campus.id)
    db.session.add(batch)
    db.session.commit()

    first = approve(seed.student, seed.program)
    second = approve(seed.other_student, seed.program, campus_id=seed.campus.id)
    # assign_applications_to_batch() copies the batch rate onto each application,
    # which is None here; the granted amounts are what the batch actually paid.
    first.batch_id, first.amount_received = batch.id, 2500
    second.batch_id, second.amount_received = batch.id, 1500
    db.session.commit()

    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    assert (batch.total_scholars, float(batch.total_amount)) == (2, 4000.0)

    # The model's own recalculate_totals(), which the batch screens call, must
    # produce the same fallback number as the mapper event did above.
    batch.recalculate_totals()
    db.session.commit()
    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    assert (batch.total_scholars, float(batch.total_amount)) == (2, 4000.0)

    # A status change must renew the fallback sum, not leave the old amount.
    first.status = ApplicationStatus.REJECTED
    db.session.commit()

    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    assert (batch.total_scholars, float(batch.total_amount)) == (1, 1500.0)

    # Setting a rate later (the batch edit route does this) switches the batch to
    # the rate x count formula.
    batch.amount_per_scholar = 1000
    batch.recalculate_totals()
    db.session.commit()
    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    assert (batch.total_scholars, float(batch.total_amount)) == (1, 1000.0)

    # Dropping the rate again falls back to the granted amount...
    batch = db.session.get(ScholarshipBatch, batch.id)
    batch.amount_per_scholar = None
    db.session.commit()
    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    assert (batch.total_scholars, float(batch.total_amount)) == (1, 1500.0)

    # ...and editing that grant must refresh the total on its own, with no
    # status or batch change to notice it.
    second.amount_received = 900
    db.session.commit()
    db.session.expire_all()
    batch = db.session.get(ScholarshipBatch, batch.id)
    assert (batch.total_scholars, float(batch.total_amount)) == (1, 900.0)
