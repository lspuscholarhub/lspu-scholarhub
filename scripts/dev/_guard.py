"""Production guard for the risky dev scripts.

These scripts seed demo accounts, reset the admin password or print password
hashes. Running them against the deployed database is almost always a mistake,
so they call ``require_confirmation()`` before they touch the database.

The guard treats a target as production-like when:

* FLASK_ENV is "production", or the process runs on Railway, or
* the database host is anything other than localhost/127.0.0.1/::1/.local.

For such a target the script exits unless ``--confirm-production`` is passed.
Local and scratch databases keep working without the flag.
"""

import os
import sys
from urllib.parse import urlparse

CONFIRM_FLAG = '--confirm-production'

_LOCAL_HOSTS = {'localhost', '127.0.0.1', '::1'}


def _database_host():
    """Return the database host without ever exposing credentials."""
    url = (os.environ.get('DATABASE_URL') or '').strip()
    if url.startswith('sqlite'):
        return 'localhost'
    if url:
        try:
            return (urlparse(url).hostname or '').lower()
        except ValueError:
            return ''
    return (os.environ.get('MYSQL_HOST')
            or os.environ.get('MYSQL_SERVER') or '').strip().lower()


def _is_production_like(host):
    if os.environ.get('FLASK_ENV', '').strip().lower() == 'production':
        return True
    if os.environ.get('RAILWAY_ENVIRONMENT'):
        return True
    if not host:
        return False
    return host not in _LOCAL_HOSTS and not host.endswith('.local')


def require_confirmation(action):
    """Exit unless the database is local or the confirmation flag was given."""
    try:
        from dotenv import load_dotenv
        load_dotenv()  # local .env; real environment variables win
    except ImportError:
        pass

    host = _database_host()
    if not _is_production_like(host):
        return

    if CONFIRM_FLAG in sys.argv:
        print(f'[guard] {action}: non-local database host "{host or "unknown"}" '
              f'allowed because {CONFIRM_FLAG} was passed.')
        return

    print(f'[guard] Refusing to {action} against a production-like database '
          f'(host: {host or "unknown"}).')
    print('[guard] This script can overwrite accounts or expose password hashes.')
    print(f'[guard] Re-run with {CONFIRM_FLAG} only if that is really intended.')
    sys.exit(1)
