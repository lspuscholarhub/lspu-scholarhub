import compileall, sys, glob, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ok = compileall.compile_dir('app', quiet=1, force=True)
print('compile:', 'OK' if ok else 'FAIL')

from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
bad = []
files = glob.glob('app/templates/**/*.html', recursive=True)
for f in files:
    rel = os.path.relpath(f, 'app/templates').replace(os.sep, '/')
    try:
        env.parse(open(f, encoding='utf-8').read())
    except Exception as e:
        bad.append((rel, str(e)))
print('templates:', len(files), 'parsed,', len(bad), 'errors')
for b in bad:
    print('  ERR', b)

# Boot the app against the live DB
os.environ.setdefault('DATABASE_URL',
    'mysql://root:REDACTED_DB_PASSWORD@altaria.proxy.rlwy.net:56613/railway')
try:
    from app import create_app, db
    app = create_app()
    with app.app_context():
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        from app.models import User, ScholarshipApplication
        print('boot: OK — DB connected, users=', User.query.count())
    print('routes:', len(list(app.url_map.iter_rules())))
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
