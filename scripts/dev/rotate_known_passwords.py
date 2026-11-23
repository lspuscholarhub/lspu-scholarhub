#!/usr/bin/env python3
"""Rotate any account still using a password that is published in this repo.

The seed scripts set admin123 / student123 / staff123 / password. Those values
are in git forever, so an account that still accepts one of them is a
known-password login even if the account itself is legitimate. This script
finds those accounts and replaces the password with a fresh random one,
without deleting the account or its applications/documents.

Defaults to a dry run. Apply with:
    python scripts/dev/rotate_known_passwords.py --confirm-production \
        --output _local_private/rotated_accounts.txt

New passwords are written to --output (never printed) so they can be handed
to the account owners. The output file must stay out of git (.gitignore
already covers _local_private/ and backups/).
"""
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from _guard import CONFIRM_FLAG, require_confirmation  # noqa: E402

KNOWN_PASSWORDS = ('admin123', 'student123', 'staff123', 'password')


def mask_email(email):
    if not email or '@' not in email:
        return email or ''
    local, domain = email.split('@', 1)
    return f'{local[:2]}***@{domain}'


def main():
    require_confirmation('rotate accounts that use a repo-known password')
    # Two separate switches: --confirm-production lets the guard through, and
    # --apply is what actually writes. Without --apply the run is read-only.
    apply = '--apply' in sys.argv

    output = None
    if '--output' in sys.argv:
        index = sys.argv.index('--output')
        if index + 1 >= len(sys.argv):
            sys.exit('--output needs a file path')
        output = Path(sys.argv[index + 1])
    if apply and output is None:
        sys.exit('Refusing to apply without --output: the new passwords would be lost.')

    from werkzeug.security import check_password_hash
    from app import create_app, db
    from app.models import User

    app = create_app()
    changed = []
    with app.app_context():
        users = User.query.order_by(User.id).all()
        for user in users:
            matched = [pw for pw in KNOWN_PASSWORDS
                       if user.password_hash and check_password_hash(user.password_hash, pw)]
            if not matched:
                continue
            print(f"  {'ROTATE' if apply else 'would rotate'}: id={user.id} "
                  f"type={user.user_type} email={mask_email(user.email)}")
            if not apply:
                continue
            new_password = secrets.token_urlsafe(12)
            user.set_password(new_password)
            if hasattr(user, 'must_change_password'):
                user.must_change_password = False
            changed.append((user.id, user.email, user.user_type, new_password))

        if changed:
            db.session.commit()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                '# Accounts whose repo-known password was rotated\n'
                '# id\temail\ttype\tnew password\n'
                + ''.join(f'{uid}\t{email}\t{utype}\t{pw}\n'
                          for uid, email, utype, pw in changed),
                encoding='utf-8')
            try:
                os.chmod(output, 0o600)
            except OSError:
                pass

    if apply:
        print(f'\nRotated {len(changed)} account(s).')
    else:
        print('\nDry run: nothing was changed.')
    if apply:
        print(f'New passwords written to {output} (keep it out of git).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
