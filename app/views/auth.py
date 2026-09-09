"""
Authentication views for LSPU ScholarHub.

Registration workflow:
  1. Student fills form + uploads COR/grades PDFs → contents verified inline
     (Student ID + name + course must match the form) → OTP sent to email
  2. Student enters OTP on verify page → account created → credentials emailed
  3. Instant access — but ONLY verified LSPU documents can ever reach this step

Login:
  - Accepts email OR student_id as the identifier
"""

import os
import re
import secrets
import string
from datetime import datetime, timedelta
from flask import (Blueprint, render_template, request, flash,
                   redirect, url_for, session)
from flask_jwt_extended import create_access_token
from app import db, limiter
from app.models import User

auth_bp = Blueprint('auth', __name__)

UPPERCLASS_YEARS = {'2nd Year', '3rd Year', '4th Year'}
OTP_EXPIRY_MINUTES = 10


# ── Helpers ───────────────────────────────────────────────────────────────────

def _generate_password(length=10):
    """Generate a secure random temporary password."""
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    pwd = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%'),
    ]
    pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
    secrets.SystemRandom().shuffle(pwd)
    return ''.join(pwd)


def _generate_otp():
    """Generate a 6-digit numeric OTP."""
    return str(secrets.randbelow(900000) + 100000)   # always 6 digits


def _send_otp_email(email, full_name, otp):
    """Send the OTP verification email."""
    try:
        from app.services.notification_service import notification_service
        subject = "LSPU ScholarHub — Email Verification Code"
        message = f"""
        <h2>Email Verification 🔐</h2>
        <p>Dear <strong>{full_name}</strong>,</p>
        <p>You are registering for <strong>LSPU ScholarHub</strong>.
           Please use the verification code below to confirm your email address.</p>
        <div style="text-align:center;margin:32px 0;">
          <div style="display:inline-block;background:#1a3a6b;color:#fff;
                      font-size:2.5rem;font-weight:700;letter-spacing:.5rem;
                      padding:16px 40px;border-radius:12px;">
            {otp}
          </div>
        </div>
        <p>This code expires in <strong>{OTP_EXPIRY_MINUTES} minutes</strong>.</p>
        <p style="color:#dc3545;">
          If you did not request this, please ignore this email.
        </p>
        <p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>
        """
        notification_service.send_email(email, subject, message)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'Could not send OTP email: {e}')


def _save_registration_file(file, user_student_id, file_type):
    """
    Save a registration document (COR or grades) to Cloudinary or local disk.
    Accepts PDF and image files (JPG, PNG).
    Returns (url_or_path, cloudinary_public_id) tuple. public_id is None for local saves.
    """
    if not file or not file.filename:
        return None, None

    from werkzeug.utils import secure_filename

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''

    allowed = {'pdf', 'jpg', 'jpeg', 'png'}
    if ext not in allowed:
        return None, None

    filename = secure_filename(
        f"{file_type}_{user_student_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
    )

    file_bytes = file.read()
    file.seek(0)

    # Try Cloudinary up to 2 times before giving up
    from app.services.storage_service import upload_file
    import logging as _log

    result = None
    for attempt in range(2):
        result = upload_file(
            file_bytes    = file_bytes,
            filename      = filename,
            folder        = f"registration/{user_student_id}",
            resource_type = 'auto',
        )
        if result['success']:
            return result['url'], result.get('public_id')
        _log.getLogger(__name__).warning(
            f'Cloudinary upload attempt {attempt+1} failed: {result.get("error")}'
        )

    # Both Cloudinary attempts failed
    # Only fall back to local if Cloudinary is NOT configured
    # (i.e. local dev environment) — on Railway we return None to block registration
    from app.services.storage_service import _cloudinary_configured
    if _cloudinary_configured():
        # On Railway — Cloudinary failed, don't save broken path
        _log.getLogger(__name__).error(
            f'Cloudinary upload failed after 2 attempts for {filename}. '
            f'Returning None to prevent broken file reference.'
        )
        return None, None

    # Local dev fallback
    from flask import current_app
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'registration')
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    with open(file_path, 'wb') as f:
        f.write(file_bytes)
    return file_path, None


def _send_credentials_email(user, temp_password):
    """Send login credentials to the newly registered student."""
    try:
        from flask import url_for as _url_for
        from app.services.notification_service import notification_service

        login_url = _url_for('auth.login', _external=True)
        subject = "Welcome to LSPU ScholarHub — Your Login Credentials"
        message = f"""
        <h2>Welcome to LSPU ScholarHub! 🎓</h2>
        <p>Dear <strong>{user.get_full_name()}</strong>,</p>
        <p>Your student account has been successfully created. Here are your login credentials:</p>
        <table style="border-collapse:collapse;margin:16px 0;">
          <tr>
            <td style="padding:8px 16px 8px 0;font-weight:bold;">Student ID:</td>
            <td style="padding:8px 0;"><code style="background:#f4f4f4;padding:4px 8px;border-radius:4px;">{user.student_id}</code></td>
          </tr>
          <tr>
            <td style="padding:8px 16px 8px 0;font-weight:bold;">Email:</td>
            <td style="padding:8px 0;"><code style="background:#f4f4f4;padding:4px 8px;border-radius:4px;">{user.email}</code></td>
          </tr>
          <tr>
            <td style="padding:8px 16px 8px 0;font-weight:bold;">Temporary Password:</td>
            <td style="padding:8px 0;"><code style="background:#fff3cd;padding:4px 8px;border-radius:4px;font-size:1.1em;">{temp_password}</code></td>
          </tr>
        </table>
        <p style="color:#dc3545;"><strong>⚠️ Important:</strong> Please log in and change your password immediately under <em>My Account → Profile</em>.</p>
        <p>You can log in at: <a href="{login_url}">{login_url}</a></p>
        <p>If you have any questions, contact us at <a href="mailto:lspu.scholarhub@gmail.com">lspu.scholarhub@gmail.com</a> or call 0968-365-2615.</p>
        <p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>
        """
        notification_service.send_email(user.email, subject, message)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'Could not send credentials email: {e}')


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('30 per 5 minutes')
def login():
    """Login with email OR student_id plus password."""
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '').strip()

        if not identifier or not password:
            flash('Please enter your Student ID (or Email) and password.', 'error')
            return render_template('auth/login.html')

        # Try email first, then student_id
        user = (User.query.filter_by(email=identifier).first()
                or User.query.filter_by(student_id=identifier).first()
                or User.query.filter_by(username=identifier).first())

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been disabled. Contact the scholarship office.', 'error')
                return render_template('auth/login.html')

            user.last_login = datetime.utcnow()
            db.session.commit()

            # Non-permanent session — expires when browser is closed
            session.permanent = False
            session['user_id']     = user.id
            session['username']    = user.username
            session['user_type']   = user.user_type
            session['is_verified'] = user.is_verified
            session['first_login'] = (user.last_login is None)
            session['last_active'] = datetime.utcnow().timestamp()

            # Audit log
            from app.services.audit_service import log_action
            log_action('auth.login',
                       f'{user.get_full_name()} ({user.username}) logged in as {user.user_type}. '
                       f'Email: {user.email}.',
                       category='auth', target_type='user', target_id=user.id,
                       user_id=user.id, user_name=user.username, user_role=user.user_type)

            flash(f'Welcome back, {user.first_name}!', 'success')

            if user.user_type == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif user.user_type == 'staff':
                return redirect(url_for('staff.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            flash('Invalid credentials. Check your Student ID (or Email) and password.', 'error')

    return render_template('auth/login.html')


# ── Register ──────────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit('20 per hour')
def register():
    """
    Step 1 of registration: validate form data, send OTP, store pending data in session.
    Account is NOT created here — only after OTP is verified.
    """
    if request.method == 'POST':
        first_name  = request.form.get('first_name',   '').strip()
        last_name   = request.form.get('last_name',    '').strip()
        middle_name = request.form.get('middle_name',  '').strip() or None  # optional
        email       = request.form.get('email',        '').strip().lower()
        student_id  = request.form.get('student_id',   '').strip()
        phone       = request.form.get('phone_number', '').strip()
        gender      = request.form.get('gender',       '').strip() or None
        town        = request.form.get('town',         '').strip() or None
        province    = request.form.get('province',     '').strip() or None
        course      = request.form.get('course',       '').strip()
        year_level  = request.form.get('year_level',   '').strip()
        birthday    = request.form.get('birthday',     '').strip()

        # ── Required fields (middle_name, gender, town, province are optional) ─
        if not all([first_name, last_name, email, student_id, phone, course, year_level, birthday]):
            flash('Please fill in all required fields.', 'error')
            return render_template('auth/register.html')

        # ── Birthday: valid date, not in the future, sane age range ─────────
        birthday_date = None
        try:
            birthday_date = datetime.strptime(birthday, '%Y-%m-%d').date()
        except ValueError:
            flash('Please provide a valid birthday.', 'error')
            return render_template('auth/register.html')
        today = datetime.utcnow().date()
        if birthday_date >= today:
            flash('Birthday must be a date in the past.', 'error')
            return render_template('auth/register.html')
        age = today.year - birthday_date.year - (
            (today.month, today.day) < (birthday_date.month, birthday_date.day))
        if age < 15 or age > 100:
            flash('Please double-check your birthday — the age you entered looks incorrect.', 'error')
            return render_template('auth/register.html')

        # ── Student ID: exactly XXXX-XXXX format ─────────────────────────────
        if not re.match(r'^\d{4}-\d{4}$', student_id):
            flash('Student ID must follow the format XXXX-XXXX (e.g. 2024-1234).', 'error')
            return render_template('auth/register.html')

        # ── Phone: exactly 11 digits ──────────────────────────────────────────
        phone_digits = re.sub(r'\D', '', phone)
        if len(phone_digits) != 11:
            flash('Phone number must be exactly 11 digits (e.g. 09123456789).', 'error')
            return render_template('auth/register.html')
        phone = phone_digits

        # ── Duplicate checks ──────────────────────────────────────────────────
        if User.query.filter_by(email=email).first():
            flash('An account with this email already exists.', 'error')
            return render_template('auth/register.html')
        if User.query.filter_by(student_id=student_id).first():
            flash('This Student ID is already registered.', 'error')
            return render_template('auth/register.html')
        if User.query.filter_by(phone_number=phone).first():
            flash('This phone number is already registered to another account.', 'error')
            return render_template('auth/register.html')

        # ── Document validation + OCR verification ────────────────────────────
        # 1st Year  → COR required, grades NOT required
        # 2nd–4th   → COR + Copy of Grades both required
        cor_path    = None
        grades_path = None
        auto_gwa    = None

        NEEDS_COR    = {'1st Year', '2nd Year', '3rd Year', '4th Year'}
        NEEDS_GRADES = {'2nd Year', '3rd Year', '4th Year'}

        cor_cloudinary_id    = None
        grades_cloudinary_id = None

        if year_level in NEEDS_COR:
            cor_file = request.files.get('cor_file')
            if not cor_file or not cor_file.filename:
                flash('Certificate of Registration (COR) is required.', 'error')
                return render_template('auth/register.html')

            cor_ext = cor_file.filename.rsplit('.', 1)[-1].lower() if '.' in cor_file.filename else ''

            # PDF only — images allowed anyone to register with random photos.
            # Official LSPU portal COR/grades are downloadable as PDF.
            if cor_ext != 'pdf':
                flash('Your COR must be a PDF file. Download the official COR PDF '
                      'from the LSPU student portal and upload it here.', 'error')
                return render_template('auth/register.html')

            # Server-side 5MB limit (matches what the form promises)
            cor_file.seek(0, os.SEEK_END)
            cor_size = cor_file.tell()
            cor_file.seek(0)
            if cor_size > 5 * 1024 * 1024:
                flash(f'Your COR is {cor_size / (1024*1024):.1f}MB — the maximum size is 5MB. '
                      f'Please upload a smaller PDF.', 'error')
                return render_template('auth/register.html')

            cor_path, cor_cloudinary_id = _save_registration_file(cor_file, student_id, 'cor')
            if not cor_path:
                flash('COR file could not be uploaded to cloud storage. Please try again.', 'error')
                return render_template('auth/register.html')

        if year_level in NEEDS_GRADES:
            grades_file = request.files.get('grades_file')
            if not grades_file or not grades_file.filename:
                flash('Copy of Grades is required for 2nd year and above.', 'error')
                return render_template('auth/register.html')

            grades_ext = grades_file.filename.rsplit('.', 1)[-1].lower() if '.' in grades_file.filename else ''

            # PDF only — same rule as COR
            if grades_ext != 'pdf':
                flash('Your Copy of Grades must be a PDF file. Download the official '
                      'grades PDF from the LSPU student portal and upload it here.', 'error')
                return render_template('auth/register.html')

            # Server-side 5MB limit (matches what the form promises)
            grades_file.seek(0, os.SEEK_END)
            grades_size = grades_file.tell()
            grades_file.seek(0)
            if grades_size > 5 * 1024 * 1024:
                flash(f'Your Copy of Grades is {grades_size / (1024*1024):.1f}MB — the maximum '
                      f'size is 5MB. Please upload a smaller PDF.', 'error')
                return render_template('auth/register.html')

            grades_path, grades_cloudinary_id = _save_registration_file(grades_file, student_id, 'grades')
            if not grades_path:
                flash('Grades file could not be uploaded to cloud storage. Please try again.', 'error')
                return render_template('auth/register.html')

        # ── Document verification — INLINE GATE (before account creation) ─────
        # The uploaded PDF is read and its contents (Student ID, name, course) are
        # matched against the form. Mismatched or random PDFs are REJECTED here —
        # they can never create an account. This replaces the old background-OCR
        # approach that only flagged impostors after the account already existed.

        # Read the saved files back for verification (local path OR Cloudinary URL)
        from app.services.storage_service import get_file_bytes as _get_bytes

        cor_b    = _get_bytes(cor_path, cor_cloudinary_id)
        grades_b = _get_bytes(grades_path, grades_cloudinary_id)

        verification = None
        if cor_b:
            import concurrent.futures
            from app.services.ocr_service import verify_documents

            def _run_verification():
                return verify_documents(
                    form_student_id=student_id,
                    form_first_name=first_name,
                    form_last_name=last_name,
                    form_middle_name=middle_name,
                    cor_bytes=cor_b,
                    cor_ext='pdf',
                    grades_bytes=grades_b,
                    grades_ext='pdf' if grades_b else None,
                    form_course=course,
                )

            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    future = ex.submit(_run_verification)
                    try:
                        verification = future.result(timeout=60)
                    except concurrent.futures.TimeoutError:
                        verification = None
            except Exception as verify_err:
                import logging as _l
                _l.getLogger(__name__).warning(f'Registration verification error: {verify_err}')
                verification = None

        # Verification unavailable (timeout/service error) — fail closed:
        # an unverified document can NOT create an account. Clean up uploads.
        if verification is None:
            from app.services.storage_service import delete_file as _delete_file
            try:
                if cor_cloudinary_id or (cor_path and os.path.exists(cor_path)):
                    _delete_file(public_id=cor_cloudinary_id, file_path=None if cor_cloudinary_id else cor_path)
                if grades_cloudinary_id or (grades_path and os.path.exists(grades_path)):
                    _delete_file(public_id=grades_cloudinary_id, file_path=None if grades_cloudinary_id else grades_path)
            except Exception:
                pass
            flash('Document verification is temporarily unavailable. '
                  'Please try again in a few minutes.', 'error')
            return render_template('auth/register.html',
                                   form_data=request.form, ocr_errors=None)

        # ── Verification FAILED — block registration, show exact reasons ──────
        if not verification.get('passed'):
            from app.services.storage_service import delete_file as _delete_file
            try:
                if cor_cloudinary_id or (cor_path and os.path.exists(cor_path)):
                    _delete_file(public_id=cor_cloudinary_id, file_path=None if cor_cloudinary_id else cor_path)
                if grades_cloudinary_id or (grades_path and os.path.exists(grades_path)):
                    _delete_file(public_id=grades_cloudinary_id, file_path=None if grades_cloudinary_id else grades_path)
            except Exception:
                pass
            return render_template('auth/register.html',
                                   form_data=request.form,
                                   ocr_errors=verification.get('errors', []))

        auto_gwa = verification.get('gwa')

        # Units enrolled — pulled from the grades PDF (verification already read it).
        # GWA and units come from the same document the office needs anyway.
        auto_units = None
        grades_data = verification.get('grades_data') or {}
        if grades_data.get('units_enrolled'):
            try:
                auto_units = int(grades_data['units_enrolled'])
            except (ValueError, TypeError):
                auto_units = None

        # ── Generate and send OTP ─────────────────────────────────────────────
        otp = _generate_otp()
        full_name = f"{first_name.title()} {last_name.title()}"
        _send_otp_email(email, full_name, otp)

        # ── Store pending registration in session ─────────────────────────────
        session['pending_registration'] = {
            'first_name':           first_name.title(),
            'last_name':            last_name.title(),
            'middle_name':          middle_name.title() if middle_name else None,
            'email':                email,
            'student_id':           student_id,
            'phone':                phone,
            'gender':               gender,
            'birthday':             birthday_date.isoformat() if birthday_date else None,
            'town':                 town,
            'province':             province,
            'course':               course,
            'year_level':           year_level,
            'cor_path':             cor_path,
            'grades_path':          grades_path,
            'cor_cloudinary_id':    cor_cloudinary_id,
            'grades_cloudinary_id': grades_cloudinary_id,
            'auto_gwa':             auto_gwa,
            'auto_units':           auto_units,
            'otp':                  otp,
            'otp_expires':          (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(),
            'attempts':             0,
        }

        flash(f'A 6-digit verification code has been sent to <strong>{email}</strong>. '
              f'Please check your inbox.', 'info')
        return redirect(url_for('auth.verify_otp'))

    return render_template('auth/register.html')


# ── OTP Verification ──────────────────────────────────────────────────────────

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """
    Step 2: Student enters the 6-digit OTP.
    On success: account is created and credentials are emailed.
    """
    pending = session.get('pending_registration')

    if not pending:
        flash('No pending registration found. Please register again.', 'error')
        return redirect(url_for('auth.register'))

    # Check expiry
    expires = datetime.fromisoformat(pending['otp_expires'])
    if datetime.utcnow() > expires:
        session.pop('pending_registration', None)
        flash('Your verification code has expired. Please register again.', 'error')
        return redirect(url_for('auth.register'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip().replace(' ', '')

        # Increment attempt counter
        pending['attempts'] = pending.get('attempts', 0) + 1
        session['pending_registration'] = pending   # save updated attempts

        # Too many attempts
        if pending['attempts'] > 5:
            session.pop('pending_registration', None)
            flash('Too many incorrect attempts. Please register again.', 'error')
            return redirect(url_for('auth.register'))

        if entered_otp != pending['otp']:
            remaining = 5 - pending['attempts']
            flash(f'Incorrect verification code. {remaining} attempt(s) remaining.', 'error')
            return render_template('auth/verify_otp.html',
                                   email=pending['email'],
                                   expires=expires)

        # ── OTP correct — create the account ─────────────────────────────────
        try:
            temp_password = _generate_password(10)
            new_user = User(
                username=pending['student_id'],
                email=pending['email'],
                first_name=pending['first_name'],
                last_name=pending['last_name'],
                middle_name=pending.get('middle_name'),
                phone_number=pending['phone'],
                gender=pending.get('gender'),
                date_of_birth=datetime.strptime(pending['birthday'], '%Y-%m-%d').date()
                              if pending.get('birthday') else None,
                town=pending.get('town'),
                province=pending.get('province'),
                student_id=pending['student_id'],
                course=pending['course'],
                year_level=pending['year_level'],
                gwa=pending.get('auto_gwa'),       # extracted from grades PDF during verification
                units_enrolled=pending.get('auto_units'),   # extracted from grades PDF
                user_type='student',
                is_active=True,
                is_verified=True,
                ocr_verified=True,                 # inline gate already passed at registration
                ocr_result=None,
                cor_file_path=pending.get('cor_path'),
                grades_file_path=pending.get('grades_path'),
                cor_cloudinary_id=pending.get('cor_cloudinary_id'),
                grades_cloudinary_id=pending.get('grades_cloudinary_id'),
            )
            new_user.set_password(temp_password)
            db.session.add(new_user)
            db.session.flush()   # get new_user.id before adding documents

            # ── Auto-add registration files to Documents ──────────────────────
            try:
                from app.models.document import Document
                import os

                def _register_doc(file_path, label):
                    if not file_path or not os.path.exists(file_path):
                        return
                    ext            = file_path.rsplit('.', 1)[-1].lower()
                    stored_name    = os.path.basename(file_path)
                    size           = os.path.getsize(file_path)
                    doc = Document(
                        user_id=new_user.id,
                        original_filename=stored_name,
                        stored_filename=stored_name,
                        file_path=file_path,
                        file_size=size,
                        category='registration',
                        file_type=ext,
                        description=label,
                        is_verified=True,   # OCR already passed — auto-verified
                    )
                    db.session.add(doc)

                _register_doc(pending.get('cor_path'),    'Certificate of Registration (COR)')
                _register_doc(pending.get('grades_path'), 'Copy of Grades')
            except Exception as doc_err:
                pass   # non-critical — account still created

            db.session.commit()

            # Clear pending data
            session.pop('pending_registration', None)

            # Send credentials
            _send_credentials_email(new_user, temp_password)

            # NOTE: Document verification already ran INLINE during registration
            # (before the OTP was even sent) — mismatched/random PDFs were rejected
            # there. Nothing left to check in the background.

            # Audit log — registration
            try:
                from app.services.audit_service import log_action
                log_action('auth.register',
                           f'New student account created: {new_user.username} ({new_user.email}).',
                           category='auth', target_type='user', target_id=new_user.id,
                           user_id=new_user.id, user_name=new_user.username, user_role='student')
            except Exception:
                pass

            flash(
                f'Email verified! Your account has been created and your login credentials '
                f'have been sent to <strong>{new_user.email}</strong>.',
                'success'
            )
            return redirect(url_for('auth.login'))

        except Exception as e:
            db.session.rollback()
            flash('Account creation failed. Please try again.', 'error')
            return redirect(url_for('auth.register'))

    return render_template('auth/verify_otp.html',
                           email=pending['email'],
                           expires=expires)


@auth_bp.route('/verify-otp/resend', methods=['POST'])
@limiter.limit('10 per 15 minutes')
def resend_otp():
    """Resend a fresh OTP to the pending email."""
    pending = session.get('pending_registration')
    if not pending:
        flash('No pending registration. Please register again.', 'error')
        return redirect(url_for('auth.register'))

    new_otp = _generate_otp()
    pending['otp']         = new_otp
    pending['otp_expires'] = (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()
    pending['attempts']    = 0
    session['pending_registration'] = pending

    full_name = f"{pending['first_name']} {pending['last_name']}"
    _send_otp_email(pending['email'], full_name, new_otp)

    flash(f'A new verification code has been sent to <strong>{pending["email"]}</strong>.', 'info')
    return redirect(url_for('auth.verify_otp'))


# ── Forgot Password ───────────────────────────────────────────────────────────

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Step 1: User must provide BOTH their Student ID and registered email.
    Both must match the same account in the database before a reset link is sent.
    """
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        email      = request.form.get('email', '').strip().lower()

        if not student_id or not email:
            flash('Please enter both your Student ID and email address.', 'error')
            return render_template('auth/forgot_password.html',
                                   student_id=student_id, email=email)

        # Validate Student ID format
        if not re.match(r'^\d{4}-\d{4}$', student_id):
            flash('Student ID must follow the format XXXX-XXXX (e.g. 2024-1234).', 'error')
            return render_template('auth/forgot_password.html',
                                   student_id=student_id, email=email)

        # Look up by student_id AND email — both must match the same account
        user = User.query.filter_by(student_id=student_id, email=email).first()

        if not user or not user.is_active:
            flash(
                'No account found matching that Student ID and email address. '
                'Please check your details and try again.',
                'error'
            )
            return render_template('auth/forgot_password.html',
                                   student_id=student_id, email=email)

        # Match confirmed — generate and send reset link
        token = secrets.token_urlsafe(48)
        user.password_reset_token   = token
        user.password_reset_expires = datetime.utcnow() + timedelta(minutes=30)
        db.session.commit()

        reset_url = url_for('auth.reset_password', token=token, _external=True)
        _send_reset_email(user.email, user.get_full_name(), reset_url)

        flash(
            f'A password reset link has been sent to <strong>{email}</strong>. '
            'It expires in 30 minutes. Please check your inbox (and spam folder).',
            'success'
        )
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', student_id='', email='')


def _send_reset_email(email, full_name, reset_url):
    """Send the password reset email."""
    try:
        from app.services.notification_service import notification_service
        subject = "LSPU ScholarHub — Password Reset Request"
        message = f"""
        <h2>Password Reset Request 🔑</h2>
        <p>Dear <strong>{full_name}</strong>,</p>
        <p>We received a request to reset the password for your LSPU ScholarHub account.</p>
        <p>Click the button below to set a new password. This link is valid for
           <strong>30 minutes</strong>.</p>
        <div style="text-align:center;margin:32px 0;">
          <a href="{reset_url}"
             style="display:inline-block;background:#1a3a6b;color:#fff;
                    font-size:1rem;font-weight:600;padding:14px 36px;
                    border-radius:8px;text-decoration:none;">
            Reset My Password
          </a>
        </div>
        <p style="word-break:break-all;font-size:.85rem;color:#555;">
          Or copy this link into your browser:<br>{reset_url}
        </p>
        <p style="color:#dc3545;">
          If you did not request a password reset, please ignore this email.
          Your password will remain unchanged.
        </p>
        <p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>
        """
        notification_service.send_email(email, subject, message)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'Could not send reset email: {e}')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Step 2: User sets a new password using the token from the email."""
    user = User.query.filter_by(password_reset_token=token).first()

    if not user or not user.password_reset_expires:
        flash('This password reset link is invalid or has already been used.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if datetime.utcnow() > user.password_reset_expires:
        # Expire the token
        user.password_reset_token   = None
        user.password_reset_expires = None
        db.session.commit()
        flash('This password reset link has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password     = request.form.get('new_password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not new_password or not confirm_password:
            flash('Please fill in both password fields.', 'error')
            return render_template('auth/reset_password.html', token=token)

        if len(new_password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('auth/reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Passwords do not match. Please try again.', 'error')
            return render_template('auth/reset_password.html', token=token)

        # Set new password and clear the token
        user.set_password(new_password)
        user.password_reset_token   = None
        user.password_reset_expires = None
        db.session.commit()

        from app.services.audit_service import log_action
        log_action('auth.password_reset',
                   f'Password successfully reset via email link for '
                   f'{user.get_full_name()} ({user.username}, {user.user_type}). '
                   f'Reset token was consumed and cleared.',
                   category='auth', target_type='user', target_id=user.id,
                   user_id=user.id, user_name=user.username, user_role=user.user_type)

        flash('Your password has been reset successfully. You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ── Logout ────────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    from app.services.audit_service import log_action
    uid   = session.get('user_id')
    uname = session.get('username', '?')
    urole = session.get('user_type', '?')
    log_action('auth.logout',
               f'{uname} ({urole}) logged out of the system.',
               category='auth', target_type='user', target_id=uid,
               user_id=uid, user_name=uname, user_role=urole)
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('main.index'))


# ── Profile redirect ──────────────────────────────────────────────────────────

@auth_bp.route('/profile')
def profile():
    if 'user_id' not in session:
        flash('Please log in to view your profile.', 'error')
        return redirect(url_for('auth.login'))

    role = session.get('user_type')
    if role == 'admin':
        return redirect(url_for('admin.profile'))
    elif role == 'staff':
        return redirect(url_for('staff.profile'))
    else:
        return redirect(url_for('student.profile'))
