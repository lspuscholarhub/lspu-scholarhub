"""Audit trail for portal → ScholarHub student syncs.

One row per sync run (manual CLI, scheduled job, or portal webhook), so the
scholarship office and ICTS can see when student data last changed and why.
"""
import json
from datetime import datetime

from app import db


class PortalSyncRun(db.Model):
    __tablename__ = 'portal_sync_runs'

    id          = db.Column(db.Integer, primary_key=True)
    started_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    finished_at = db.Column(db.DateTime, nullable=True)
    trigger     = db.Column(db.String(30), nullable=False, default='manual')   # manual | login | webhook | schedule
    mode        = db.Column(db.String(20), nullable=False, default='sql')      # sql | file
    status      = db.Column(db.String(20), nullable=False, default='running')  # running | success | partial | failed

    seen      = db.Column(db.Integer, nullable=False, default=0)
    created   = db.Column(db.Integer, nullable=False, default=0)
    updated   = db.Column(db.Integer, nullable=False, default=0)
    unchanged = db.Column(db.Integer, nullable=False, default=0)
    skipped   = db.Column(db.Integer, nullable=False, default=0)
    failed    = db.Column(db.Integer, nullable=False, default=0)

    error   = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)   # JSON: per-student actions + fields

    def set_details(self, payload):
        self.details = json.dumps(payload, default=str) if payload else None

    def get_details(self):
        if not self.details:
            return {}
        try:
            return json.loads(self.details)
        except (TypeError, ValueError):
            return {}

    def to_dict(self):
        return {
            'id': self.id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'trigger': self.trigger,
            'mode': self.mode,
            'status': self.status,
            'seen': self.seen,
            'created': self.created,
            'updated': self.updated,
            'unchanged': self.unchanged,
            'skipped': self.skipped,
            'failed': self.failed,
            'error': self.error,
        }

    def __repr__(self):
        return f'<PortalSyncRun #{self.id} {self.status} seen={self.seen}>'
