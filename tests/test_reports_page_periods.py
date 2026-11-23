"""The reports pages count applications whose academic period was never recorded.

The page and the CSV it offers must agree, so both apply the same rule: an
application with no period is unknown, not another period, and stays in view.
"""
import importlib

import pytest

from app import db
from app.models import User


def _capture(monkeypatch, module_name):
    """Replace render_template so the view's context can be inspected."""
    module = importlib.import_module(f'app.views.{module_name}')
    captured = {}
    monkeypatch.setattr(module, 'render_template',
                        lambda template, **context: captured.update(context) or 'rendered')
    return captured


@pytest.mark.parametrize('role', ['admin', 'staff'])
def test_reports_page_counts_applications_without_a_period(role, seed, approve, sign_in,
                                                           monkeypatch):
    unset = User(username=f't-np-{role}', email=f'np-{role}@example.test',
                 password_hash='x', first_name='No', last_name='Period',
                 user_type='student', student_id=f'NP-{role}', campus_id=seed.campus.id)
    db.session.add(unset)
    db.session.commit()
    approve(seed.student, seed.program, period=seed.period)
    approve(unset, seed.program)                      # academic_period_id stays NULL

    captured = _capture(monkeypatch, role)
    user = seed.admin if role == 'admin' else seed.staff
    response = sign_in(user).get(f'/{role}/reports')

    assert response.status_code == 200
    assert captured['total_apps'] == 2
    assert captured['approved'] == 2
