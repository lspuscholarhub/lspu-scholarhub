"""Chat history model — persists AI chatbot conversations per user."""
from datetime import datetime
from app import db


class ChatHistory(db.Model):
    __tablename__ = 'chat_history'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                           nullable=False, index=True)
    role       = db.Column(db.Enum('user', 'model'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {'role': self.role, 'content': self.content}
