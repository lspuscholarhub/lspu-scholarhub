#!/usr/bin/env python3
"""Reset accounts whose current password is known.

Two ways to use it:

1. Sweep (default): find every account that still accepts a password published
   in this repo (the seed scripts used admin123 / student123 / staff123 /
   password) and give it a fresh random one. Those values are in git forever,
   so an account that still accepts one of them is a known-password login even
   if the account itself is legitimate.

2. Named reset: ``--account 56`` (id, email, username or student id) resets
   exactly that account, for a weak password that is not in the repo list,
   combined with ``--force-change`` so the owner must choose their own
   password at the next login. The account stays active and keeps its
   applications/documents -- they are not locked out, they just cannot keep
   using the old password.

Defaults to a dry run. Apply with:
    python scripts/dev/rotate_known_passwords.py --confirm-production \
        --apply --output _local_private/test_accounts.md

    # force a reset for one student who is on a weak password
    python scripts/dev/rotate_known_passwords.py --confirm-production \
        --account 56 --apply --force-change \
        --output _local_private/test_accounts.md

New passwords are written to --output before the database commit, so a crash
or a failed commit can never leave an account with a password nobody recorded.
The file is merged (not overwritten), so earlier rotated accounts keep their
credentials. With _local_private/test_accounts.md only the credential block
between the markers is rewritten, so the notes in that file survive a rotation.
Keep the file out of git -- .gitignore covers _local_private/ and backups/.
Passwords are never printed to the terminal.
"""
import argparse
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from _guard import CONFIRM_FLAG, require_confirmation  # noqa: E402

KNOWN_PASSWORDS = ('admin123', 'student123', 'staff123', 'password')

CREDENTIALS_HEADER = (
    '# Accounts whose password was reset by scripts/dev/rotate_known_passwords.py\n'
    '# id\temail\ttype\tnew password\n'
)

# A hand-written doc keeps its credential rows between these markers; only that
# block is replaced when a rotation is saved into it.
BLOCK_START = '<!-- rotate_known_passwords:start -->'
BLOCK_END = '<!-- rotate_known_passwords:end -->'


def mask_email(email):
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    return f'{local[:2]}***@{domain}'


def parse_args():
    parser = argparse.ArgumentParser(
        description='Rotate accounts that accept a known password.')
    parser.add_argument('--apply', action='store_true',
                        help='write the changes (default is a dry run)')
    parser.add_argument('--output', type=Path,
                        help='credentials file; required with --apply')
    parser.add_argument('--account', action='append', default=[],
                        metavar='ID_OR_EMAIL',
                        help='reset exactly this account even if its password '
                             'is not in the repo list (repeatable)')
    parser.add_argument('--force-change', action='store_true',
                        help='require the owner to choose a new password at next '
                             'login (the app blocks every page until they do)')
    parser.add_argument(CONFIRM_FLAG, dest='confirm_production',
                        action='store_true',
                        help='allow a non-local / production-like database')
    args = parser.parse_args()
    if args.apply and args.output is None:
        parser.error('--apply needs --output: the new passwords would be lost.')
    return args


def _read_existing(path):
    """Existing credentials, keyed by account id, so a rerun never drops one."""
    entries = {}
    if path and path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            parts = line.split('\t')
            if len(parts) >= 4 and parts[0].strip().isdigit():
                entries[int(parts[0])] = line.rstrip('\n')
    return entries


def save_credentials(path, changed):
    """Persist the new passwords atomically, keeping every earlier entry.

    Called BEFORE db.session.commit(): if the write fails we abort without
    touching the database; if the commit fails, the file already holds the
    passwords so nothing is lost (a stale line is harmless, an unrecorded
    password locks a real student out).

    The destination is normally the hand-written
    _local_private/test_accounts.md. When it carries the block markers only the
    rows between them are replaced, so the notes around them survive; a plain
    file with no markers keeps the old header-plus-rows format.
    """
    entries = _read_existing(path)
    for uid, email, utype, new_password in changed:
        entries[uid] = f'{uid}\t{email}\t{utype}\t{new_password}'
    rows = [entries[uid] for uid in sorted(entries)]

    existing = path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    if BLOCK_START in existing and BLOCK_END in existing:
        start = existing.index(BLOCK_START)
        end = existing.index(BLOCK_END)
        lines = existing[:start + 1] + rows + existing[end:]
    else:
        lines = CREDENTIALS_HEADER.splitlines() + rows

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def select_targets(accounts):
    """Accounts to reset: the named ones, or every known-password match."""
    from werkzeug.security import check_password_hash
    from app import db
    from app.models import User

    def matched_passwords(user):
        return [pw for pw in KNOWN_PASSWORDS
                if user.password_hash and check_password_hash(user.password_hash, pw)]

    if not accounts:
        targets = []
        for user in User.query.order_by(User.id).all():
            matched = matched_passwords(user)
            if matched:
                targets.append((user, matched))
        return targets

    targets = []
    for spec in accounts:
        user = db.session.get(User, int(spec)) if spec.isdigit() else None
        if user is None:
            user = (User.query.filter_by(email=spec).first()
                    or User.query.filter_by(username=spec).first()
                    or User.query.filter_by(student_id=spec).first())
        if user is None:
            sys.exit(f'No account matches --account {spec!r}.')
        targets.append((user, matched_passwords(user)))
    return targets


def main():
    args = parse_args()
    require_confirmation('rotate accounts that use a known password')

    from werkzeug.security import check_password_hash
    from app import create_app, db
    from app.models import User

    app = create_app()
    changed = []
    with app.app_context():
        targets = select_targets(args.account)
        if not targets:
            print('No account still accepts a password published in this repo.')
            return 0

        for user, matched in targets:
            reason = ('password is published in this repo' if matched
                      else 'named explicitly, password not in the repo list')
            if not user.is_active:
                reason += ', account is DISABLED'
            print(f"  {'ROTATE' if args.apply else 'would rotate'}: id={user.id} "
                  f"type={user.user_type} email={mask_email(user.email)} ({reason})")
            if not args.apply:
                continue

            new_password = secrets.token_urlsafe(12)
            user.set_password(new_password)
            if args.force_change:
                user.must_change_password = True
            changed.append((user.id, user.email, user.user_type, new_password))

        if changed:
            try:
                save_credentials(args.output, changed)
            except OSError as exc:
                db.session.rollback()
                sys.exit(f'Could not write {args.output} ({exc.__class__.__name__}). '
                         f'Nothing was committed, so no password changed.')

            try:
                db.session.commit()
            except Exception as exc:  # noqa: BLE001 - never echo the DB URL
                db.session.rollback()
                sys.exit(f'Database write failed ({exc.__class__.__name__}); nothing '
                         f'was committed. The new passwords are already in '
                         f'{args.output} but are NOT active -- re-run to retry, or '
                         f'delete those lines before handing the file out.')

            # Confirm the stored hashes accept the passwords we recorded.
            db.session.expire_all()
            for uid, _, _, new_password in changed:
                user = db.session.get(User, uid)
                ok = bool(user and check_password_hash(user.password_hash, new_password))
                print(f'  verified: id={uid} {"accepts the new password" if ok else "FAILED"}')
                if not ok:
                    return 2

    if not args.apply:
        print('\nDry run: nothing was changed.')
        return 0

    print(f'\nReset {len(changed)} account(s).')
    print(f'New passwords are in {args.output} (keep it out of git).')
    if args.force_change:
        print('Each account must choose its own password at the next login; the '
              'old password no longer works.')
    print('Owners who never receive the temporary password can still use '
          'Auth > Forgot password (Student ID + registered email) to set one.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
