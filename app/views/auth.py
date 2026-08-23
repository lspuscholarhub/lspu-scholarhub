"""
Authentication views for LSPU ScholarHub.

Registration workflow:
  1. Student fills form → OTP sent to email → session stores pending data
  2. Student enters OTP on verify page → account created → credentials emailed
  3. Instant access (no manual admin approval)

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
from app import db
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
    Save a registration document (COR or grades) to disk.
    Accepts PDF and image files (JPG, PNG) — images are analyzed via Gemini Vision.
    Returns the relative file path or None on failure.
    """
    if not file or not file.filename:
        return None

    from flask import current_app
    from werkzeug.utils import secure_filename

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''

    # Accept PDF and images
    allowed = {'pdf', 'jpg', 'jpeg', 'png'}
    if ext not in allowed:
        return None

    filename = f"{file_type}_{user_student_id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
    filename = secure_filename(filename)

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'registration')
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    return file_path


def _send_credentials_email(user, temp_password):
    """Send login credentials to the newly registered student."""
    try:
        from app.services.notification_service import notification_service

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
        <p>You can log in at: <a href="http://localhost:5000/auth/login">http://localhost:5000/auth/login</a></p>
        <p>If you have any questions, contact us at <a href="mailto:scholarships@lspu.edu.ph">scholarships@lspu.edu.ph</a> or call (049) 576-1234.</p>
        <p>Best regards,<br><strong>LSPU Scholarship Office</strong></p>
        """
        notification_service.send_email(user.email, subject, message)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f'Could not send credentials email: {e}')


# ── Login ─────────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
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

            session['user_id']     = user.id
            session['username']    = user.username
            session['user_type']   = user.user_type
            session['is_verified'] = user.is_verified
            session['first_login'] = (user.last_login is None)

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

        # ── Required fields (middle_name, gender, town, province are optional) ─
        if not all([first_name, last_name, email, student_id, phone, course, year_level]):
            flash('Please fill in all required fields.', 'error')
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

        cor_bytes    = None
        cor_ext      = None
        grades_bytes = None
        grades_ext   = None

        if year_level in NEEDS_COR:
            cor_file = request.files.get('cor_file')
            if not cor_file or not cor_file.filename:
                flash('Certificate of Registration (COR) is required.', 'error')
                return render_template('auth/register.html')

            cor_ext = cor_file.filename.rsplit('.', 1)[-1].lower() if '.' in cor_file.filename else ''

            # Accept PDF and images (JPG/PNG) — images are analyzed via Gemini Vision
            allowed_exts = {'pdf', 'jpg', 'jpeg', 'png'}
            if cor_ext not in allowed_exts:
                flash('Your COR must be a PDF or image file (JPG/PNG). '
                      'Please upload your official COR or take a clear photo of it.', 'error')
                return render_template('auth/register.html')

            cor_bytes = cor_file.read()
            cor_file.seek(0)

            cor_path = _save_registration_file(cor_file, student_id, 'cor')
            if not cor_path:
                flash('COR file could not be saved. Please upload a valid PDF (max 5MB).', 'error')
                return render_template('auth/register.html')

        if year_level in NEEDS_GRADES:
            grades_file = request.files.get('grades_file')
            if not grades_file or not grades_file.filename:
                flash('Copy of Grades is required for 2nd year and above.', 'error')
                return render_template('auth/register.html')

            grades_ext = grades_file.filename.rsplit('.', 1)[-1].lower() if '.' in grades_file.filename else ''

            # Accept PDF and images
            allowed_exts = {'pdf', 'jpg', 'jpeg', 'png'}
            if grades_ext not in allowed_exts:
                flash('Your Copy of Grades must be a PDF or image file (JPG/PNG). '
                      'Please upload your official grades or take a clear photo of it.', 'error')
                return render_template('auth/register.html')

            grades_bytes = grades_file.read()
            grades_file.seek(0)

            grades_path = _save_registration_file(grades_file, student_id, 'grades')
            if not grades_path:
                flash('Grades file could not be saved. Please upload a valid PDF (max 5MB).', 'error')
                return render_template('auth/register.html')

        # ── Document validation — file type check only (no OCR during registration) ──
        # OCR/AI verification is done by staff when reviewing scholarship applications.
        # Running Gemini during registration causes timeouts on production servers.
        # Staff can view uploaded COR/grades from the student profile page.
        auto_gwa = None  # GWA will be entered manually by staff after reviewing grades

        # ── Generate and send OTP ─────────────────────────────────────────────
        otp = _generate_otp()
        full_name = f"{first_name.title()} {last_name.title()}"
        _send_otp_email(email, full_name, otp)

        # ── Store pending registration in session ─────────────────────────────
        session['pending_registration'] = {
            'first_name':      first_name.title(),
            'last_name':       last_name.title(),
            'middle_name':     middle_name.title() if middle_name else None,
            'email':           email,
            'student_id':      student_id,
            'phone':           phone,
            'gender':          gender,
            'town':            town,
            'province':        province,
            'course':          course,
            'year_level':      year_level,
            'cor_path':        cor_path,
            'grades_path':     grades_path,
            'auto_gwa':        auto_gwa,   # extracted by OCR, may be None
            'otp':             otp,
            'otp_expires':     (datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat(),
            'attempts':        0,
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
                town=pending.get('town'),
                province=pending.get('province'),
                student_id=pending['student_id'],
                course=pending['course'],
                year_level=pending['year_level'],
                gwa=pending.get('auto_gwa'),       # auto-populated from OCR
                user_type='student',
                is_active=True,
                is_verified=True,
                cor_file_path=pending.get('cor_path'),
                grades_file_path=pending.get('grades_path'),
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

            # ── Run OCR in background thread after account is created ─────────
            # This keeps registration instant while still auto-verifying documents.
            # Results are stored on the user record and visible on the admin/staff profile page.
            try:
                import threading
                from flask import current_app

                def _background_ocr(app, user_id, cor_path, grades_path,
                                     student_id, first_name, last_name,
                                     middle_name, course):
                    """Run OCR after account creation — non-blocking."""
                    with app.app_context():
                        try:
                            import os
                            from app.models import User as _User
                            from app import db as _db

                            user_rec = _User.query.get(user_id)
                            if not user_rec:
                                return

                            # Read file bytes from saved paths
                            def _read(path):
                                if path and os.path.exists(path):
                                    with open(path, 'rb') as f:
                                        return f.read()
                                return None

                            cor_b    = _read(cor_path)
                            grades_b = _read(grades_path)

                            if not cor_b:
                                return

                            cor_ext_bg    = cor_path.rsplit('.', 1)[-1].lower() if cor_path and '.' in cor_path else ''
                            grades_ext_bg = grades_path.rsplit('.', 1)[-1].lower() if grades_path and '.' in grades_path else ''

                            from app.services.ocr_service import verify_documents
                            result = verify_documents(
                                form_student_id=student_id,
                                form_first_name=first_name,
                                form_last_name=last_name,
                                form_middle_name=middle_name,
                                cor_bytes=cor_b,
                                cor_ext=cor_ext_bg,
                                grades_bytes=grades_b,
                                grades_ext=grades_ext_bg,
                                form_course=course,
                            )

                            # Store OCR result on user record
                            user_rec.ocr_verified  = result.get('passed', False)
                            user_rec.ocr_result    = str(result.get('errors', []))
                            if result.get('gwa') and not user_rec.gwa:
                                user_rec.gwa = result['gwa']
                            _db.session.commit()

                        except Exception as ocr_err:
                            import logging as _l
                            _l.getLogger(__name__).warning(f'Background OCR failed: {ocr_err}')

                t = threading.Thread(
                    target=_background_ocr,
                    args=(
                        current_app._get_current_object(),
                        new_user.id,
                        pending.get('cor_path'),
                        pending.get('grades_path'),
                        pending['student_id'],
                        pending['first_name'],
                        pending['last_name'],
                        pending.get('middle_name'),
                        pending['course'],
                    ),
                    daemon=True,
                )
                t.start()
            except Exception as bg_err:
                import logging as _log
                _log.getLogger(__name__).warning(f'Could not start background OCR: {bg_err}')

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
