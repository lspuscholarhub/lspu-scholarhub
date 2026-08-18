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

    # Bind extensions to this app instance
    db.init_app(app)
    migrate.init_app(app, db)   # enables `flask db init/migrate/upgrade`
    mail.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)          # CSRF protection on all POST/PUT/PATCH/DELETE forms

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

    # ── Template globals ──────────────────────────────────────────────────
    from datetime import datetime as _dt

    @app.context_processor
    def inject_globals():
        from flask import session as _session
        return {
            'now': _dt.utcnow(),
            'session': _session,
            'ApplicationStatus': None,   # imported per-template via model
        }

    return app
