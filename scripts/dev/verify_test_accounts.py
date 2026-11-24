#!/usr/bin/env python3
"""Check the recorded test passwords against the live password hashes.

_local_private/test_accounts.md is the only record of the test accounts'
passwords, and it drifted once: two student entries kept values from an earlier
rotation while those accounts had been restored to their own password, so the
sheet looked authoritative and was wrong. Run this after editing the sheet and
before handing the project over:

    python scripts/dev/verify_test_accounts.py --confirm-production

Exits 0 when every recorded password still authenticates the account it is
listed under, 1 when an entry has drifted or its account is gone. Passwords are
never printed.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _guard import CONFIRM_FLAG, require_confirmation  # noqa: E402
from rotate_known_passwords import BLOCK_END, BLOCK_START, mask_email  # noqa: E402

DEFAULT_SHEET = Path('_local_private/test_accounts.md')


def read_credentials(path):
    """The block entries as {id: (email, password)}; notes around it are ignored."""
    text = Path(path).read_text(encoding='utf-8')
    try:
        start = text.index(BLOCK_START) + len(BLOCK_START)
        end = text.index(BLOCK_END)
    except ValueError:
        raise SystemExit(f'{path} has no credential block markers '
                         f'({BLOCK_START} / {BLOCK_END}).')

    entries = {}
    for line in text[start:end].splitlines():
        parts = line.split('\t')
        if len(parts) == 4 and parts[0].strip().isdigit():
            entries[int(parts[0])] = (parts[1].strip(), parts[3].strip())
    return entries


def compare(entries, accounts):
    """Split the entries into ok / drifted / missing against {id: (email, hash)}."""
    from werkzeug.security import check_password_hash

    ok, drifted, missing = [], [], []
    for uid, (email, password) in sorted(entries.items()):
        if uid not in accounts:
            missing.append((uid, email))
            continue
        stored_email, password_hash = accounts[uid]
        if password_hash and check_password_hash(password_hash, password):
            ok.append((uid, stored_email))
        else:
            drifted.append((uid, stored_email))
    return ok, drifted, missing


def parse_args():
    parser = argparse.ArgumentParser(
        description='Check the recorded test passwords against the live hashes.')
    parser.add_argument('--sheet', type=Path, default=DEFAULT_SHEET,
                        help=f'credentials file (default: {DEFAULT_SHEET})')
    parser.add_argument(CONFIRM_FLAG, dest='confirm_production',
                        action='store_true',
                        help='allow a non-local / production-like database')
    return parser.parse_args()


def main():
    args = parse_args()
    require_confirmation('check the recorded test-account passwords')

    entries = read_credentials(args.sheet)
    if not entries:
        sys.exit(f'No credential entries found in {args.sheet}.')

    from app import create_app
    from app.models import User

    app = create_app()
    with app.app_context():
        accounts = {
            user.id: (user.email, user.password_hash)
            for user in User.query.filter(User.id.in_(list(entries))).all()
        }

    ok, drifted, missing = compare(entries, accounts)
    for uid, email in ok:
        print(f'  ok       id={uid} {mask_email(email)}')
    for uid, email in drifted:
        print(f'  DRIFTED  id={uid} {mask_email(email)}: the recorded password does '
              f'not authenticate this account')
    for uid, email in missing:
        print(f'  MISSING  id={uid} {mask_email(email)}: no account with this id')

    if drifted or missing:
        print(f'\n{len(drifted)} drifted, {len(missing)} missing. Update '
              f'{args.sheet} before handing the project over.')
        return 1
    print(f'\nAll {len(ok)} recorded password(s) still authenticate.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
