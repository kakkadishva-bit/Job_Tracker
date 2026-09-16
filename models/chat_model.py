"""
JobAgent - Chat Database Models
Group chat for logged-in users with privacy policy enforcement.
"""
from datetime import datetime
from models.user_model import db


class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(20), default='text')  # text, system, feedback
    is_flagged = db.Column(db.Boolean, default=False)
    flag_reason = db.Column(db.String(500), nullable=True)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='chat_messages')

    __table_args__ = (
        db.Index('idx_chat_created', 'created_at'),
        db.Index('idx_chat_user', 'user_id', 'created_at'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else 'Unknown',
            'message': self.message,
            'message_type': self.message_type,
            'is_flagged': self.is_flagged,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ChatUserStatus(db.Model):
    __tablename__ = 'chat_user_status'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    has_accepted_policy = db.Column(db.Boolean, default=False)
    accepted_at = db.Column(db.DateTime, nullable=True)
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(500), nullable=True)
    banned_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='chat_status')

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'has_accepted_policy': self.has_accepted_policy,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'is_banned': self.is_banned,
            'ban_reason': self.ban_reason,
        }