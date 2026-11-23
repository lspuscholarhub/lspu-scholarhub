"""Section 14: pages that print a program still render when that row is gone.

Every page below lists applications. One seeded application points at a missing
scholarship, so a template (or view) that dereferences it without a fallback
fails here instead of in front of a user.
"""
import pytest

from app import db

ADMIN_PAGES = ['/admin/', '/admin/applications', '/admin/monitoring',
               '/admin/batches', '/admin/students/{student}']
STAFF_PAGES = ['/staff/', '/staff/review-applications', '/staff/monitoring',
               '/staff/batches', '/staff/students/{student}']


@pytest.fixture()
def applications(seed, approve):
    """A real award plus an approved application whose program row does not exist."""
    approve(seed.student, seed.program)
    approve(seed.student, scholarship_id=9999, campus_id=None)


@pytest.mark.parametrize('path', ADMIN_PAGES)
def test_admin_pages_render_with_a_missing_program(path, seed, applications, sign_in):
    response = sign_in(seed.admin).get(path.replace('{student}', str(seed.student.id)))
    assert response.status_code == 200, path


@pytest.mark.parametrize('path', STAFF_PAGES)
def test_staff_pages_render_with_a_missing_program(path, seed, applications, sign_in):
    response = sign_in(seed.staff).get(path.replace('{student}', str(seed.student.id)))
    assert response.status_code == 200, path


def test_student_dashboard_renders_with_a_missing_program(seed, applications, sign_in):
    response = sign_in(seed.student).get('/student/dashboard')
    assert response.status_code == 200
