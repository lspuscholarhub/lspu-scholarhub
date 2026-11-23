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

from sqlalchemy import event

from app.models import ScholarshipApplication
from app.models import scholarship as scholarship_model

APP_DIR = Path(__file__).resolve().parents[1] / 'app'

# A call to any of these means the site asked for a recount (the two services
# recalculate the batch they assign into and the batch a scholar left behind).
RECALCULATES = {
    'recalculate_batch_totals',
    'recalculate_totals',
    'assign_applications_to_batch',
    'auto_assign_to_batch',
}

# Deleting a batch removes the row the totals live on, so there is nothing left
# to recalculate; the applications' links are cleared only as part of that delete.
EXEMPT = {
    ('views/admin.py', 'delete_batch'): 'the batch row is deleted, so it has no totals to keep',
    ('views/staff.py', 'delete_batch'): 'the batch row is deleted, so it has no totals to keep',
}

# A scholarship's own status is not an application mutation; only application
# variables (and names derived from them) count.
_APPLICATION_OBJECT = re.compile(r'^(app|application)(_\w+)?$')


def _functions(tree):
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


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


def _recalculates(node, relative):
    """Calls that make this function responsible for the recount.

    In a view, auto-assigning only runs on the approve branch, so a reject that
    relies on it still leaves totals stale: views must ask for the recount
    themselves. Services may delegate to the assignment helpers, which recalculate
    the batch joined and the batch left.
    """
    allowed = RECALCULATES if relative.startswith('services/') else {
        'recalculate_batch_totals', 'recalculate_totals'}
    return {
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    } & allowed


def _application_mutations():
    """Yield (file, function, line) for every application status/batch write in app/."""
    for path in sorted(APP_DIR.rglob('*.py')):
        relative = path.relative_to(APP_DIR).as_posix()
        if relative.startswith('models/'):          # the model owns the automatic refresh
            continue
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for function in _functions(tree):
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
