from datetime import datetime
from app import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token

class User(db.Model):
    """User model for authentication and user management"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=True)   # optional — some students don't have one
    phone_number = db.Column(db.String(20))
    gender = db.Column(db.Enum('Male', 'Female'), nullable=True)
    town = db.Column(db.String(100), nullable=True)
    province = db.Column(db.String(100), nullable=True)
    date_of_birth = db.Column(db.Date)
    address = db.Column(db.Text)
    # Student-specific academic fields
    student_id = db.Column(db.String(30), unique=True)
    course = db.Column(db.String(100))
    year_level = db.Column(db.String(20))
    # Uploaded registration documents (for 2nd year and above)
    cor_file_path    = db.Column(db.String(500))   # Certificate of Registration
    grades_file_path = db.Column(db.String(500))   # Copy of Grades
    grades_semester  = db.Column(db.String(50))    # Which semester the grades are for (e.g. "2nd Semester AY 2025-2026")
    grades_updated_at = db.Column(db.DateTime)     # When grades were last uploaded/updated
    # Academic monitoring
    gwa              = db.Column(db.Float)          # General Weighted Average (input by staff)
    units_enrolled   = db.Column(db.Integer)        # Total units enrolled this semester
    user_type = db.Column(db.Enum('student', 'admin', 'staff'), default='student', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    # Password reset
    password_reset_token   = db.Column(db.String(100), unique=True, nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    # Phone verification
    phone_verified         = db.Column(db.Boolean, default=False, nullable=False)
    phone_otp              = db.Column(db.String(10), nullable=True)
    phone_otp_expires      = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    applications = db.relationship('ScholarshipApplication', foreign_keys='ScholarshipApplication.applicant_id', backref='applicant', lazy=True, cascade='all, delete-orphan')
    reviewed_applications = db.relationship('ScholarshipApplication', foreign_keys='ScholarshipApplication.reviewed_by', backref='reviewer', lazy=True)
    notifications = db.relationship('Notification', backref='recipient', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_access_token(self):
        """Generate JWT access token"""
        return create_access_token(identity=self.id)
    
    def get_full_name(self):
        """Get user's full name (includes middle name if present)."""
        if self.middle_name:
            return f"{self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    @property
    def grades_up_to_date(self):
        """Check if grades are updated for the current academic period."""
        from app.models.academic_period import AcademicPeriod
        current = AcademicPeriod.get_current()
        if not current or not self.grades_semester:
            return False
        return self.grades_semester == current.display_name
    
    def to_dict(self):
        """Convert user object to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone_number': self.phone_number,
            'user_type': self.user_type,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
