"""
Monitoring & Evaluation Form Submission model.

Workflow:
  - Every scholar must submit the LSPU M&E form (LSPU-SFA-SF-006) each semester.
  - Student downloads the blank form, has instructors sign it, uploads a
    photo/PDF scan of the accomplished form.
  - Staff/admin can view the uploaded file on the Monitoring page.
"""
from datetime import datetime
from app import db


class MonitoringSubmission(db.Model):
    __tablename__ = 'monitoring_submissions'

    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    application_id  = db.Column(db.Integer, db.ForeignKey('scholarship_applications.id'), nullable=False)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_periods.id'), nullable=True)

    # File storage (Cloudinary preferred, local fallback)
    original_filename   = db.Column(db.String(255), nullable=False)
    file_url            = db.Column(db.String(500), nullable=True)
    cloudinary_public_id = db.Column(db.String(255), nullable=True)
    local_path          = db.Column(db.String(500), nullable=True)
    file_type           = db.Column(db.String(10))          # pdf, jpg, jpeg, png
    file_size           = db.Column(db.Integer)             # bytes

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    owner        = db.relationship('User', backref=db.backref('monitoring_submissions', lazy=True))
    application  = db.relationship('ScholarshipApplication',
                                   backref=db.backref('monitoring_submissions', lazy=True))
    academic_period = db.relationship('AcademicPeriod', backref='monitoring_submissions')

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
        return f'<MonitoringSubmission user={self.user_id} app={self.application_id}>'
