from datetime import datetime
from app import db
from enum import Enum

class NotificationType(Enum):
    APPLICATION_SUBMITTED = 'application_submitted'
    APPLICATION_APPROVED = 'application_approved'
    APPLICATION_REJECTED = 'application_rejected'
    DEADLINE_REMINDER = 'deadline_reminder'
    NEW_SCHOLARSHIP = 'new_scholarship'
    SYSTEM_ANNOUNCEMENT = 'system_announcement'

class NotificationChannel(Enum):
    EMAIL = 'email'
    SMS = 'sms'
    IN_APP = 'in_app'
    PUSH = 'push'

class Notification(db.Model):
    """Notification model for managing user notifications"""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.Enum(NotificationType), nullable=False)
    channel = db.Column(db.Enum(NotificationChannel), default=NotificationChannel.IN_APP, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    read_at = db.Column(db.DateTime)
    related_entity_type = db.Column(db.String(50))  # e.g., 'scholarship', 'application'
    related_entity_id = db.Column(db.Integer)
    academic_period_id = db.Column(db.Integer, db.ForeignKey('academic_periods.id'), nullable=True)
    
    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert notification object to dictionary"""
        return {
            'id': self.id,
            'recipient_id': self.recipient_id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type.value if self.notification_type else None,
            'channel': self.channel.value if self.channel else None,
            'is_read': self.is_read,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'related_entity_type': self.related_entity_type,
            'related_entity_id': self.related_entity_id
        }
    
    @staticmethod
    def create_application_notification(user_id, scholarship_title, status):
        """Create notification for application status change"""
        if status == 'approved':
            title = "Application Approved!"
            message = f"Congratulations! Your application for '{scholarship_title}' has been approved."
            notification_type = NotificationType.APPLICATION_APPROVED
        elif status == 'rejected':
            title = "Application Update"
            message = f"Your application for '{scholarship_title}' has been reviewed. Please check your account for details."
            notification_type = NotificationType.APPLICATION_REJECTED
        else:
            return None
            
        return Notification(
            recipient_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            channel=NotificationChannel.IN_APP
        )
    
    def __repr__(self):
        return f'<Notification {self.title}>'
