"""
Campus model — represents each LSPU campus.

Currently:
  - Santa Cruz Campus
  - Siniloan Campus
  - San Pablo City
  - Los Baños

Every user, scholarship, batch, and application belongs to a campus.
University-wide scholarships have campus_id = NULL.
"""
from datetime import datetime
from app import db


class Campus(db.Model):
    __tablename__ = 'campuses'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False, unique=True)
    short_name  = db.Column(db.String(30), nullable=True)   # e.g. 'SC', 'SN', 'SBC', 'LB'
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Campus {self.short_name or self.name}>'

    @classmethod
    def get_by_name(cls, name):
        return cls.query.filter(cls.name.ilike(f'%{name}%')).first()
