"""Post-upgrade system test — verifies all routes work after multi-campus changes."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from app import create_app, db

app = create_app()
app.config['TESTING'] = True
app.config['WTF_CSRF_ENABLED'] = False

results = []

def test(label, fn):
    try:
        fn()
        results.append(('pass', label))
    except Exception as e:
        results.append(('fail', label, str(e)))

with app.app_context():
    with app.test_client() as c:
        # GUEST PAGES
        test("Home page", lambda: c.get('/').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Scholarship list", lambda: c.get('/scholarship/').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Chatbot page", lambda: c.get('/chatbot/').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Login page", lambda: c.get('/auth/login').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        
        r = c.get('/auth/register')
        has_campus = b'campus_id' in r.data or b'Campus' in r.data
        test("Register page has campus dropdown", lambda: None if has_campus else (_ for _ in ()).throw(AssertionError("campus_id not in form")))

        # STUDENT (user 150, Santa Cruz)
        with c.session_transaction() as s:
            s['user_id'] = 150
            s['user_type'] = 'student'
            s['campus_id'] = 1
            s['campus_name'] = 'Santa Cruz Campus'

        test("Student dashboard", lambda: c.get('/student/dashboard').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Student applications", lambda: c.get('/student/applications').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Student profile", lambda: c.get('/student/profile').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Student notifications", lambda: c.get('/student/notifications').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Student M&E download", lambda: None if c.get('/student/monitoring-form/download').status_code == 200 else (_ for _ in ()).throw(AssertionError()))
        test("Student my-scholarship", lambda: None if c.get('/student/my-scholarship').status_code in (200, 302) else (_ for _ in ()).throw(AssertionError()))
        
        r = c.get('/scholarship/')
        test("Student sees campus scholarships", lambda: None if r.status_code == 200 else (_ for _ in ()).throw(AssertionError()))

        # STAFF (Alfonso, Santa Cruz)
        with c.session_transaction() as s:
            s['user_id'] = 53
            s['user_type'] = 'staff'
            s['campus_id'] = 1
            s['campus_name'] = 'Santa Cruz Campus'

        test("Staff dashboard", lambda: c.get('/staff/').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Staff review", lambda: c.get('/staff/review-applications').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Staff monitoring", lambda: c.get('/staff/monitoring').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Staff batches", lambda: c.get('/staff/batches').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Staff reports", lambda: c.get('/staff/reports').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Staff students", lambda: c.get('/staff/students').status_code == 200 or (_ for _ in ()).throw(AssertionError()))

        # ADMIN (university_admin)
        with c.session_transaction() as s:
            s['user_id'] = 1
            s['user_type'] = 'university_admin'

        test("Admin dashboard", lambda: c.get('/admin/').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin users", lambda: c.get('/admin/users').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin scholarships", lambda: c.get('/admin/scholarships').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin applications", lambda: c.get('/admin/applications').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin monitoring", lambda: c.get('/admin/monitoring').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin batches", lambda: c.get('/admin/batches').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin settings", lambda: c.get('/admin/settings').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin students", lambda: c.get('/admin/students').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin reports", lambda: c.get('/admin/reports').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin notifications", lambda: c.get('/admin/notifications').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin audit log", lambda: c.get('/admin/audit-log').status_code == 200 or (_ for _ in ()).throw(AssertionError()))
        test("Admin import", lambda: c.get('/admin/import').status_code == 200 or (_ for _ in ()).throw(AssertionError()))

        # CAMPUS CONTEXT
        test("Switch to all campuses", lambda: None if c.get('/admin/campus-context/0', follow_redirects=False).status_code == 302 else (_ for _ in ()).throw(AssertionError()))
        test("Switch to Santa Cruz", lambda: None if c.get('/admin/campus-context/1', follow_redirects=False).status_code == 302 else (_ for _ in ()).throw(AssertionError()))
        test("Switch to Siniloan", lambda: None if c.get('/admin/campus-context/2', follow_redirects=False).status_code == 302 else (_ for _ in ()).throw(AssertionError()))

        # HEALTH
        test("Health endpoint", lambda: c.get('/health').status_code == 200 or (_ for _ in ()).throw(AssertionError()))

# Print results
print("\n" + "=" * 55)
print("  POST-UPGRADE SYSTEM TEST RESULTS")
print("=" * 55)
for item in results:
    if item[0] == 'pass':
        print(f"  {item[1]:.<45} PASS")
    else:
        print(f"  {item[1]:.<45} FAIL")
        print(f"    -> {item[2]}")

passed = sum(1 for r in results if r[0] == 'pass')
failed = sum(1 for r in results if r[0] == 'fail')
print(f"\n  TOTAL: {passed} passed, {failed} failed out of {len(results)} tests")
print("=" * 55)
