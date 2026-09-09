"""
Scholarship Batch model — groups approved scholars into batches.

Real-world workflow:
  - A scholarship (e.g. TES) receives applications each semester
  - Approved scholars are grouped into batches (Batch 1, Batch 1.1, Batch 2, etc.)
  - Each batch has a fixed amount per scholar and tracks male/female counts
  - The system auto-suggests the next batch name but admin can rename it
"""
from datetime import datetime
from app import db


class ScholarshipBatch(db.Model):
    __tablename__ = 'scholarship_batches'

    id                 = db.Column(db.Integer, primary_key=True)
    scholarship_id     = db.Column(db.Integer, db.ForeignKey('scholarships.id', ondelete='CASCADE'), nullable=False)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_periods.id'), nullable=False)
    batch_name         = db.Column(db.String(50), nullable=False)       # e.g. 'Batch 1', 'Batch 1.1', 'Batch 2'
    batch_number       = db.Column(db.Float, nullable=False, default=1) # numeric for sorting (1, 1.1, 2, 3)
    amount_per_scholar = db.Column(db.Numeric(10, 2), nullable=True)    # ₱ per student
    total_scholars     = db.Column(db.Integer, default=0)
    total_male         = db.Column(db.Integer, default=0)
    total_female       = db.Column(db.Integer, default=0)
    total_amount       = db.Column(db.Numeric(12, 2), default=0)
    status             = db.Column(db.Enum('open', 'closed', 'finalized'), default='open')
    notes              = db.Column(db.Text, nullable=True)
    campus_id          = db.Column(db.Integer, db.ForeignKey('campuses.id'), nullable=True)
    created_by         = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    scholarship  = db.relationship('Scholarship', backref=db.backref('batches', lazy=True, order_by='ScholarshipBatch.batch_number'))
    creator      = db.relationship('User', foreign_keys=[created_by])
    applications = db.relationship('ScholarshipApplication', backref='batch', lazy=True)

    def recalculate_totals(self):
        """Recalculate summary fields from linked applications."""
        from app.models import User
        apps = [a for a in self.applications if a.status and a.status.value == 'approved']
        self.total_scholars = len(apps)
        self.total_male   = sum(1 for a in apps if a.applicant and a.applicant.gender == 'Male')
        self.total_female = sum(1 for a in apps if a.applicant and a.applicant.gender == 'Female')
        if self.amount_per_scholar:
            self.total_amount = float(self.amount_per_scholar) * self.total_scholars
        else:
            self.total_amount = sum(float(a.amount_received or 0) for a in apps)

    @classmethod
    def suggest_next_batch_name(cls, scholarship_id, academic_period_id):
        """
        Auto-suggest the next batch name for a scholarship in a given period.
        Logic: find the highest batch_number and increment.
          - If last was 1 → suggest 'Batch 2'
          - If last was 1.1 → suggest 'Batch 2'
          - If none exist → suggest 'Batch 1'
        Admin can always override this.
        """
        last = cls.query.filter_by(
            scholarship_id=scholarship_id,
            academic_period_id=academic_period_id,
        ).order_by(cls.batch_number.desc()).first()

        if not last:
            return 'Batch 1', 1.0

        # If last was a sub-batch (e.g. 1.1), next is the next whole number
        import math
        next_num = math.ceil(last.batch_number) + 1
        return f'Batch {next_num}', float(next_num)

    @classmethod
    def suggest_sub_batch_name(cls, scholarship_id, academic_period_id, parent_number):
        """
        Suggest a sub-batch name (e.g. Batch 1 → Batch 1.1).
        Used when more scholars need to be added to an existing batch group.
        """
        existing = cls.query.filter(
            cls.scholarship_id == scholarship_id,
            cls.academic_period_id == academic_period_id,
            cls.batch_number >= parent_number,
            cls.batch_number < parent_number + 1,
        ).order_by(cls.batch_number.desc()).first()

        if existing:
            # e.g. existing is 1.1 → next is 1.2
            sub = round((existing.batch_number - int(existing.batch_number)) * 10) + 1
            next_num = parent_number + sub / 10
        else:
            next_num = parent_number + 0.1

        return f'Batch {next_num:.1f}'.replace('.0', ''), next_num

    @property
    def display_name(self):
        return self.batch_name

    def to_dict(self):
        return {
            'id':                 self.id,
            'scholarship_id':    self.scholarship_id,
            'academic_period_id': self.academic_period_id,
            'batch_name':        self.batch_name,
            'batch_number':      self.batch_number,
            'amount_per_scholar': float(self.amount_per_scholar) if self.amount_per_scholar else None,
            'total_scholars':    self.total_scholars,
            'total_male':        self.total_male,
            'total_female':      self.total_female,
            'total_amount':      float(self.total_amount) if self.total_amount else 0,
            'status':            self.status,
        }

    def __repr__(self):
        return f'<ScholarshipBatch {self.batch_name} (scholarship={self.scholarship_id})>'
