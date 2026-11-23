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
SEND_FLAG = '--send-sms'

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


def mask_phone(number):
    """Show only the last four digits of a phone number."""
    digits = ''.join(ch for ch in (number or '') if ch.isdigit())
    return f'***{digits[-4:]}' if len(digits) >= 4 else '***'


def require_sms_confirmation():
    """Return TEST_SMS_NUMBER only when an explicit send was requested.

    SMS test scripts are one command away from texting a real person, so they
    send nothing unless BOTH ``--send-sms`` and a valid TEST_SMS_NUMBER are
    present. The recipient is never hardcoded in the repository.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv()  # local .env; real environment variables win
    except ImportError:
        pass

    number = (os.environ.get('TEST_SMS_NUMBER') or '').strip()
    digits = ''.join(ch for ch in number if ch.isdigit())

    if SEND_FLAG not in sys.argv:
        print('[guard] No SMS was sent: this script sends a real text message.')
        print(f'[guard] Re-run with {SEND_FLAG} and '
              'TEST_SMS_NUMBER=+639XXXXXXXXX to send exactly one test SMS.')
        sys.exit(1)

    if len(digits) < 7:
        print('[guard] Refusing to send: TEST_SMS_NUMBER is missing or too short.')
        print('[guard] Set it to the full recipient number, e.g. +639171234567.')
        sys.exit(1)

    print(f'[guard] Sending ONE test SMS to {mask_phone(number)} '
          f'because {SEND_FLAG} was passed.')
    return number
