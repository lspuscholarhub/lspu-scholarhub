import os
from dotenv import load_dotenv

load_dotenv()


def _fix_db_url(url: str) -> str:
    """Railway provides DATABASE_URL with mysql:// prefix — PyMySQL needs mysql+pymysql://"""
    if url and url.startswith('mysql://'):
        return url.replace('mysql://', 'mysql+pymysql://', 1)
    return url


class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = _fix_db_url(
        os.environ.get('DATABASE_URL') or 'mysql+pymysql://root:@localhost/lspu_scholarhub'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,       # recycle connections before MySQL closes them (5 min default)
        'pool_pre_ping': True,     # verify connection is alive before using it
    }
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or 'app/static/uploads'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16777216))  # 16MB

    # Email
    MAIL_SERVER   = os.environ.get('MAIL_SERVER')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = os.environ.get('MAIL_USE_TLS', 'True').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')

    # JWT
    JWT_SECRET_KEY             = os.environ.get('JWT_SECRET_KEY') or 'jwt-secret-string'
    JWT_ACCESS_TOKEN_EXPIRES   = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))

    # Chatbot
    CHATBOT_ENABLED = os.environ.get('CHATBOT_ENABLED', 'true').lower() in ['true', 'on', '1']
    CHATBOT_TYPE    = os.environ.get('CHATBOT_TYPE', 'gemini')

    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE  = os.environ.get('LOG_FILE', 'logs/app.log')


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    # CSRF: disable SSL strict so it works behind Railway's HTTPS proxy
    WTF_CSRF_SSL_STRICT = False
    WTF_CSRF_TIME_LIMIT = None   # no expiry on CSRF tokens
    PREFERRED_URL_SCHEME = 'https'
    # Session cookies — expire when browser is closed
    SESSION_COOKIE_SECURE   = False   # Railway terminates TLS at the proxy; the app
                                      # receives plain HTTP internally, so Secure flag
                                      # would break session cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600   # 1 hour if session IS permanent


config = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
