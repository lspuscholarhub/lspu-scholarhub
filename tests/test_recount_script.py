"""The one-off recount script repairs totals written before the model kept them."""
import importlib.util
from pathlib import Path

from sqlalchemy import update

from app import db
from app.models import ScholarshipBatch
from app.services.batch_service import assign_applications_to_batch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'recalculate_batch_totals.py'


def _script():
    spec = importlib.util.spec_from_file_location('recalculate_batch_totals', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stale_totals(batch_id):
    """Write zeros the way a pre-maintenance database would look: raw bulk SQL."""
    db.session.execute(
        update(ScholarshipBatch).where(ScholarshipBatch.id == batch_id)
        .values(total_scholars=0, total_male=0, total_female=0, total_amount=0)
    )
    db.session.commit()
    db.session.expire_all()
    return db.session.get(ScholarshipBatch, batch_id)


def test_recount_repairs_stale_totals_and_reports_the_rows(open_batch, seed, approve):
    first = approve(seed.student, seed.program)
    second = approve(seed.other_student, seed.program, campus_id=seed.campus.id)
    assign_applications_to_batch(open_batch, [str(first.id), str(second.id)])
    db.session.commit()
    assert _stale_totals(open_batch.id).total_scholars == 0

    changed = _script().recalculate_all_batches()

    assert [row[0] for row in changed] == [open_batch.id]
    batch_id, name, before, after = changed[0]
    assert (batch_id, name) == (open_batch.id, 'Batch 1')
    assert before == (0, 0, 0, 0.0)
    assert after[0] == 2 and after[3] == 20000.0

    db.session.expire_all()
    repaired = db.session.get(ScholarshipBatch, open_batch.id)
    assert (repaired.total_scholars, float(repaired.total_amount)) == (2, 20000.0)


def test_recount_is_quiet_on_a_consistent_database(open_batch, seed, approve):
    scholar = approve(seed.student, seed.program)
    assign_applications_to_batch(open_batch, [str(scholar.id)])
    db.session.commit()

    assert _script().recalculate_all_batches() == []


def test_dry_run_reports_without_repairing(open_batch, seed, approve):
    first = approve(seed.student, seed.program)
    assign_applications_to_batch(open_batch, [str(first.id)])
    db.session.commit()
    _stale_totals(open_batch.id)

    changed = _script().recalculate_all_batches(dry_run=True)

    assert [row[0] for row in changed] == [open_batch.id]
    db.session.expire_all()
    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 0
