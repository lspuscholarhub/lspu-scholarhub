import os
from app import create_app, db
from app.models import User, Scholarship, ScholarshipApplication, Notification
from app.models.document import Document

# Use production config on Railway (RAILWAY_ENVIRONMENT is set automatically)
env = os.environ.get('FLASK_ENV', 'development')
if os.environ.get('RAILWAY_ENVIRONMENT') or os.environ.get('RAILWAY_STATIC_URL'):
    env = 'production'

app = create_app(env)

@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Scholarship': Scholarship,
        'ScholarshipApplication': ScholarshipApplication,
        'Notification': Notification,
        'Document': Document,
    }

# Create tables on startup
try:
    with app.app_context():
        db.create_all()
        print("✓ Database tables ready")
except Exception as e:
    print(f"✗ Database connection failed: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=(env == 'development'), host='0.0.0.0', port=port)
