from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config.config import config
import os

# Initialize extensions (not yet bound to an app)
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
jwt = JWTManager()
csrf = CSRFProtect()
# Storage backend is env-configurable: memory:// works for small deployments;
# set LIMIT_STORAGE_URI to a redis:// URL when running multiple instances.
limiter = Limiter(key_func=get_remote_address,
                  storage_uri=os.environ.get('LIMIT_STORAGE_URI', 'memory://'))


def create_app(config_name=None):
    """Application factory — creates and configures the Flask app."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Cap upload size: protects workers from memory/time blowups under load.
    # Largest legitimate file is a Copy of Grades PDF — 10MB is generous.
    app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

    # Harden the DB connection pool for cloud MySQL (Railway).
    # MUST be set before db.init_app():
    # - pool_pre_ping: drop dead connections instead of erroring on them
    # - pool_recycle:  refresh connections before MySQL's wait_timeout kills them
    app.config.setdefault('SQLALCHEMY_ENGINE_OPTIONS', {
        'pool_pre_ping': True,
        'pool_recycle': 280,   # below Railway MySQL's default wait_timeout
        'pool_size': 5,
        'max_overflow': 10,
    })

    # Friendly handling when an upload exceeds the size cap
    @app.errorhandler(413)
    def too_large(e):
        from flask import jsonify, request as _req, flash as _flash
        from flask import redirect as _redir
        if _req.is_json or _req.path.startswith('/chatbot'):
            return jsonify({'error': 'File too large. Maximum size is 10MB.'}), 413
        _flash('That file is too large — the maximum size is 10MB. '
               'Please compress it or upload a smaller copy.', 'error')
        return _redir(_req.referrer or '/')

    # Trust Railway's reverse proxy (fixes HTTPS detection and CSRF)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Bind extensions to this app instance
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Last-resort 500 handler: log the traceback, show a friendly page,
    # and keep the worker alive instead of surfacing a bare error.
    @app.errorhandler(500)
    def internal_error(e):
        import logging
        from flask import jsonify, request as _req, flash as _flash
        from flask import render_template as _render, redirect as _redir
        logging.getLogger(__name__).exception('Unhandled 500 on %s', _req.path)
        db.session.rollback()
        if _req.path.startswith('/chatbot') or _req.path.startswith('/api') or _req.is_json:
            return jsonify({'error': 'Something went wrong on our side. Please try again.'}), 500
        _flash('Something went wrong on our side. Please try again — if it keeps '
               'happening, contact the scholarship office.', 'error')
        try:
            return _redir(_req.referrer or '/'), 302
        except Exception:
            return _render('errors/500.html'), 500

    # Friendly handling when a rate limit is hit
    @app.errorhandler(429)
    def ratelimit_handler(e):
        from flask import jsonify, request as _req, flash as _flash
        from flask import redirect as _redir
        if _req.path.startswith('/chatbot') or _req.is_json:
            return jsonify({
                'error':    'Too many requests. Please wait a moment and try again.',
                'response': 'You are sending messages too quickly — please wait a moment and try again.',
                'source':   'ratelimit',
            }), 429
        _flash('Too many attempts. Please wait a few minutes and try again.', 'warning')
        return _redir(_req.referrer or '/auth/login')

    # Register blueprints
    from app.views.main import main_bp
    from app.views.auth import auth_bp
    from app.views.scholarship import scholarship_bp
    from app.views.admin import admin_bp
    from app.views.staff import staff_bp
    from app.views.student import student_bp
    from app.views.chatbot import chatbot_bp
    from app.views.api import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(scholarship_bp, url_prefix='/scholarship')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(staff_bp, url_prefix='/staff')
    app.register_blueprint(student_bp, url_prefix='/student')
    app.register_blueprint(chatbot_bp, url_prefix='/chatbot')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Exempt the API blueprint — it uses JWT bearer tokens, not session cookies
    csrf.exempt(api_bp)

    # Ensure required directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs('logs', exist_ok=True)

    # ── Auto-migrate: add missing columns ─────────────────────────────────
    # db.create_all() only creates new tables, not new columns.
    # This safely adds columns that were added to models after initial deploy.
    with app.app_context():
        import logging
        _migrate_log = logging.getLogger('migrate')
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                # Check if column exists using raw SQL (works with all DB backends)
                result = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() "
                    "AND table_name = 'scholarships' "
                    "AND column_name = 'custom_form_fields'"
                ))
                exists = result.scalar() > 0
                if not exists:
                    conn.execute(text(
                        'ALTER TABLE scholarships ADD COLUMN custom_form_fields JSON NULL'
                    ))
                    conn.commit()
                    _migrate_log.info('SUCCESS: Added custom_form_fields column to scholarships.')
                else:
                    _migrate_log.info('OK: custom_form_fields column already exists.')
        except Exception as e:
            _migrate_log.error(f'MIGRATION FAILED: {e}')  # Log the actual error

    # Migration 2: M&E form deadline on academic periods
    with app.app_context():
        import logging
        _migrate_log = logging.getLogger('migrate')
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema = DATABASE() "
                    "AND table_name = 'academic_periods' "
                    "AND column_name = 'me_form_deadline'"
                ))
                exists = result.scalar() > 0
                if not exists:
                    conn.execute(text(
                        'ALTER TABLE academic_periods ADD COLUMN me_form_deadline DATE NULL'
                    ))
                    conn.commit()
                    _migrate_log.info('SUCCESS: Added me_form_deadline column to academic_periods.')
                else:
                    _migrate_log.info('OK: me_form_deadline column already exists.')
        except Exception as e:
            _migrate_log.error(f'MIGRATION FAILED (me_form_deadline): {e}')

    # Migration 3: student lifecycle status (active / graduated / dropped_out)
    with app.app_context():
        import logging
        _migrate_log = logging.getLogger('migrate')
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                for _col, _ddl in (
                    ('student_status',
                     "ALTER TABLE users ADD COLUMN student_status "
                     "VARCHAR(20) NOT NULL DEFAULT 'active'"),
                    ('status_date',
                     'ALTER TABLE users ADD COLUMN status_date DATE NULL'),
                ):
                    result = conn.execute(text(
                        "SELECT COUNT(*) FROM information_schema.columns "
                        "WHERE table_schema = DATABASE() "
                        "AND table_name = 'users' "
                        f"AND column_name = '{_col}'"
                    ))
                    if result.scalar() == 0:
                        conn.execute(text(_ddl))
                        conn.commit()
                        _migrate_log.info(f'SUCCESS: Added {_col} column to users.')
                    else:
                        _migrate_log.info(f'OK: {_col} column already exists.')
        except Exception as e:
            _migrate_log.error(f'MIGRATION FAILED (student_status): {e}')

    # ── Inactivity timeout ────────────────────────────────────────────────
    # Log out users who have been inactive for more than 30 minutes.
    # Checked on every request — if last_active is older than timeout, clear session.
    INACTIVITY_TIMEOUT = 30 * 60   # 30 minutes in seconds

    @app.before_request
    def check_session_timeout():
        from flask import session as _s, request as _req, redirect as _redir, url_for as _uf
        from datetime import datetime as _dt

        # Only check authenticated sessions
        if not _s.get('user_id'):
            return

        # Skip static files
        if _req.endpoint and _req.endpoint.startswith('static'):
            return

        now        = _dt.utcnow().timestamp()
        last_active = _s.get('last_active')

        if last_active and (now - last_active) > INACTIVITY_TIMEOUT:
            # Session expired — clear and redirect to login
            _s.clear()
            from flask import flash as _flash
            _flash('You have been logged out due to inactivity.', 'warning')
            return _redir(_uf('auth.login'))

        # Update last active timestamp on every request
        _s['last_active'] = now

    @app.before_request
    def enforce_password_change():
        """Force password change before any authenticated route is accessible."""
        from flask import session as _s, request as _req, redirect as _redir, url_for as _uf

        if not _s.get('user_id'):
            return

        # Skip the force-change-password page itself, logout, and static files
        allowed_endpoints = ('auth.force_change_password', 'auth.logout', 'static')
        if _req.endpoint in allowed_endpoints:
            return

        # Check if user must change password
        from app.models.user import User as _User
        from app import db as _db
        _user = _db.session.get(_User, _s.get('user_id'))
        if _user and _user.must_change_password:
            return _redir(_uf('auth.force_change_password'))

    # ── Template globals ──────────────────────────────────────────────────
    from datetime import datetime as _dt

    # Shared constants — the 41 official LSPU degree programs
    LSPU_COURSES = sorted([
        'Bachelor Elementary Education major in Generalist',
        'Bachelor of Secondary Education major in English',
        'Bachelor of Secondary Education major in Filipino',
        'Bachelor of Secondary Education major in Mathematics',
        'Bachelor of Secondary Education major in Social Studies',
        'Bachelor of Secondary Education major in Science',
        'Bachelor of Physical Education',
        'Bachelor of Technical-Vocational Teacher Education major in Computer Programming',
        'Bachelor of Technical-Vocational Teacher Education major in Food and Service Management',
        'Bachelor of Technical-Vocational Teacher Education major in Garments, Fashion and Design',
        'Bachelor of Technology and Livelihood Education major in Home Economics',
        'Bachelor of Technology and Livelihood Education major in Industrial Arts',
        'Bachelor of Technology and Livelihood Education major in Information and Communication Technology',
        'Bachelor of Arts in Broadcasting',
        'Bachelor of Science in Biology',
        'Bachelor of Science in Chemistry',
        'Bachelor of Science in Mathematics',
        'Bachelor of Science in Psychology',
        'Bachelor of Science in Nursing',
        'Bachelor of Science in Civil Engineering',
        'Bachelor of Science in Computer Engineering',
        'Bachelor of Science in Electrical Engineering',
        'Bachelor of Science in Electronics Engineering',
        'Bachelor of Science in Mechanical Engineering',
        'Bachelor of Science in Accountancy',
        'Bachelor of Science in Business Administration major in Financial Management',
        'Bachelor of Science in Business Administration major in Marketing Management',
        'Bachelor of Science in Entrepreneurship',
        'Bachelor of Science in Office Administration',
        'Bachelor of Public Administration',
        'Bachelor of Science in Hospitality Management',
        'Bachelor of Science in Tourism Management',
        'Bachelor of Science in Criminology',
        'Bachelor of Science in Computer Science',
        'Bachelor of Science in Information Technology',
        'Bachelor of Science in Industrial Technology major in Architectural Drafting Technology',
        'Bachelor of Science in Industrial Technology major in Automotive Technology',
        'Bachelor of Science in Industrial Technology major in Electrical Technology',
        'Bachelor of Science in Industrial Technology major in Electronics Technology',
        'Bachelor of Science in Industrial Technology major in Food Beverages Preparation and Service Management',
        'Bachelor of Science in Industrial Technology major in Heating, Ventilating, Air-Conditioning and Refrigeration',
    ])

    @app.context_processor
    def inject_globals():
        from flask import session as _session
        from app.utils.gwa_utils import get_gwa_label, get_gwa_badge_class, GWA_THRESHOLD

        # Real unread notification count for the navbar bell badge
        unread = 0
        has_approved_scholarship = False
        if _session.get('user_id') and _session.get('user_type') == 'student':
            try:
                from app.models.notification import Notification
                unread = Notification.query.filter_by(
                    user_id=_session['user_id'], is_read=False).count()
            except Exception:
                unread = 0
            try:
                from app.models import ScholarshipApplication
                from app.models.scholarship import ApplicationStatus as _AS
                has_approved_scholarship = ScholarshipApplication.query.filter_by(
                    applicant_id=_session['user_id'],
                    status=_AS.APPROVED).limit(1).count() > 0
            except Exception:
                has_approved_scholarship = False

        # Campus data for navbar
        all_campuses = []
        try:
            from app.models import Campus
            all_campuses = Campus.query.filter_by(is_active=True).order_by(Campus.id).all()
        except Exception:
            pass

        # Academic periods for navbar period switcher
        all_academic_periods = []
        try:
            from app.models.academic_period import AcademicPeriod
            all_academic_periods = AcademicPeriod.query.order_by(AcademicPeriod.id.desc()).all()
        except Exception:
            pass

        return {
            'now': _dt.utcnow(),
            'session': _session,
            'ApplicationStatus': None,   # imported per-template via model
            'LSPU_COURSES': LSPU_COURSES,
            'get_gwa_label': get_gwa_label,
            'get_gwa_badge_class': get_gwa_badge_class,
            'GWA_THRESHOLD': GWA_THRESHOLD,
            'unread_count': unread,
            'has_approved_scholarship': has_approved_scholarship,
            'all_campuses': all_campuses,
            'all_academic_periods': all_academic_periods,
        }

    return app
