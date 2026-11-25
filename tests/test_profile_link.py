"""The header's "My Profile" link points at /auth/profile for every role.

That route decides where to send the user from the session role. A super admin
used to fall through to the student branch, so their own profile answered
"Access denied. You do not have permission to view this page." and bounced them
to the login form while still signed in.
"""
import pytest

from app import db
from app.models import User


@pytest.fixture()
def super_admin(app, seed):
    user = User(username='t-super', email='super@example.test', password_hash='x',
                first_name='Super', last_name='Admin', user_type='super_admin',
                campus_id=seed.campus.id)
    db.session.add(user)
    db.session.commit()
    return user


def test_each_role_reaches_its_own_profile(seed, super_admin, sign_in):
    users = {'super_admin': (super_admin, '/admin/profile'),
             'admin': (seed.admin, '/admin/profile'),
             'staff': (seed.staff, '/staff/profile'),
             'student': (seed.student, '/student/profile')}

    for role, (user, expected) in users.items():
        client = sign_in(user)

        redirect = client.get('/auth/profile')
        assert redirect.status_code == 302, role
        assert redirect.headers['Location'].endswith(expected), role

        page = client.get(expected)
        assert page.status_code == 200, role
        assert 'Access denied' not in page.get_data(as_text=True), role
