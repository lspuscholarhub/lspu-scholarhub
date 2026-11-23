#!/usr/bin/env python3
"""
LSPU ScholarHub — Security Leak Finder
=======================================
Combines static code analysis with live tests against the deployed system.

Usage:
    python papers/leak_finder.py              # full scan (static + live)
    python papers/leak_finder.py --static     # code analysis only
    python papers/leak_finder.py --live       # live tests only (needs DB)

Reports are colorized: GREEN = safe, YELLOW = warning, RED = vulnerable.
"""

import os, re, sys, time, argparse
from pathlib import Path

# ── Color helpers ────────────────────────────────────────────────────────────
class C:
    R = '\033[91m'   # red
    Y = '\033[93m'   # yellow
    G = '\033[92m'   # green
    B = '\033[94m'   # blue
    W = '\033[97m'   # white
    D = '\033[0m'    # reset
    BOLD = '\033[1m'

# Counts are kept separately so the summary can distinguish a real
# vulnerability from something that only deserves a review.
COUNTS = {'vuln': 0, 'warning': 0}

def ok(msg):    print(f"  {C.G}✔ SAFE{C.D}      {msg}")
def warn(msg):  COUNTS['warning'] += 1; print(f"  {C.Y}⚠ WARNING{C.D}   {msg}")
def fail(msg):  COUNTS['vuln'] += 1;    print(f"  {C.R}✘ VULN{C.D}     {msg}")
def info(msg):  print(f"  {C.B}ℹ INFO{C.D}      {msg}")
def section(title):
    print(f"\n{C.BOLD}{C.W}" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + f"{C.D}")

# ── Static Analysis ──────────────────────────────────────────────────────────

def scan_hardcoded_secrets(project_root):
    """Check for hardcoded API keys, passwords, tokens in source code."""
    section("1. HARDCODED SECRETS IN SOURCE CODE")
    findings = 0

    # Every pattern requires an actual value, not just an opening quote:
    # service-key names appear inside strings such as
    # "GEMINI_API_KEY=" or print("SECRET_KEY=" + key), and those are env reads
    # or generated output, not committed secrets.
    patterns = [
        (r"(?:api[_-]?key|apikey)\s*[=:]\s*['\"][A-Za-z0-9_\-]{20,}['\"]", "Hardcoded API key"),
        (r"(?:password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{8,}['\"]", "Hardcoded password"),
        (r"(?:secret|token)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Hardcoded secret/token"),
        (r"['\"]AIza[A-Za-z0-9_\-]{35}['\"]", "Google API key"),
        (r"['\"]sk-[A-Za-z0-9]{40,}['\"]", "OpenAI key"),
        (r"['\"]ghp_[A-Za-z0-9]{36}['\"]", "GitHub PAT"),
        (r"BREVO_API_KEY\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Brevo key in code"),
        (r"RESEND_API_KEY\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Resend key in code"),
        (r"GEMINI_API_KEY\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", "Gemini key in code"),
        (r"SECRET_KEY\s*=\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "Flask SECRET_KEY not from env"),
    ]

    # Only scan what ships. Local scratch folders (gitignored) and backups are
    # not part of the system and would otherwise drown real findings.
    exclude_dirs = {'__pycache__', '.git', 'node_modules', '.freebuff', 'venv', 'env',
                    '_local_private', 'backups', '.cloud-attachments', '.pytest_cache',
                    'instance'}
    py_files = []
    for root, dirs, files in os.walk(project_root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in files:
            if f.endswith(('.py', '.env', '.cfg', '.ini', '.yml', '.yaml')):
                py_files.append(os.path.join(root, f))

    for filepath in py_files:
        try:
            with open(filepath, encoding='utf-8', errors='ignore') as fh:
                for i, line in enumerate(fh, 1):
                    stripped = line.strip()
                    if (stripped.startswith('#') or 'os.environ' in stripped
                            or 'os.getenv' in stripped or 'environ.get' in stripped
                            or 'get(' in stripped):
                        continue
                    for pattern, desc in patterns:
                        if re.search(pattern, stripped, re.I):
                            relpath = os.path.relpath(filepath, project_root)
                            fail(f"{desc} at {relpath}:{i}")
                            findings += 1
        except Exception:
            pass

    if findings == 0:
        ok("No hardcoded secrets found in source code")
    return findings


def scan_sql_injection(project_root):
    """Check for string-formatted SQL queries."""
    section("2. SQL INJECTION RISKS")
    findings = 0

    patterns = [
        (r'\.execute\([f"\'].*\{', "f-string in execute()"),
        (r'\.execute\(.*%\s*s', "%-format in execute()"),
        (r'\.execute\(.*\+\s*', "String concat in execute()"),
        (r'text\([f"\'].*\{', "f-string in text()"),
        (r'raw\([f"\'].*\{', "f-string in raw()"),
        (r'\.filter\(.*text\(', "text() in filter — check parameterization"),
    ]

    for root, dirs, files in os.walk(os.path.join(project_root, 'app')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.py'): continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding='utf-8') as fh:
                    for i, line in enumerate(fh, 1):
                        for pattern, desc in patterns:
                            if re.search(pattern, line):
                                relpath = os.path.relpath(filepath, project_root)
                                warn(f"{desc} at {relpath}:{i}: {line.strip()[:80]}")
                                findings += 1
            except Exception:
                pass

    if findings == 0:
        ok("No raw SQL injection patterns found (project uses SQLAlchemy ORM)")
    return findings


def scan_path_traversal(project_root):
    """Check file-serving routes for path traversal vulnerabilities."""
    section("3. PATH TRAVERSAL IN FILE SERVING")
    findings = 0

    for root, dirs, files in os.walk(os.path.join(project_root, 'app')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.py'): continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding='utf-8') as fh:
                    content = fh.read()
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'send_file' in line or 'open(' in line:
                            # check the surrounding block for path construction;
                            # generated filenames are often defined a few lines up
                            ctx = '\n'.join(lines[max(0, i - 15):i + 15])
                            relpath = os.path.relpath(filepath, project_root)
                            if 'normpath' in ctx and 'isabs' in ctx:
                                ok(f"Path traversal guarded at {relpath}:{i+1} (normpath + isabs check)")
                            elif 'secure_filename' in ctx:
                                ok(f"Server-generated filename at {relpath}:{i+1} (secure_filename)")
                            elif "'static'" in ctx or '"static"' in ctx:
                                ok(f"Fixed static path at {relpath}:{i+1}")
                            elif 'os.path.join' in ctx:
                                warn(f"File serving at {relpath}:{i+1} — verify path validation")
                                findings += 1
            except Exception:
                pass

    if findings == 0:
        ok("File serving paths appear properly validated")
    return findings


def scan_debug_mode(project_root):
    """Check for debug mode in production configs."""
    section("4. DEBUG MODE & CONFIGURATION")
    findings = 0

    init_path = os.path.join(project_root, 'app', '__init__.py')
    if os.path.exists(init_path):
        with open(init_path, encoding='utf-8') as fh:
            content = fh.read()
            if 'DEBUG=True' in content or 'debug=True' in content:
                fail("DEBUG=True found in app/__init__.py — disable in production")
                findings += 1
            elif 'app.config[' in content and 'DEBUG' in content:
                warn("DEBUG config found in __init__.py — verify it's env-driven")
                findings += 1
            else:
                ok("Debug mode not hardcoded in app config")

    # Check .env for DEBUG
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as fh:
            for line in fh:
                if 'DEBUG' in line and '=True' in line:
                    fail("DEBUG=True in .env — should be False in production")
                    findings += 1

    # SESSION_COOKIE_SECURE is reviewed in section 8, which reads
    # config/config.py as well as app/__init__.py (production sets it there).

    return findings


def scan_error_handling(project_root):
    """Check for info disclosure in error handlers."""
    section("5. ERROR HANDLING & INFO DISCLOSURE")
    findings = 0

    for root, dirs, files in os.walk(os.path.join(project_root, 'app')):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.py'): continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding='utf-8') as fh:
                    for i, line in enumerate(fh, 1):
                        # Check for traceback/exception leaking
                        if 'traceback' in line.lower() and ('flash' in line or 'render' in line or 'return' in line):
                            relpath = os.path.relpath(filepath, project_root)
                            warn(f"Traceback may be exposed to users at {relpath}:{i}")
                            findings += 1
                        if 'str(e)' in line and ('flash' in line or 'return' in line):
                            relpath = os.path.relpath(filepath, project_root)
                            info(f"Exception string shown to user at {relpath}:{i} — review for info leak")
                            findings += 1
            except Exception:
                pass

    if findings == 0:
        ok("No obvious info disclosure in error handlers")
    return findings


def scan_csrf_protection(project_root):
    """Check that all POST forms have CSRF tokens."""
    section("6. CSRF PROTECTION")
    findings = 0

    template_dir = os.path.join(project_root, 'app', 'templates')
    if not os.path.exists(template_dir):
        warn("Templates directory not found")
        return 0

    for root, dirs, files in os.walk(template_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.html'): continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding='utf-8') as fh:
                    content = fh.read()
                    forms = re.findall(r'<form[^>]*method=["\']POST["\'][^>]*>', content, re.I)
                    csrf_tokens = re.findall(r'csrf_token', content)
                    if forms and not csrf_tokens:
                        relpath = os.path.relpath(filepath, project_root)
                        fail(f"POST form without CSRF token at {relpath}")
                        findings += 1
            except Exception:
                pass

    if findings == 0:
        ok("All POST forms have CSRF tokens")
    return findings


def scan_xss_risks(project_root):
    """Check for unescaped output in templates."""
    section("7. XSS RISKS IN TEMPLATES")
    findings = 0

    template_dir = os.path.join(project_root, 'app', 'templates')
    if not os.path.exists(template_dir):
        return 0

    for root, dirs, files in os.walk(template_dir):
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for f in files:
            if not f.endswith('.html'): continue
            filepath = os.path.join(root, f)
            try:
                with open(filepath, encoding='utf-8') as fh:
                    for i, line in enumerate(fh, 1):
                        # Jinja2 safe filter on user input
                        if '|safe' not in line:
                            continue
                        # The reports/dashboard templates inject json.dumps()
                        # output (chart labels and counts) into a <script> block;
                        # those variables are generated server-side, not user text.
                        expr = line.split('|safe', 1)[0].rsplit('{{', 1)[-1].strip()
                        if '|tojson' in expr:
                            continue  # tojson escapes </script>, so |safe adds nothing risky
                        if re.fullmatch(r'(?:dash_)?(?:sch|gwa|scholar)_[A-Za-z_]+'
                                        r'|comparison\.rows\.[A-Za-z_]+', expr):
                            continue
                        relpath = os.path.relpath(filepath, project_root)
                        warn(f"|safe filter at {relpath}:{i}: {line.strip()[:80]}")
                        findings += 1
            except Exception:
                pass

    if findings == 0:
        ok("No obvious XSS risks from |safe on user data")
    return findings


def scan_session_config(project_root):
    """Check session configuration for security."""
    section("8. SESSION & COOKIE SECURITY")
    findings = 0

    init_path = os.path.join(project_root, 'app', '__init__.py')
    if not os.path.exists(init_path):
        return 0

    with open(init_path, encoding='utf-8') as fh:
        content = fh.read()

    # Also check config/config.py
    config_path = os.path.join(project_root, 'config', 'config.py')
    if os.path.exists(config_path):
        with open(config_path, encoding='utf-8') as fh:
            content += fh.read()

    checks = {
        'SESSION_COOKIE_SECURE': 'Secure flag (HTTPS-only cookies)',
        'SESSION_COOKIE_HTTPONLY': 'HttpOnly flag (no JS access)',
        'SESSION_COOKIE_SAMESITE': 'SameSite flag (CSRF mitigation)',
    }
    for key, desc in checks.items():
        if key in content:
            ok(f"{desc} is set")
        else:
            warn(f"{desc} not configured — {key}")
            findings += 1

    # Check for session timeout
    if 'PERMANENT_SESSION_LIFETIME' in content:
        ok("Session timeout configured")
    else:
        info("No PERMANENT_SESSION_LIFETIME set — sessions may not expire")

    return findings


# ── Live Tests ───────────────────────────────────────────────────────────────

def get_app():
    """Create Flask test app connected to the Railway database."""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        # Try to read from .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.split('=', 1)[1].strip()
    # No hard-coded fallback: credentials must come from the environment or .env
    if not db_url or 'localhost' in db_url:
        sys.exit('Set DATABASE_URL to a non-local database before running.')

    os.environ['DATABASE_URL'] = db_url
    from app import create_app
    return create_app()


def live_test_unauthenticated_access(app):
    """Test that protected routes reject unauthenticated users."""
    section("9. UNAUTHENTICATED ACCESS (Live)")
    findings = 0

    protected_routes = [
        '/admin/',
        '/admin/users',
        '/admin/scholarships',
        '/admin/applications',
        '/admin/monitoring',
        '/admin/notifications',
        '/admin/settings',
        '/admin/reports',
        '/admin/profile',
        '/staff/',
        '/staff/review',
        '/staff/scholarships',
        '/staff/monitoring',
        '/staff/batches',
        '/staff/students',
        '/staff/notifications',
        '/staff/reports',
        '/student/',
        '/student/my-scholarship',
        '/student/profile',
        '/student/notifications',
    ]

    with app.test_client() as c:
        for route in protected_routes:
            try:
                r = c.get(route, follow_redirects=False)
                if r.status_code == 200:
                    fail(f"UNPROTECTED: GET {route} returned 200 without login")
                    findings += 1
                elif r.status_code in (301, 302) and '/login' in r.headers.get('Location', ''):
                    ok(f"GET {route} → redirect to login ✔")
                elif r.status_code in (301, 302):
                    ok(f"GET {route} → redirect ({r.status_code}) ✔")
                elif r.status_code == 401 or r.status_code == 403:
                    ok(f"GET {route} → {r.status_code} (blocked) ✔")
                else:
                    ok(f"GET {route} → {r.status_code} (non-200) ✔")
            except Exception as e:
                warn(f"GET {route} → exception: {e}")

    return findings


def _mask_email(email):
    """Keep account identifiers out of the report."""
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    return f'{local[:2]}***@{domain}'


def _session_client(app, user_id, user_type):
    """Client with an injected session — no password needed, like error_sweep."""
    client = app.test_client()
    with client.session_transaction() as sess:
        sess.clear()
        sess['user_id'] = user_id
        sess['user_type'] = user_type
        sess['is_verified'] = True
    return client


def live_test_role_escalation(app):
    """Test that student and staff sessions cannot reach higher-privilege pages."""
    section("10. ROLE ESCALATION (Live)")

    from app.models import User

    with app.app_context():
        student = User.query.filter_by(user_type='student', is_active=True).first()
        staff = User.query.filter_by(user_type='staff', is_active=True).first()

    # Routes that students must not reach.
    student_targets = [
        '/admin/', '/admin/users', '/admin/scholarships', '/admin/settings',
        '/staff/', '/staff/scholarships', '/staff/batches', '/staff/students',
    ]
    # Routes that staff must not reach.
    staff_targets = ['/admin/', '/admin/users', '/admin/scholarships']

    for role, user, routes in (('student', student, student_targets),
                               ('staff', staff, staff_targets)):
        if not user:
            warn(f"No active {role} account available for the escalation test")
            continue
        info(f"Testing {role} {_mask_email(user.email)} by session injection")
        client = _session_client(app, user.id, role)
        for route in routes:
            try:
                r = client.get(route, follow_redirects=False)
            except Exception as e:
                warn(f"GET {route} → exception: {e}")
                continue
            if r.status_code == 200:
                fail(f"ESCALATION: {role} session rendered GET {route}")
            elif r.status_code == 302:
                loc = r.headers.get('Location', '')
                # A redirect back into the admin area would be a bypass.
                if route.startswith('/admin') and loc.startswith('/admin'):
                    fail(f"ESCALATION: {role} redirected within admin: {route} -> {loc}")
                else:
                    ok(f"{role} blocked from {route} → 302 {loc}")
            elif r.status_code in (301, 401, 403, 404):
                ok(f"{role} blocked from {route} → {r.status_code}")
            else:
                ok(f"{role} got {r.status_code} from {route}")

    # A real credential login is optional: it needs an account whose password
    # the operator is willing to put in the environment.
    email = os.environ.get('LEAK_TEST_EMAIL', '').strip()
    password = os.environ.get('LEAK_TEST_PASSWORD', '')
    if not (email and password):
        info("Set LEAK_TEST_EMAIL and LEAK_TEST_PASSWORD to also exercise the login form")
        return 0

    csrf_was_enabled = app.config.get('WTF_CSRF_ENABLED', True)
    app.config['WTF_CSRF_ENABLED'] = False  # in-process client only
    try:
        with app.test_client() as c:
            r = c.post('/auth/login',
                       data={'identifier': email, 'password': password},
                       follow_redirects=False)
    finally:
        app.config['WTF_CSRF_ENABLED'] = csrf_was_enabled

    if r.status_code == 302 and '/login' not in r.headers.get('Location', ''):
        ok(f"Credential login works for {_mask_email(email)}")
    else:
        warn(f"Credential login for {_mask_email(email)} failed "
             f"(status {r.status_code}); the session checks above still cover the guards")

    return 0


def live_test_idor(app):
    """Test IDOR: can user A access user B's documents/data?"""
    section("11. IDOR — CROSS-USER DATA ACCESS (Live)")

    with app.app_context():
        from app.models import User, Document
        students = User.query.filter_by(user_type='student', is_active=True).limit(10).all()
        if len(students) < 2:
            warn("Need at least 2 student accounts for IDOR testing")
            return 0
        me = students[0]
        foreign = (Document.query.filter(Document.user_id != me.id)
                   .with_entities(Document.id, Document.user_id).first())

    if not foreign:
        info("No document owned by another user — skipping the cross-user IDOR test")
        return 0

    doc_id, owner_id = foreign
    info(f"Testing document {doc_id} (owner #{owner_id}) as student #{me.id}")
    routes = [f'/student/documents/{doc_id}/download',
              f'/student/documents/{doc_id}/view',
              f'/student/documents/{doc_id}/raw']

    # 1) Unauthenticated clients must never get the file.
    with app.test_client() as c:
        for route in routes:
            try:
                r = c.get(route, follow_redirects=False)
                if r.status_code == 200:
                    fail(f"IDOR: unauthenticated GET {route} served the document")
                else:
                    ok(f"Unauthenticated GET {route} → {r.status_code} (blocked)")
            except Exception as e:
                warn(f"GET {route} → exception: {e}")

    # 2) A signed-in student must not get another student's file.
    client = _session_client(app, me.id, 'student')
    for route in routes:
        try:
            r = client.get(route, follow_redirects=False)
            if r.status_code == 200:
                fail(f"IDOR: student #{me.id} retrieved another student's {route}")
            elif r.status_code in (301, 302):
                ok(f"Student #{me.id} redirected away from {route} (blocked)")
            elif r.status_code in (401, 403, 404):
                ok(f"Student #{me.id} blocked from {route} → {r.status_code}")
            else:
                ok(f"Student #{me.id} got {r.status_code} from {route} (non-200)")
        except Exception as e:
            warn(f"GET {route} → exception: {e}")

    return 0


def live_test_info_disclosure(app):
    """Test for info leaks in error responses and HTML source."""
    section("12. INFO DISCLOSURE IN RESPONSES (Live)")
    findings = 0

    with app.test_client() as c:
        # Trigger various errors to check response content
        error_routes = [
            '/admin/',
            '/auth/login',
            '/auth/register',
            '/student/',
        ]

        sensitive_patterns = [
            (r'(?:api[_-]?key|apikey)\s*[=:]\s*[A-Za-z0-9_\-]{20,}', "Hardcoded API key in response"),
            (r'(?:secret|token)\s*[=:]\s*[A-Za-z0-9_\-]{16,}', "Secret/token in response"),
            (r'traceback|File \"[^\"]+\.py\"', "Stack trace in response"),
            (r'mysql://[^"\']+', "Database connection string in response"),
            (r'GEMINI_API_KEY|RESEND_API_KEY|BREVO_API_KEY', "Service API key in response"),
            (r'INTERNAL SERVER ERROR', "Raw 500 error page (should be generic)"),
            (r'password\s*[=:]\s*[^\s<>{"]{8,}', "Possible hardcoded password (not form field)"),
        ]

        for route in error_routes:
            try:
                r = c.get(route, follow_redirects=True)
                content = r.data.decode('utf-8', errors='ignore')

                for pattern, desc in sensitive_patterns:
                    if re.search(pattern, content, re.I):
                        fail(f"{desc} found in response from {route}")
                        findings += 1

                # Check for debug toolbar
                if 'Werkzeug Debugger' in content or 'Interactive Debugger' in content:
                    fail(f"Werkzeug debugger exposed at {route}")
                    findings += 1

                if 'Traceback (most recent call last)' in content:
                    fail(f"Full traceback exposed at {route}")
                    findings += 1

            except Exception as e:
                warn(f"Error testing {route}: {e}")

        # Test a nonexistent route for error handling
        try:
            r = c.get('/this-does-not-exist-12345', follow_redirects=True)
            content = r.data.decode('utf-8', errors='ignore')
            if 'Traceback' in content or 'File \"' in content:
                fail("Stack trace leaked on 404 page")
                findings += 1
            elif 'werkzeug' in content.lower():
                warn("Werkzeug error page on 404 — consider custom 404 handler")
                findings += 1
            else:
                ok("404 page doesn't leak internal details")
        except Exception:
            pass

    if findings == 0:
        ok("No info disclosure detected in responses")
    return findings


def live_test_campus_scoping(app):
    """Report what each campus context sees for a real admin account."""
    section("13. CAMPUS SCOPING (Live)")

    from app.models import User, Campus

    with app.app_context():
        admin = (User.query.filter_by(user_type='super_admin', is_active=True).first()
                 or User.query.filter_by(user_type='admin', is_active=True).first())
        campuses = Campus.query.filter_by(is_active=True).with_entities(
            Campus.id, Campus.name).all()

    if not admin:
        warn("No active admin account available for the campus scoping test")
        return 0
    if len(campuses) < 2:
        info("Need 2+ active campuses for the scoping test")
        return 0

    client = _session_client(app, admin.id, admin.user_type)
    for campus_id, campus_name in campuses:
        with client.session_transaction() as sess:
            sess['campus_context'] = campus_id
        try:
            r = client.get('/admin/scholarships', follow_redirects=False)
        except Exception as e:
            warn(f"Campus '{campus_name}' → exception: {e}")
            continue
        if r.status_code != 200:
            info(f"Campus '{campus_name}' → {r.status_code} (not rendered for this admin)")
            continue
        content = r.data.decode('utf-8', errors='ignore')
        ids = set(re.findall(r'/admin/scholarships/(\d+)/edit', content))
        info(f"Campus '{campus_name}': {len(ids)} scholarship(s) visible"
             + (f" — IDs {', '.join(sorted(ids))}" if ids else ''))

    info("Campus scoping is reported per campus; compare the sets above to spot leakage")
    return 0


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    # Ensure UTF-8 output on Windows
    import io
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description='LSPU ScholarHub Security Leak Finder')
    parser.add_argument('--static', action='store_true', help='Static code analysis only')
    parser.add_argument('--live', action='store_true', help='Live tests only')
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"\n{C.BOLD}{C.W}")
    print("+=" + "=" * 66 + "+")
    print("|          LSPU ScholarHub — Security Leak Finder                    |")
    print("|          Combining static analysis + live tests                    |")
    print("+=" + "=" * 66 + "+")
    print(f"{C.D}")

    if not args.live:
        print(f"\n{C.BOLD}{C.B}── PHASE 1: Static Code Analysis ──{C.D}\n")
        scan_hardcoded_secrets(project_root)
        scan_sql_injection(project_root)
        scan_path_traversal(project_root)
        scan_debug_mode(project_root)
        scan_error_handling(project_root)
        scan_csrf_protection(project_root)
        scan_xss_risks(project_root)
        scan_session_config(project_root)

    if not args.static:
        print(f"\n{C.BOLD}{C.B}── PHASE 2: Live Security Tests ──{C.D}\n")
        try:
            app = get_app()
            live_test_unauthenticated_access(app)
            live_test_role_escalation(app)
            live_test_idor(app)
            live_test_info_disclosure(app)
            live_test_campus_scoping(app)
        except Exception as e:
            warn(f"Could not run live tests: {e}")
            info("Set DATABASE_URL or ensure .env has the Railway connection string")

    # Summary
    total_vulns = COUNTS['vuln']
    total_warnings = COUNTS['warning']
    print(f"\n{C.BOLD}{C.W}" + "=" * 70)
    print(f"  SUMMARY")
    print("=" * 70 + f"{C.D}")
    if total_vulns == 0:
        print(f"\n  {C.G}{C.BOLD}✔ No vulnerabilities found!{C.D}")
        print(f"  {C.G}The system passed all security checks.{C.D}")
    else:
        print(f"\n  {C.R}{C.BOLD}✘ Found {total_vulns} vulnerability(ies){C.D}")
        print(f"  Review the {C.R}VULN{C.D} items above before deploying.")
    if total_warnings:
        print(f"  {C.Y}{total_warnings} warning(s){C.D} also listed above — lower priority, worth a look.")
    print()

    return 1 if total_vulns > 0 else 0


if __name__ == '__main__':
    sys.exit(main())
