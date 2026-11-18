"""Per-scholarship requirements a scholar must submit to keep the grant.

The Scholarship Office asks for different things depending on the program — a
Certificate of Enrollment for one, a signed grade slip for another — so the
requirement list belongs to the scholarship rather than being hard-coded.
Students upload one file per requirement; staff can see how many scholars have
submitted.
"""
from datetime import date, datetime

from app import db


class ScholarshipRequirement(db.Model):
    __tablename__ = 'scholarship_requirements'

    id             = db.Column(db.Integer, primary_key=True)
    scholarship_id = db.Column(db.Integer,
                               db.ForeignKey('scholarships.id', ondelete='CASCADE'),
                               nullable=False)
    title          = db.Column(db.String(150), nullable=False)
    instructions   = db.Column(db.String(255), nullable=True)
    due_date       = db.Column(db.Date, nullable=True)
    is_required    = db.Column(db.Boolean, nullable=False, default=True)
    sort_order     = db.Column(db.Integer, nullable=False, default=0)
    created_by     = db.Column(db.Integer,
                               db.ForeignKey('users.id', ondelete='SET NULL'),
                               nullable=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    scholarship = db.relationship(
        'Scholarship',
        backref=db.backref('requirements', lazy=True, cascade='all, delete-orphan',
                           order_by='ScholarshipRequirement.sort_order'))
    submissions = db.relationship('RequirementSubmission', back_populates='requirement',
                                  cascade='all, delete-orphan', lazy=True)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < date.today())

    def __repr__(self):
        return f'<ScholarshipRequirement {self.title} (scholarship={self.scholarship_id})>'


class RequirementSubmission(db.Model):
    __tablename__ = 'requirement_submissions'

    id                 = db.Column(db.Integer, primary_key=True)
    requirement_id     = db.Column(db.Integer,
                                   db.ForeignKey('scholarship_requirements.id',
                                                 ondelete='CASCADE'),
                                   nullable=False)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    application_id     = db.Column(db.Integer,
                                   db.ForeignKey('scholarship_applications.id'),
                                   nullable=True)
    academic_period_id = db.Column(db.Integer,
                                   db.ForeignKey('academic_periods.id'), nullable=True)

    original_filename    = db.Column(db.String(255), nullable=False)
    file_url             = db.Column(db.String(500), nullable=True)
    cloudinary_public_id = db.Column(db.String(255), nullable=True)
    local_path           = db.Column(db.String(500), nullable=True)
    file_type            = db.Column(db.String(10))
    file_size            = db.Column(db.Integer)

    status      = db.Column(db.String(20), nullable=False, default='submitted')
    remarks     = db.Column(db.String(255), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    requirement = db.relationship('ScholarshipRequirement', back_populates='submissions')
    owner       = db.relationship('User', foreign_keys=[user_id],
                                  backref=db.backref('requirement_submissions', lazy=True))

    @property
    def file_size_display(self):
        if not self.file_size:
            return 'Unknown'
        if self.file_size < 1024:
            return f'{self.file_size} B'
        if self.file_size < 1024 ** 2:
            return f'{self.file_size / 1024:.1f} KB'
        return f'{self.file_size / 1024 ** 2:.1f} MB'

    def __repr__(self):
        return (f'<RequirementSubmission req={self.requirement_id} '
                f'user={self.user_id}>')
