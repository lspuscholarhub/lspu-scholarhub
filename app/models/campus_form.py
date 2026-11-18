"""Campus-wide forms a scholar must submit, alongside the M&E form.

The Monitoring & Evaluation form is a fixed column on the academic period, but
campuses sometimes need other forms for the whole semester — a scholarship
agreement, a renewal letter, an endorsement slip. Those are not tied to one
scholarship program, so staff add them here per academic period and every
scholar in the campus uploads one file for each.
"""
from datetime import date, datetime

from app import db


class CampusForm(db.Model):
    __tablename__ = 'campus_forms'

    id                 = db.Column(db.Integer, primary_key=True)
    campus_id          = db.Column(db.Integer,
                                   db.ForeignKey('campuses.id', ondelete='CASCADE'),
                                   nullable=False)
    academic_period_id = db.Column(db.Integer,
                                   db.ForeignKey('academic_periods.id', ondelete='SET NULL'),
                                   nullable=True)
    title              = db.Column(db.String(150), nullable=False)
    instructions       = db.Column(db.String(255), nullable=True)
    due_date           = db.Column(db.Date, nullable=True)
    is_required        = db.Column(db.Boolean, nullable=False, default=True)
    sort_order         = db.Column(db.Integer, nullable=False, default=0)
    created_by         = db.Column(db.Integer,
                                   db.ForeignKey('users.id', ondelete='SET NULL'),
                                   nullable=True)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    campus = db.relationship('Campus')
    submissions = db.relationship('CampusFormSubmission', back_populates='form',
                                  cascade='all, delete-orphan', lazy=True)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.due_date < date.today())

    def __repr__(self):
        return f'<CampusForm {self.title} (campus={self.campus_id})>'


class CampusFormSubmission(db.Model):
    __tablename__ = 'campus_form_submissions'

    id                 = db.Column(db.Integer, primary_key=True)
    form_id            = db.Column(db.Integer,
                                   db.ForeignKey('campus_forms.id', ondelete='CASCADE'),
                                   nullable=False)
    user_id            = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    academic_period_id = db.Column(db.Integer,
                                   db.ForeignKey('academic_periods.id', ondelete='SET NULL'),
                                   nullable=True)

    original_filename    = db.Column(db.String(255), nullable=False)
    file_url             = db.Column(db.String(500), nullable=True)
    cloudinary_public_id = db.Column(db.String(255), nullable=True)
    local_path           = db.Column(db.String(500), nullable=True)
    file_type            = db.Column(db.String(10))
    file_size            = db.Column(db.Integer)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    form  = db.relationship('CampusForm', back_populates='submissions')
    owner = db.relationship('User', foreign_keys=[user_id],
                            backref=db.backref('campus_form_submissions', lazy=True))

    def __repr__(self):
        return f'<CampusFormSubmission form={self.form_id} user={self.user_id}>'
