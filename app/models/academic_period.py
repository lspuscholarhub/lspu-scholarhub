"""
Academic Period model — tracks academic years and semesters.
The system uses this to know which semester is current and to
associate applications/batches with the correct period.
"""
from datetime import datetime
from app import db


class AcademicPeriod(db.Model):
    __tablename__ = 'academic_periods'

    id            = db.Column(db.Integer, primary_key=True)
    academic_year = db.Column(db.String(20), nullable=False)   # e.g. '2025-2026'
    semester      = db.Column(db.String(30), nullable=False)   # '1st Semester', '2nd Semester', 'Summer'
    is_current    = db.Column(db.Boolean, default=False)
    start_date    = db.Column(db.Date, nullable=True)
    end_date      = db.Column(db.Date, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    batches      = db.relationship('ScholarshipBatch', backref='academic_period', lazy=True)
    applications = db.relationship('ScholarshipApplication', backref='academic_period', lazy=True)

    @classmethod
    def get_current(cls):
        """Return the current academic period."""
        return cls.query.filter_by(is_current=True).first()

    @classmethod
    def set_current(cls, period_id):
        """Set a period as current (unsets all others)."""
        cls.query.update({'is_current': False})
        period = cls.query.get(period_id)
        if period:
            period.is_current = True
        db.session.commit()
        return period

    @property
    def display_name(self):
        return f"{self.semester} AY {self.academic_year}"

    def to_dict(self):
        return {
            'id':            self.id,
            'academic_year': self.academic_year,
            'semester':      self.semester,
            'is_current':    self.is_current,
            'display_name':  self.display_name,
        }

    def __repr__(self):
        return f'<AcademicPeriod {self.display_name}>'
