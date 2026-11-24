"""Configurable public contact address and outgoing-mail sender.

Both used to be the literal string lspu.scholarhub@gmail.com, repeated in the
footer, the contact page, error pages, the chatbot's answers and every send
path. That Google account was disabled: the UI pointed at an inbox nobody could
read, and mail could not be repaired without editing code. Both values now come
from the environment.

    CONTACT_EMAIL     where students are told to write (contact form inbox too)
    MAIL_FROM_EMAIL   the From address on outgoing mail; falls back to
                      MAIL_USERNAME, which is the authenticated SMTP account
    MAIL_FROM_NAME    display name on outgoing mail (default LSPU ScholarHub)
"""
import os

DEFAULT_CONTACT_EMAIL = 'lspu.scholarhub@gmail.com'
DEFAULT_SENDER_NAME = 'LSPU ScholarHub'


def contact_email():
    """The office address shown to users and used as the contact-form inbox."""
    return (os.environ.get('CONTACT_EMAIL') or DEFAULT_CONTACT_EMAIL).strip()


def sender_email():
    """From address for outgoing mail: MAIL_FROM_EMAIL, else the SMTP user.

    Returns '' when neither is set, so each provider decides its own default
    instead of inheriting an address that cannot send.
    """
    return (os.environ.get('MAIL_FROM_EMAIL')
            or os.environ.get('MAIL_USERNAME') or '').strip()


def sender_name():
    """Display name shown next to the From address."""
    return (os.environ.get('MAIL_FROM_NAME') or DEFAULT_SENDER_NAME).strip()