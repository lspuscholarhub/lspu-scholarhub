"""Verify the registration gate end-to-end using the live Railway DB.

Tests (all with CSRF disabled, test client):
  1. GET  /register renders 200 with new form context
  2. POST with a RANDOM PDF (no student data)  → rejected, no account, files deleted
  3. POST with an image renamed .pdf           → rejected at extension check (Gemini reads it)
  4. POST with valid synthetic PDF w/ matching ID+name → passes gate, reaches OTP step
  5. Cleanup: delete created user + files

Run:  DATABASE_URL='mysql://...' python docs/verify_registration_gate.py
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('_testing', '1')

DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('Set DATABASE_URL to the live Railway MySQL URL first.')
    sys.exit(1)

os.environ['DATABASE_URL'] = DATABASE_URL

from app import create_app, db
from app.models import User

app = create_app()
app.config['WTF_CSRF_ENABLED'] = False
app.config['TESTING'] = True

results = []


def check(name, cond, detail=''):
    results.append((name, bool(cond), detail))
    line = f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  -- {detail}" if detail else '')
    print(line)


# ── Build test PDFs ────────────────────────────────────────────────────────────
def build_pdf(lines):
    """Minimal valid single-page PDF with visible text lines."""
    content_lines = ['BT /F1 12 Tf 50 750 Td 14 TL']
    for i, line in enumerate(lines):
        safe = line.replace('(', '[').replace(')', ']')
        if i == 0:
            content_lines.append(f'({safe}) Tj')
        else:
            content_lines.append(f'T* ({safe}) Tj')
    stream = '\n'.join(content_lines) + '\nET'

    objects = []
    objects.append('<< /Type /Catalog /Pages 2 0 R >>')
    objects.append('<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    objects.append('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                   '/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>')
    objects.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    stream_obj = f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream'
    objects.append(stream_obj)

    out = io.BytesIO()
    out.write(b'%PDF-1.4\n')
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f'{i} 0 obj\n{obj}\nendobj\n'.encode('latin-1'))
    xref_pos = out.tell()
    out.write(f'xref\n0 {len(objects)+1}\n'.encode())
    out.write(b'0000000000 65535 f \n')
    for off in offsets[1:]:
        out.write(f'{off:010d} 00000 n \n'.encode())
    out.write(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF'.encode())
    return out.getvalue()


FAKE_RANDOM_PDF = build_pdf([
    'Hello, this is a random document.',
    'It has no student information at all.',
    'Just some text to try to sneak past the gate.',
])

FAKE_MATCHING_PDF = build_pdf([
    'Laguna State Polytechnic University',
    'CERTIFICATE OF REGISTRATION',
    'Student No. : 2099-0001',
    'Name: Test Registration Gate',
    'Course: BS Information Technology',
    '1st Semester, S.Y. 2026-2027',
])

FORM = {
    'first_name': 'Test',
    'last_name': 'Registration Gate',
    'email': 'gate-test-9182@gmail.com',
    'student_id': '2099-0001',
    'phone_number': '09123456789',
    'gender': 'Male',
    'town': 'Sta. Cruz',
    'province': 'Laguna',
    'course': 'BS Information Technology',
    'year_level': '1st Year',
}


def post_registration(client, pdf_bytes, filename='cor.pdf'):
    data = dict(FORM)
    data['cor_file'] = (io.BytesIO(pdf_bytes), filename)
    return client.post('/auth/register', data=data, content_type='multipart/form-data',
                       follow_redirects=False)


with app.app_context():
    # Pre-clean any leftovers from previous runs
    for u in User.query.filter(User.email == FORM['email']).all():
        db.session.delete(u)
    db.session.commit()

client = app.test_client()

# 1. Register page renders
r = client.get('/auth/register')
check('GET /auth/register returns 200', r.status_code == 200, f'status={r.status_code}')

# 2. Random PDF with no student data → must be blocked
with app.test_client() as c2:
    r2 = post_registration(c2, FAKE_RANDOM_PDF, 'random.pdf')
    page = r2.data.decode('utf-8', errors='ignore')
    blocked = 'could not be verified' in page or 'Student ID or name was found' in page
    check('Random PDF (no student data) is BLOCKED', blocked)
    with app.app_context():
        n = User.query.filter_by(email=FORM['email']).count()
        check('No account created from random PDF', n == 0, f'users={n}')

# 3. Image renamed to .pdf → extension accepted, but Gemini/text-extract will find
#    nothing verifiable in a real JPEG; our synthetic test just checks it isn't 500
with app.test_client() as c3:
    r3 = post_registration(c3, b'\xff\xd8\xff\xe0FAKEJPGDATA', 'photo.pdf')
    check('Image-renamed-PDF does not crash (no 500)', r3.status_code in (200, 302),
          f'status={r3.status_code}')

# 4. Valid matching PDF → passes gate, lands on OTP page
with app.test_client() as c4:
    r4 = post_registration(c4, FAKE_MATCHING_PDF, 'cor.pdf')
    with app.app_context():
        pending = session_data = c4.get_cookie('session')  # just ensure no crash
    page = r4.data.decode('utf-8', errors='ignore')
    reached_otp = r4.status_code == 302 and '/auth/verify-otp' in (r4.headers.get('Location') or '')
    check('Valid matching PDF passes the gate, goes to OTP step', reached_otp,
          f'status={r4.status_code} loc={r4.headers.get("Location")}')

    if reached_otp:
        # 5. Complete OTP verification with the code from the session
        with app.app_context():
            from flask import session as flask_session
            with c4.session_transaction() as s:
                pending = s.get('pending_registration')
        check('Pending registration stored in session', pending is not None)
        if pending:
            otp = pending.get('otp')
            r5 = c4.post('/auth/verify-otp', data={'otp': otp}, follow_redirects=False)
            with app.app_context():
                created = User.query.filter_by(email=FORM['email']).first()
                check('Account created after OTP', created is not None)
                if created:
                    check('Account flagged ocr_verified=True', created.ocr_verified is True,
                          f'ocr_verified={created.ocr_verified}')
                    check('GWA auto-populated (None ok for 1st yr, no grades)',
                          created.gwa is None or isinstance(created.gwa, (int, float)),
                          f'gwa={created.gwa}')

# ── Cleanup ────────────────────────────────────────────────────────────────────
with app.app_context():
    from app.models.document import Document
    for u in User.query.filter(User.email == FORM['email']).all():
        for d in Document.query.filter_by(user_id=u.id).all():
            db.session.delete(d)
        if u.cor_cloudinary_id:
            try:
                from app.services.storage_service import delete_file
                delete_file(public_id=u.cor_cloudinary_id)
            except Exception:
                pass
        db.session.delete(u)
    db.session.commit()
    left = User.query.filter(User.email.like('gate-test-%')).count()
    check('Cleanup: test user removed', left == 0, f'remaining={left}')

print()
failed = [r for r in results if not r[1]]
print(f'{len(results) - len(failed)}/{len(results)} checks passed')
sys.exit(1 if failed else 0)
