from datetime import datetime
from app import db


class Document(db.Model):
    """Stores metadata for every file uploaded by a student."""
    __tablename__ = 'documents'

    id                = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    application_id    = db.Column(db.Integer, db.ForeignKey('scholarship_applications.id'), nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename   = db.Column(db.String(255), nullable=False, unique=True)
    file_path         = db.Column(db.String(500), nullable=False)
    file_size         = db.Column(db.Integer)          # bytes
    category          = db.Column(db.String(50))       # transcript, good_moral, birth_cert, awards …
    file_type         = db.Column(db.String(10))       # pdf, docx, jpg …
    description       = db.Column(db.String(255))
    is_verified       = db.Column(db.Boolean, default=False, nullable=False)
    ctc_detected      = db.Column(db.Boolean, nullable=True)   # None=not checked, True=CTC found, False=not found
    uploaded_at       = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner       = db.relationship('User', backref=db.backref('documents', lazy=True))
    application = db.relationship('ScholarshipApplication',
                                  backref=db.backref('uploaded_documents', lazy=True))

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def file_size_display(self):
        """Human-readable file size."""
        if self.file_size is None:
            return 'Unknown'
        if self.file_size < 1024:
            return f'{self.file_size} B'
        if self.file_size < 1024 ** 2:
            return f'{self.file_size / 1024:.1f} KB'
        return f'{self.file_size / 1024 ** 2:.1f} MB'

    @property
    def icon_class(self):
        """Bootstrap-icon class based on file type."""
        icons = {
            'pdf':  'bi-file-earmark-pdf text-danger',
            'doc':  'bi-file-earmark-word text-primary',
            'docx': 'bi-file-earmark-word text-primary',
            'jpg':  'bi-file-earmark-image text-success',
            'jpeg': 'bi-file-earmark-image text-success',
            'png':  'bi-file-earmark-image text-success',
        }
        return icons.get((self.file_type or '').lower(), 'bi-file-earmark text-secondary')

    def to_dict(self):
        return {
            'id':                self.id,
            'user_id':           self.user_id,
            'application_id':    self.application_id,
            'original_filename': self.original_filename,
            'stored_filename':   self.stored_filename,
            'file_size':         self.file_size,
            'file_size_display': self.file_size_display,
            'category':          self.category,
            'file_type':         self.file_type,
            'description':       self.description,
            'is_verified':       self.is_verified,
            'uploaded_at':       self.uploaded_at.isoformat() if self.uploaded_at else None,
        }

    def __repr__(self):
        return f'<Document {self.original_filename}>'
