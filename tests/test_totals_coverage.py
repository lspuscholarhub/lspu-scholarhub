"""Guard tests for the batch-total invariant.

The application model refreshes the affected batches itself (per-model mapper
events in app/models/scholarship.py), so an ordinary ORM status edit, re-batch or
delete cannot leave the dashboard totals stale. What can still go stale is a
mutation the model never sees - a bulk/raw-SQL update - or a call site that
forgets to hand the work to the model in the first place. These tests make both
kinds of regression visible instead of trusting the next author to remember.
"""
import ast
import re
from pathlib import Path

from sqlalchemy import event, update

from app import db
from app.models import ScholarshipApplication, ScholarshipBatch
from app.models import scholarship as scholarship_model
from app.models.scholarship import ApplicationStatus
from app.services.batch_service import (assign_applications_to_batch,
                                        recalculate_batch_totals)

APP_DIR = Path(__file__).resolve().parents[1] / 'app'

# A call to any of these means the site asked for a recount (the two services
# recalculate the batch they assign into and the batch a scholar left behind).
RECALCULATES = {
    'recalculate_batch_totals',
    'recalculate_totals',
    'assign_applications_to_batch',
    'auto_assign_to_batch',
}

# Raw SQL and bulk ORM updates never load the rows, so the mapper events cannot
# fire for them: those callers have to recount by hand.
EXPLICIT_RECOUNTS = {'recalculate_batch_totals', 'recalculate_totals'}

# Deleting a batch removes the row the totals live on, so there is nothing left
# to recalculate; the applications' links are cleared only as part of that delete.
EXEMPT = {
    ('views/admin.py', 'delete_batch'): 'the batch row is deleted, so it has no totals to keep',
    ('views/staff.py', 'delete_batch'): 'the batch row is deleted, so it has no totals to keep',
}

# A scholarship's own status is not an application mutation; only application
# variables (and names derived from them) count.
_APPLICATION_OBJECT = re.compile(r'^(app|application)(_\w+)?$')

_APPLICATION_NAMES = {'ScholarshipApplication', 'scholarship_applications'}


def _functions(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _app_functions():
    """Yield (module path relative to app/, function node) for every app module."""
    for path in sorted(APP_DIR.rglob('*.py')):
        relative = path.relative_to(APP_DIR).as_posix()
        if relative.startswith('models/'):          # the model owns the automatic refresh
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for function in _functions(tree):
            yield relative, function


def _mutates_application(node):
    """True for ``application.status = ...`` / ``app.batch_id = ...`` style writes."""
    targets = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, ast.AnnAssign) and node.value is not None:
        targets = [node.target]
    for target in targets:
        if not isinstance(target, ast.Attribute) or target.attr not in ('status', 'batch_id'):
            continue
        if isinstance(target.value, ast.Name) and _APPLICATION_OBJECT.match(target.value.id):
            return True
    return False


def _refers_to_applications(node):
    """Whether an expression names the application model or its table."""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and sub.id in _APPLICATION_NAMES:
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in _APPLICATION_NAMES:
            return True
    return False


def _raw_application_write(node):
    """True for bulk/raw SQL writes the mapper events and the ORM scan never see.

    Covers ``ScholarshipApplication.query.filter(...).update({...})``,
    ``session.execute(update(ScholarshipApplication)...)``,
    ``session.bulk_update_mappings(ScholarshipApplication, ...)`` and textual
    ``UPDATE scholarship_applications ...`` statements.
    """
    if not isinstance(node, ast.Call):
        return False
    name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
    if name in ('update', 'bulk_update_mappings') and _refers_to_applications(node):
        return True
    if name == 'text':
        return any(isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                   and 'scholarship_applications' in arg.value.lower()
                   for arg in node.args)
    return False


def _called_names(node, allowed):
    return {
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    } & allowed


def _recalculates(node, relative):
    """Calls that make this function responsible for the recount.

    In a view, auto-assigning only runs on the approve branch, so a reject that
    relies on it still leaves totals stale: views must ask for the recount
    themselves. Services may delegate to the assignment helpers, which recalculate
    the batch joined and the batch left.
    """
    allowed = RECALCULATES if relative.startswith('services/') else EXPLICIT_RECOUNTS
    return _called_names(node, allowed)


def _application_mutations():
    """Yield (file, function, line) for every application status/batch write in app/."""
    for relative, function in _app_functions():
        if _recalculates(function, relative):
            continue
        for node in ast.walk(function):
            if _mutates_application(node):
                yield relative, function.name, node.lineno


def test_every_application_status_or_batch_change_recalculates_totals():
    offenders = [
        f'{relative}:{line} in {name}() sets an application status/batch '
        f'without calling any of {sorted(RECALCULATES)}'
        for relative, name, line in _application_mutations()
        if (relative, name) not in EXEMPT
    ]
    assert not offenders, (
        'these writes would leave batch totals stale:\n  ' + '\n  '.join(offenders)
    )


def test_raw_or_bulk_application_writes_ask_for_a_recount():
    """Bulk SQL bypasses the mapper events, so it must recount explicitly."""
    offenders = []
    for relative, function in _app_functions():
        lines = [node.lineno for node in ast.walk(function)
                 if _raw_application_write(node)]
        if not lines:
            continue
        if _called_names(function, EXPLICIT_RECOUNTS):
            continue
        offenders.append(
            f'{relative}:{lines[0]} in {function.name}() writes applications with '
            f'bulk/raw SQL; the mapper events will not see it, so it must call '
            f'{sorted(EXPLICIT_RECOUNTS)}'
        )
    assert not offenders, (
        'these writes would leave batch totals stale:\n  ' + '\n  '.join(offenders)
    )


def test_the_model_refreshes_totals_without_anyone_remembering():
    """The automatic safety net itself must stay registered."""
    listeners = {
        'before_update': scholarship_model._remember_previous_batch,
        'before_delete': scholarship_model._remember_deleted_batch,
        'after_insert': scholarship_model._totals_after_insert,
        'after_update': scholarship_model._totals_after_update,
        'after_delete': scholarship_model._totals_after_delete,
    }
    for name, listener in listeners.items():
        assert event.contains(ScholarshipApplication, name, listener), \
            f'missing {name} listener: totals would drift again'


def test_bulk_updates_bypass_the_model_so_callers_must_recount(open_batch, seed, approve):
    """Pin the gap the static guard exists for: no ORM events on bulk SQL."""
    first = approve(seed.student, seed.program)
    second = approve(seed.other_student, seed.program, campus_id=seed.campus.id)
    assign_applications_to_batch(open_batch, [str(first.id), str(second.id)])
    db.session.commit()

    # No application object is loaded, so before/after_update never run.
    ScholarshipApplication.query.filter(
        ScholarshipApplication.id == first.id
    ).update({'status': ApplicationStatus.REJECTED}, synchronize_session=False)
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 2, \
        'the model was expected not to see a bulk status write'

    # The caller owns the recount for bulk writes.
    recalculate_batch_totals(open_batch.id)
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 1

    # Same for a bulk re-batch: batch_id changes without any ORM edit.
    db.session.execute(
        update(ScholarshipApplication)
        .where(ScholarshipApplication.id == second.id)
        .values(batch_id=None)
    )
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 1

    recalculate_batch_totals(open_batch.id)
    db.session.commit()
    db.session.expire_all()
    assert db.session.get(ScholarshipBatch, open_batch.id).total_scholars == 0
