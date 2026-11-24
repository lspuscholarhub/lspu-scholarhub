"""Staff/admin accounts are created from a name, an email and a role.

The username comes from the email, the campuses default to the creating
admin's own, and a temporary password is generated (and shown once) when the
password field is left blank.
"""
import re

from app.models import User


def _create(client, **overrides):
    data = {'first_name': 'rina', 'last_name': 'cruz',
            'email': 'rina.cruz@lspu.test', 'role': 'staff'}
    data.update(overrides)
    return client.post('/admin/users/create', data=data, follow_redirects=True)


def test_name_email_and_role_are_enough(seed, sign_in):
    client = sign_in(seed.admin)
    response = _create(client)

    created = User.query.filter_by(email='rina.cruz@lspu.test').one()
    assert created.user_type == 'staff'
    assert created.username == 'rina.cruz'
    assert created.get_full_name() == 'Rina Cruz'
    assert created.is_active and created.is_verified
    assert created.must_change_password is True
    # No campus was ticked, so the creating admin's campus was used.
    assert created.campus_id == seed.campus.id
    assert [c.id for c in created.assigned_campuses] == [seed.campus.id]

    # The generated password is handed over in the flash and actually works.
    match = re.search(rb'Temporary password: ([^ <]+)', response.data)
    assert match, 'the temporary password was not shown to the admin'
    assert created.check_password(match.group(1).decode())


def test_username_from_email_never_collides(seed, sign_in):
    client = sign_in(seed.admin)
    _create(client, email='juan@lspu.test')
    _create(client, email='juan@example.test')

    usernames = sorted(u.username for u in
                       User.query.filter(User.email.like('juan@%')).all())
    assert usernames == ['juan', 'juan2']


def test_duplicate_email_creates_nothing(seed, sign_in):
    client = sign_in(seed.admin)
    response = _create(client, email='staff@example.test')

    assert b'already registered' in response.data
    assert User.query.filter_by(email='staff@example.test').count() == 1


def test_typed_password_is_used_instead_of_a_generated_one(seed, sign_in):
    client = sign_in(seed.admin)
    response = _create(client, password='Chosen-pass-1')

    created = User.query.filter_by(email='rina.cruz@lspu.test').one()
    assert created.check_password('Chosen-pass-1')
    assert b'Temporary password:' not in response.data
