"""Crawl every GET route as every role and report any 5xx errors.

Runs against the LIVE Railway database (read-only GET requests only).
Run:  DATABASE_URL='mysql://...' python docs/error_sweep.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False

SCHOLARSHIP_IDS = [29, 30, 31]   # private, public, public
STUDENT_ID = 165  # an existing active student in the live DB
STAFF_ID = 52
ADMIN_ID = 1

# (url, roles_allowed) — role None means public/guest
ROUTES = [
    ('/', None),
    ('/scholarship/', None),
    ('/contact', None),
    ('/auth/login', None),
    ('/auth/register', None),
    ('/scholarship/<S1>', None),
    ('/scholarship/<S1>/apply', 'student'),
    ('/student/dashboard', 'student'),
    ('/student/applications', 'student'),
    ('/student/my-scholarship', 'student'),
    ('/student/profile', 'student'),
    ('/student/upload-gwa', 'student'),
    ('/student/notifications', 'student'),
    ('/staff/dashboard', 'staff'),
    ('/staff/scholarships', 'staff'),
    ('/staff/review', 'staff'),
    ('/staff/batches', 'staff'),
    ('/staff/monitoring', 'staff'),
    ('/staff/students', 'staff'),
    ('/staff/reports', 'staff'),
    ('/staff/notifications', 'staff'),
    ('/staff/profile', 'staff'),
    ('/staff/import', 'staff'),
    ('/admin/dashboard', 'admin'),
    ('/admin/scholarships', 'admin'),
    ('/admin/applications', 'admin'),
    ('/admin/batches', 'admin'),
    ('/admin/monitoring', 'admin'),
    ('/admin/students', 'admin'),
    ('/admin/reports', 'admin'),
    ('/admin/notifications', 'admin'),
    ('/admin/audit-log', 'admin'),
    ('/admin/settings', 'admin'),
    ('/admin/profile', 'admin'),
    ('/admin/import', 'admin'),
    ('/admin/staff', 'admin'),
    ('/admin/users', 'admin'),
]

USER_IDS = {'student': STUDENT_ID, 'staff': STAFF_ID, 'admin': ADMIN_ID}

errors = []
count = [0]

with app.app_context():
    from app.models import Scholarship, ScholarshipApplication, User
    from app.models.scholarship_batch import ScholarshipBatch

    extra = []
    for sid in SCHOLARSHIP_IDS:
        if Scholarship.query.get(sid):
            extra.append((f'/scholarship/{sid}', None))
            extra.append((f'/scholarship/{sid}/apply', 'student'))
    # any application detail pages for the student
    for a in ScholarshipApplication.query.filter_by(applicant_id=STUDENT_ID).all():
        extra.append((f'/scholarship/application/{a.id}/edit', 'student'))
    for b in ScholarshipBatch.query.all():
        extra.append((f'/staff/batches/{b.id}', 'staff'))
        extra.append((f'/admin/batches/{b.id}', 'admin'))
    for u in User.query.filter_by(user_type='student').limit(3).all():
        extra.append((f'/staff/students/{u.id}', 'staff'))
        extra.append((f'/admin/students/{u.id}', 'admin'))

with app.test_client() as c:
    def crawl(role):
        with c.session_transaction() as s:
            s.clear()
            if role:
                s['user_id'] = USER_IDS[role]
                s['user_type'] = role
                s['username'] = f'test-{role}'
                s['is_verified'] = True
        for raw in ROUTES + extra:
            allowed = raw[1]
            if allowed and allowed != role:
                continue
            url = raw[0]
            for k, v in [('S1', SCHOLARSHIP_IDS[0])]:
                url = url.replace(f'<{k}>', str(v))
            try:
                r = c.get(url, follow_redirects=False)
                count[0] += 1
                if r.status_code >= 500:
                    errors.append((role or 'guest', url, r.status_code))
            except Exception as e:
                errors.append((role or 'guest', url, f'EXC: {type(e).__name__}: {e}'))

    for role in (None, 'student', 'staff', 'admin'):
        crawl(role)

print(f'\nChecked {count[0]} requests across guest/student/staff/admin')
if errors:
    print(f'\n{len(errors)} ERRORS FOUND:')
    for role, url, code in errors:
        print(f'  [{role}] {url} -> {code}')
    sys.exit(1)
else:
    print('ALL CLEAN - no 5xx errors')
