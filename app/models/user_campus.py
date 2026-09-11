"""
User-Campus junction table — allows staff and admin users
to be assigned to multiple campuses.
"""
from app import db


class UserCampus(db.Model):
    """Many-to-many: a staff/admin user can manage multiple campuses."""
    __tablename__ = 'user_campuses'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    campus_id  = db.Column(db.Integer, db.ForeignKey('campuses.id'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'campus_id', name='uq_user_campus'),
    )

    def __repr__(self):
        return f'<UserCampus user={self.user_id} campus={self.campus_id}>'
