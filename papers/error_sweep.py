#!/usr/bin/env python3
"""
LSPU ScholarHub — Error Sweep
==============================
Tests every route for every user role and reports any 500 errors.
Uses session injection (no password needed) for authenticated routes.
Run: python papers/error_sweep.py
"""

import os, sys, io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class C:
    R = '\033[91m'; Y = '\033[93m'; G = '\033[92m'; B = '\033[94m'
    W = '\033[97m'; D = '\033[0m'; BOLD = '\033[1m'

def ok(msg):    print(f"  {C.G}PASS{C.D}  {msg}")
def fail(msg):  print(f"  {C.R}FAIL{C.D}  {msg}")
def skip(msg):  print(f"  {C.Y}SKIP{C.D}  {msg}")
def section(t): print(f"\n{C.BOLD}{C.W}-- {t} --{C.D}\n")

# ── Routes by role ───────────────────────────────────────────────────────────

GUEST_ROUTES = [
    '/',
    '/scholarships',
    '/auth/login',
    '/auth/register',
    '/auth/forgot-password',
    '/chatbot/',
]

STUDENT_ROUTES = [
    '/student/dashboard',
    '/student/applications',
    '/student/profile',
    '/student/notifications',
    '/student/documents',
    '/student/my-scholarship',
]

STAFF_ROUTES = [
    '/staff/',
    '/staff/scholarships',
    '/staff/students',
    '/staff/batches',
    '/staff/monitoring',
    '/staff/notifications',
    '/staff/reports',
    '/staff/profile',
]

ADMIN_ROUTES = [
    '/admin/',
    '/admin/scholarships',
    '/admin/applications',
    '/admin/students',
    '/admin/batches',
    '/admin/monitoring',
    '/admin/notifications',
    '/admin/reports',
    '/admin/settings',
    '/admin/profile',
    '/admin/users',
]

SUPER_ADMIN_ROUTES = [
    '/admin/',
    '/admin/scholarships',
    '/admin/users',
    '/admin/campus-context/1',
    '/admin/campus-context/2',
    '/admin/campus-context/3',
    '/admin/campus-context/4',
]

CHATBOT_ROUTES = [
    '/chatbot/',
]


def get_app():
    db_url = 'mysql+pymysql://root:REDACTED_DB_PASSWORD@altaria.proxy.rlwy.net:56613/railway'
    os.environ['DATABASE_URL'] = db_url
    from app import create_app
    return create_app()


def inject_session(client, app, user_type):
    """Inject session to simulate a logged-in user (no password needed)."""
    from app.models import User
    with app.app_context():
        user = User.query.filter_by(user_type=user_type, is_active=True).first()
        if not user:
            return False, f'No active {user_type}'
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['user_type'] = user.user_type
    return True, user.email


def sweep(client, app, role, routes):
    """Test routes for a role, returns (pass, fail, skip)."""
    section(f"{role.upper()} — {len(routes)} routes")
    p = f = s = 0
    for route in routes:
        try:
            r = client.get(route, follow_redirects=True)
            if r.status_code == 500:
                fail(f"GET {route} -> 500"); f += 1
            elif r.status_code == 404:
                skip(f"GET {route} -> 404"); s += 1
            else:
                ok(f"GET {route} -> {r.status_code}"); p += 1
        except Exception as e:
            fail(f"GET {route} -> Exception: {e}"); f += 1
    return p, f, s


def main():
    print(f"\n{C.BOLD}{C.W}")
    print("+=" + "=" * 50 + "+")
    print("|    LSPU ScholarHub — Error Sweep               |")
    print("|    Testing all routes for 500 errors            |")
    print("+=" + "=" * 50 + "+")
    print(f"{C.D}")

    app = get_app()
    tp = tf = ts = 0

    with app.test_client() as c:
        # Guest
        section("GUEST (unauthenticated)")
        for route in GUEST_ROUTES:
            try:
                r = c.get(route, follow_redirects=True)
                if r.status_code == 500:
                    fail(f"GET {route} -> 500"); tf += 1
                else:
                    ok(f"GET {route} -> {r.status_code}"); tp += 1
            except Exception as e:
                fail(f"GET {route} -> Exception: {e}"); tf += 1

        # Authenticated roles
        for role, routes in [('student', STUDENT_ROUTES), ('staff', STAFF_ROUTES),
                             ('admin', ADMIN_ROUTES), ('super_admin', SUPER_ADMIN_ROUTES)]:
            ok2, msg = inject_session(c, app, role)
            if ok2:
                p, f, s = sweep(c, app, role, routes)
                tp += p; tf += f; ts += s
            else:
                skip(f"Could not inject session for {role}: {msg}")
                ts += len(routes)

        # Chatbot
        ok2, _ = inject_session(c, app, 'student')
        if ok2:
            section("CHATBOT")
            for route in CHATBOT_ROUTES:
                try:
                    r = c.get(route, follow_redirects=True)
                    if r.status_code == 500:
                        fail(f"GET {route} -> 500"); tf += 1
                    else:
                        ok(f"GET {route} -> {r.status_code}"); tp += 1
                except Exception as e:
                    fail(f"GET {route} -> Exception: {e}"); tf += 1

    # Summary
    total = tp + tf + ts
    print(f"\n{C.BOLD}{C.W}" + "=" * 60)
    print(f"  ERROR SWEEP SUMMARY")
    print(f"=" * 60 + f"{C.D}")
    print(f"\n  Total routes tested:  {total}")
    print(f"  {C.G}Passed:  {tp}{C.D}")
    print(f"  {C.R}Failed:  {tf}{C.D}")
    print(f"  {C.Y}Skipped: {ts}{C.D}")

    if tf == 0:
        print(f"\n  {C.G}{C.BOLD}ALL CLEAR - No 500 errors found!{C.D}\n")
    else:
        print(f"\n  {C.R}{C.BOLD}{tf} route(s) returned 500 - fix before deploying!{C.D}\n")

    return 1 if tf > 0 else 0

if __name__ == '__main__':
    sys.exit(main())
