"""Messages sent through the public contact form.

The form used to only email the office, so a message was lost whenever the mail
provider was not configured or refused the send. Every submission is stored here
first; admins read them under Messages, and the email is a notification on top.
"""
from datetime import datetime

from app import db


class ContactMessage(db.Model):
    __tablename__ = 'contact_messages'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(20))
    subject    = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow,
                           nullable=False, index=True)
    # Whether the mail provider accepted the notification — not whether the
    # message exists. The row is the record; this only says if it was also sent.
    emailed    = db.Column(db.Boolean, default=False, nullable=False)
    is_read    = db.Column(db.Boolean, default=False, nullable=False)

    @property
    def created_campus(self):
        """created_at on the campus clock (PHT), for display."""
        from app.utils.timefmt import to_campus
        return to_campus(self.created_at)

    def __repr__(self):
        return f'<ContactMessage {self.id} from {self.email}>'
