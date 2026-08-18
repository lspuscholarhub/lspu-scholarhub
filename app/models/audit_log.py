"""
Audit Log model — records every significant action in the system.
Covers: logins, logouts, application decisions, GWA updates,
        scholarship changes, user management, and document actions.
"""
from datetime import datetime
from app import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id          = db.Column(db.Integer, primary_key=True)
    # Who did it
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    user_name   = db.Column(db.String(120))   # snapshot — survives user deletion
    user_role   = db.Column(db.String(20))    # admin / staff / student

    # What happened
    action      = db.Column(db.String(80), nullable=False)   # e.g. 'application.approve'
    category    = db.Column(db.String(40))                   # auth / application / scholarship / user / gwa / document
    description = db.Column(db.Text)                         # human-readable detail
    target_type = db.Column(db.String(40))                   # 'application' | 'scholarship' | 'user' …
    target_id   = db.Column(db.Integer)                      # PK of the affected record

    # Context
    ip_address  = db.Column(db.String(45))
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    actor = db.relationship('User', foreign_keys=[user_id], backref=db.backref('audit_logs', lazy=True))

    def to_dict(self):
        return {
            'id':          self.id,
            'user_name':   self.user_name,
            'user_role':   self.user_role,
            'action':      self.action,
            'category':    self.category,
            'description': self.description,
            'target_type': self.target_type,
            'target_id':   self.target_id,
            'ip_address':  self.ip_address,
            'timestamp':   self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.user_name}>'
