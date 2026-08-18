"""
GWA History model — stores per-semester GWA entries for each student.
Allows trend tracking over time instead of just the current GWA snapshot.
"""
from datetime import datetime
from app import db


class GwaHistory(db.Model):
    __tablename__ = 'gwa_history'

    id          = db.Column(db.Integer, primary_key=True)
    student_id  = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    gwa         = db.Column(db.Float, nullable=False)
    semester    = db.Column(db.String(30), nullable=False)   # e.g. '1st Semester'
    school_year = db.Column(db.String(20), nullable=False)   # e.g. '2025-2026'
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    notes       = db.Column(db.String(255))
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    student  = db.relationship('User', foreign_keys=[student_id],
                                backref=db.backref('gwa_history', lazy=True,
                                                   order_by='GwaHistory.recorded_at.desc()'))
    recorder = db.relationship('User', foreign_keys=[recorded_by])

    @property
    def standing(self):
        """Return LSPU grade standing label."""
        if self.gwa <= 1.25:   return 'Excellent'
        if self.gwa <= 1.75:   return 'Very Satisfactory'
        if self.gwa <= 2.25:   return 'Satisfactory'
        if self.gwa <= 2.75:   return 'Fairly Satisfactory'
        if self.gwa <= 3.00:   return 'Passed'
        if self.gwa < 4.00:    return 'Conditional Failure'
        return 'Failed'

    @property
    def is_at_risk(self):
        return self.gwa > 3.00

    def to_dict(self):
        return {
            'id':          self.id,
            'student_id':  self.student_id,
            'gwa':         self.gwa,
            'semester':    self.semester,
            'school_year': self.school_year,
            'standing':    self.standing,
            'is_at_risk':  self.is_at_risk,
            'notes':       self.notes,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
        }

    def __repr__(self):
        return f'<GwaHistory student={self.student_id} gwa={self.gwa} {self.semester} {self.school_year}>'
