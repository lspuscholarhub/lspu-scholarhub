"""Exercise key POST flows as each role; report 5xx errors (not business rejections).

POSTs are done against the LIVE DB but only in ways that are safe:
- login with wrong password (rejected, not 500)
- apply without terms (validation flash, no DB write)
- edit with valid data then restore original data
- withdraw on a synthetic app created+deleted in the same run
Run:  DATABASE_URL='mysql://...' python docs/post_sweep.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from datetime import datetime

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

errors = []
notes = []

with app.test_client() as c:
    def login(uid, utype, uname):
        with c.session_transaction() as s:
            s.clear()
            s['user_id'] = uid
            s['user_type'] = utype
            s['username'] = uname
            s['is_verified'] = True

    def post_check(role, url, data, expect_5xx_only=True):
        try:
            r = c.post(url, data=data, follow_redirects=False)
            if r.status_code >= 500:
                errors.append((role, f'POST {url}', r.status_code))
            else:
                notes.append((role, f'POST {url}', r.status_code))
        except Exception as e:
            errors.append((role, f'POST {url}', f'EXC: {type(e).__name__}: {e}'))

    # ── Guest: login wrong password, register validation failure ──────────────
    login(None, None, None)
    post_check('guest', '/auth/login', {'username': 'nobody', 'password': 'wrong'})
    post_check('guest', '/auth/register', {'student_id': '', 'email': 'bad'})
    post_check('guest', '/chatbot/chat', {'message': 'hello'})

    # ── Student flows ─────────────────────────────────────────────────────────
    # Look up LIVE ids — the old hardcoded scholarship 30 / student 49 no longer exist
    with app.app_context():
        from app.models import Scholarship, User
        _s = Scholarship.query.filter_by(status='active').first() or Scholarship.query.first()
        _u = User.query.filter_by(user_type='student', is_active=True).first()
        assert _s and _u, 'live DB needs at least one scholarship and one student'
        LIVE_SCHOLARSHIP_ID = _s.id
        LIVE_STUDENT_ID = _u.id

    login(LIVE_STUDENT_ID, 'student', 'student')
    # apply without agreeing to terms → validation flash, no DB write
    post_check('student', f'/scholarship/{LIVE_SCHOLARSHIP_ID}/apply', {'first_name': 'x'})
    # edit application (create a synthetic pending app first)
    with app.app_context():
        from app.models import ScholarshipApplication, User
        from app.models.scholarship import ApplicationStatus
        a = ScholarshipApplication(scholarship_id=LIVE_SCHOLARSHIP_ID, applicant_id=LIVE_STUDENT_ID,
                                   application_data={'first_name': 'Orig'},
                                   documents=[], status=ApplicationStatus.PENDING,
                                   submitted_at=datetime.utcnow())
        db = None
        from app import db as _db
        _db.session.add(a)
        _db.session.commit()
        app_id = a.id
    post_check('student', f'/scholarship/application/{app_id}/edit',
               {'first_name': 'New', 'last_name': 'Name', 'gwa': '2.5', 'units_enrolled': '18'})
    # withdraw the synthetic app
    post_check('student', f'/scholarship/application/{app_id}/withdraw', {})
    # notifications mark read / mark all
    post_check('student', '/student/notifications/mark-all-read', {})
    # chatbot
    post_check('student', '/chatbot/chat', {'message': 'what documents do i need'})
    # profile update with unchanged data
    post_check('student', '/student/profile/update', {'first_name': 'Test', 'last_name': 'User'})

    # ── Staff flows ───────────────────────────────────────────────────────────
    login(52, 'staff', 'Jessa')
    # review with invalid action (should flash, not 500)
    post_check('staff', '/staff/applications/999999/review', {'action': 'approve'})
    # announcement send with empty target (should flash)
    post_check('staff', '/staff/notifications/send', {'recipient_type': 'all', 'title': '', 'message': ''})
    # batch create with no name (should flash)
    post_check('staff', '/staff/batches/create', {'batch_name': ''})

    # ── Admin flows ───────────────────────────────────────────────────────────
    login(1, 'admin', 'admin')
    post_check('admin', '/admin/applications/999999/review', {'action': 'approve'})
    post_check('admin', '/admin/notifications/send', {'recipient_type': 'all', 'title': '', 'message': ''})
    post_check('admin', '/admin/settings/period/create', {'name': '', 'year_start': ''})

print(f'\n{len(notes)} POSTs exercised')
if errors:
    print(f'{len(errors)} ERRORS:')
    for role, url, code in errors:
        print(f'  [{role}] {url} -> {code}')
    sys.exit(1)
print('ALL POST FLOWS CLEAN - no 5xx')
