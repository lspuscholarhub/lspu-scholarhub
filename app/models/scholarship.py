from datetime import datetime
from sqlalchemy.dialects.mysql import DECIMAL
from app import db
from enum import Enum

class ScholarshipStatus(Enum):
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    CLOSED = 'closed'

class ApplicationStatus(Enum):
    PENDING = 'pending'
    UNDER_REVIEW = 'under_review'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    WITHDRAWN = 'withdrawn'

class Scholarship(db.Model):
    __tablename__ = 'scholarships'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), default='General')
    scholarship_type = db.Column(db.Enum('Financial Assistance', 'Merit Scholarship', 'Grant', 'Other'),
                                 default='Financial Assistance')
    funding_type = db.Column(db.Enum('public', 'private'), default='public', nullable=False,
                             server_default='public')  # public: only one held at a time; private: combinable
    description = db.Column(db.Text, nullable=False)
    eligibility_criteria = db.Column(db.Text, nullable=False)
    benefits = db.Column(db.Text, nullable=False)
    application_deadline = db.Column(db.DateTime, nullable=True)
    award_amount = db.Column(DECIMAL(10, 2))
    max_applicants = db.Column(db.Integer)
    current_applicants = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum(ScholarshipStatus), default=ScholarshipStatus.ACTIVE, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    allowed_student_ids = db.Column(db.Text, nullable=True)
    custom_form_fields = db.Column(db.JSON, nullable=True)  # Custom form fields for this scholarship
    campus_id = db.Column(db.Integer, db.ForeignKey('campuses.id'), nullable=True)  # NULL = university-wide
    scope     = db.Column(db.Enum('campus', 'university'), default='campus', nullable=False)

    campus = db.relationship('Campus', backref='scholarships', lazy=True)

    applications = db.relationship('ScholarshipApplication', backref='scholarship',
                                   lazy=True, cascade='all, delete-orphan')

    def get_allowed_ids(self):
        if not self.allowed_student_ids:
            return set()
        return {sid.strip() for sid in self.allowed_student_ids.split(',') if sid.strip()}

    def is_visible_to(self, student_id=None):
        if not self.is_hidden:
            return True
        if not student_id:
            return False
        return student_id in self.get_allowed_ids()

    def is_application_open(self):
        if self.status != ScholarshipStatus.ACTIVE:
            return False
        if self.application_deadline is not None and self.application_deadline < datetime.utcnow():
            return False
        if self.max_applicants is not None and self.current_applicants >= self.max_applicants:
            return False
        return True

    def increment_applicants(self):
        if self.current_applicants is not None:
            self.current_applicants += 1

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'eligibility_criteria': self.eligibility_criteria,
            'benefits': self.benefits,
            'application_deadline': self.application_deadline.isoformat() if self.application_deadline else None,
            'award_amount': float(self.award_amount) if self.award_amount else None,
            'max_applicants': self.max_applicants,
            'current_applicants': self.current_applicants,
            'status': self.status.value if self.status else None,
            'is_hidden': self.is_hidden,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_application_open': self.is_application_open()
        }

    def __repr__(self):
        return f'<Scholarship {self.title}>'


class ScholarshipApplication(db.Model):
    __tablename__ = 'scholarship_applications'

    id = db.Column(db.Integer, primary_key=True)
    scholarship_id = db.Column(db.Integer, db.ForeignKey('scholarships.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    application_data = db.Column(db.JSON)
    documents = db.Column(db.JSON)
    status = db.Column(db.Enum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False)
    scholar_tag = db.Column(db.Enum('active', 'at_risk', 'probation', 'inactive'), default='active')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)
    final_decision_date = db.Column(db.DateTime)
    approved_at = db.Column(db.DateTime)

    # Batch & period assignment
    batch_id           = db.Column(db.Integer, db.ForeignKey('scholarship_batches.id', ondelete='SET NULL'), nullable=True)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_periods.id'), nullable=True)
    amount_received    = db.Column(db.Numeric(10, 2), nullable=True)   # actual amount given to this student
    seq_number         = db.Column(db.Integer, nullable=True)          # sequence number within the batch
    campus_id          = db.Column(db.Integer, db.ForeignKey('campuses.id'), nullable=True)

    # Monitoring & Tracking
    scholar_status        = db.Column(db.String(30), default='active')
    compliance_status     = db.Column(db.String(20), default='compliant')
    last_compliance_check = db.Column(db.DateTime)
    status_updated_at     = db.Column(db.DateTime)
    renewal_notified_at   = db.Column(db.DateTime)
    is_active             = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'scholarship_id': self.scholarship_id,
            'applicant_id': self.applicant_id,
            'application_data': self.application_data,
            'documents': self.documents,
            'status': self.status.value if self.status else None,
            'scholar_tag': self.scholar_tag,
            'scholar_status': self.scholar_status,
            'compliance_status': self.compliance_status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'final_decision_date': self.final_decision_date.isoformat() if self.final_decision_date else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
        }

    def __repr__(self):
        return f'<ScholarshipApplication {self.id}>'
