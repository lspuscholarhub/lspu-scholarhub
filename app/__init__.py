from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from flask_wtf.csrf import CSRFProtect
from config.config import config
import os

# Initialize extensions (not yet bound to an app)
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()
jwt = JWTManager()
csrf = CSRFProtect()


def create_app(config_name=None):
    """Application factory — creates and configures the Flask app."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Trust Railway's reverse proxy (fixes HTTPS detection and CSRF)
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Bind extensions to this app instance
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)

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

    # ── Template globals ──────────────────────────────────────────────────
    from datetime import datetime as _dt

    # Shared constants
    LSPU_COURSES = sorted([
        'Bachelor of Science in Information Technology',
        'Bachelor of Science in Computer Science',
        'Bachelor of Science in Civil Engineering',
        'Bachelor of Science in Electrical Engineering',
        'Bachelor of Science in Mechanical Engineering',
        'Bachelor of Science in Chemistry',
        'Bachelor of Science in Mathematics',
        'Bachelor of Science in Nursing',
        'Bachelor of Science in Accountancy',
        'Bachelor of Science in Business Administration Major In Financial Management',
        'Bachelor of Elementary Education',
        'Bachelor of Secondary Education Major In English',
        'Bachelor of Science in Hospitality Management',
        'Bachelor of Science in Psychology',
    ])

    @app.context_processor
    def inject_globals():
        from flask import session as _session
        from app.utils.gwa_utils import get_gwa_label, get_gwa_badge_class, GWA_THRESHOLD
        return {
            'now': _dt.utcnow(),
            'session': _session,
            'ApplicationStatus': None,   # imported per-template via model
            'LSPU_COURSES': LSPU_COURSES,
            'get_gwa_label': get_gwa_label,
            'get_gwa_badge_class': get_gwa_badge_class,
            'GWA_THRESHOLD': GWA_THRESHOLD,
        }

    return app
