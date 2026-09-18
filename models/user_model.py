"""
JobAgent - User & Auth Database Models
Enterprise-grade user management with proper indexing and security.
"""
from datetime import datetime, timedelta
from typing import Dict, Optional
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)

    # Relationships
    profile = db.relationship('UserProfile', uselist=False, back_populates='user', cascade='all, delete-orphan')
    saved_jobs = db.relationship('SavedJob', back_populates='user', cascade='all, delete-orphan')
    applications = db.relationship('JobApplication', back_populates='user', cascade='all, delete-orphan')
    interview_history = db.relationship('InterviewHistory', back_populates='user', cascade='all, delete-orphan')
    sessions = db.relationship('UserSession', back_populates='user', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', back_populates='user', cascade='all, delete-orphan')
    preference = db.relationship('UserPreference', uselist=False, backref='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        if self.locked_until and datetime.utcnow() < self.locked_until:
            return True
        return False

    def record_login_attempt(self, success=False):
        if success:
            self.login_attempts = 0
            self.locked_until = None
            self.last_login = datetime.utcnow()
        else:
            self.login_attempts += 1
            if self.login_attempts >= 5:
                self.locked_until = datetime.utcnow() + timedelta(minutes=15)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'username': self.username,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }


class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    full_name = db.Column(db.String(200), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(200), nullable=True)
    headline = db.Column(db.String(300), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    linkedin_url = db.Column(db.String(500), nullable=True)
    github_url = db.Column(db.String(500), nullable=True)
    portfolio_url = db.Column(db.String(500), nullable=True)
    avatar_url = db.Column(db.String(500), nullable=True)
    resume_file_path = db.Column(db.String(500), nullable=True)
    resume_text = db.Column(db.Text, nullable=True)
    theme_preference = db.Column(db.String(20), default='dark')
    preferred_roles = db.Column(db.Text, nullable=True)  # JSON array of roles
    skills = db.Column(db.Text, nullable=True)  # JSON array of skills
    experience_level = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='profile')

    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'phone': self.phone,
            'location': self.location,
            'headline': self.headline,
            'bio': self.bio,
            'linkedin_url': self.linkedin_url,
            'github_url': self.github_url,
            'portfolio_url': self.portfolio_url,
            'preferred_roles': self.preferred_roles,
            'skills': self.skills,
            'experience_level': self.experience_level,
        }


class SavedJob(db.Model):
    __tablename__ = 'saved_jobs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    role_title = db.Column(db.String(300), nullable=False)
    guide_data = db.Column(db.Text, nullable=True)  # JSON data
    company = db.Column(db.String(200), nullable=True)
    job_url = db.Column(db.String(1000), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default='saved')  # saved, applied, interviewing, offer, rejected
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', back_populates='saved_jobs')

    __table_args__ = (
        db.Index('idx_user_role', 'user_id', 'role_title'),
    )


class JobApplication(db.Model):
    __tablename__ = 'job_applications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    saved_job_id = db.Column(db.Integer, db.ForeignKey('saved_jobs.id', ondelete='SET NULL'), nullable=True)
    company = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(300), nullable=False)
    location = db.Column(db.String(200), nullable=True)
    job_url = db.Column(db.String(1000), nullable=True)
    salary_range = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='applied')  # applied, screening, interview, offer, rejected, accepted
    applied_date = db.Column(db.DateTime, default=datetime.utcnow)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    resume_used = db.Column(db.String(500), nullable=True)

    user = db.relationship('User', back_populates='applications')

    __table_args__ = (
        db.Index('idx_app_user_status', 'user_id', 'status'),
    )


class InterviewHistory(db.Model):
    __tablename__ = 'interview_history'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id', ondelete='SET NULL'), nullable=True)
    company = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(300), nullable=False)
    interview_type = db.Column(db.String(100), nullable=True)  # technical, hr, coding, behavioral, final
    interview_date = db.Column(db.DateTime, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True)
    questions_asked = db.Column(db.Text, nullable=True)  # JSON array
    feedback = db.Column(db.Text, nullable=True)
    rating = db.Column(db.Integer, nullable=True)  # 1-5
    status = db.Column(db.String(50), default='scheduled')  # scheduled, completed, cancelled, rescheduled
    notes = db.Column(db.Text, nullable=True)
    weak_areas = db.Column(db.Text, nullable=True)  # JSON array of skill/topic strings from practice sessions
    strong_areas = db.Column(db.Text, nullable=True)  # JSON array
    overall_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='interview_history')

    __table_args__ = (
        db.Index('idx_interview_user_date', 'user_id', 'interview_date'),
    )


class UserPreference(db.Model):
    __tablename__ = 'user_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    email_notifications = db.Column(db.Boolean, default=True)
    job_alerts = db.Column(db.Boolean, default=True)
    weekly_digest = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(20), default='dark')
    language = db.Column(db.String(10), default='en')
    search_radius_km = db.Column(db.Integer, default=50)
    preferred_locations = db.Column(db.Text, nullable=True)  # JSON array
    excluded_keywords = db.Column(db.Text, nullable=True)  # JSON array

    # ── Notification preferences (slot-based engine) ─────────────────
    timezone = db.Column(db.String(64), default='Asia/Kolkata', nullable=False)
    notification_slots = db.Column(db.String(100), default='8,12,17', nullable=False)
    notify_job_search = db.Column(db.Boolean, default=True, nullable=False)
    notify_new_skills = db.Column(db.Boolean, default=True, nullable=False)
    notify_indemand_skills = db.Column(db.Boolean, default=True, nullable=False)
    notify_resume = db.Column(db.Boolean, default=True, nullable=False)
    notify_interview = db.Column(db.Boolean, default=True, nullable=False)
    notify_tracker = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'timezone': self.timezone,
            'notification_slots': self.notification_slots,
            'notify_job_search': self.notify_job_search,
            'notify_new_skills': self.notify_new_skills,
            'notify_indemand_skills': self.notify_indemand_skills,
            'notify_resume': self.notify_resume,
            'notify_interview': self.notify_interview,
            'notify_tracker': self.notify_tracker,
            'email_notifications': self.email_notifications,
            'job_alerts': self.job_alerts,
            'weekly_digest': self.weekly_digest,
            'theme': self.theme,
            'language': self.language,
            'search_radius_km': self.search_radius_km,
        }


# ─── Lightweight schema upgrades ─────────────────────────────────────
# db.create_all() creates NEW tables but never adds columns to existing
# ones (e.g. a database created by an earlier deploy). This helper adds
# any missing columns with safe defaults. Works on SQLite and Postgres
# (both support ADD COLUMN).

("notify_job_search", "BOOLEAN DEFAULT TRUE NOT NULL"),
("notify_new_skills", "BOOLEAN DEFAULT TRUE NOT NULL"),
("notify_indemand_skills", "BOOLEAN DEFAULT TRUE NOT NULL"),
("notify_resume", "BOOLEAN DEFAULT TRUE NOT NULL"),
("notify_interview", "BOOLEAN DEFAULT TRUE NOT NULL"),
("notify_tracker", "BOOLEAN DEFAULT TRUE NOT NULL"),

_NOTIFICATION_COLUMNS = (
    ("read_at", "DATETIME NULL"),
)

_INTERVIEW_HISTORY_COLUMNS = (
    ("weak_areas", "TEXT NULL"),
    ("strong_areas", "TEXT NULL"),
    ("overall_score", "FLOAT NULL"),
)


def ensure_schema_upgrades(app) -> None:
    """Add columns introduced after the initial schema, if missing."""
    from sqlalchemy import inspect as sa_inspect, text
    with app.app_context():
        try:
            engine = db.engine
        except Exception:  # pragma: no cover - engine not ready
            return
        plan = (
            ('user_preferences', _PREFERENCE_COLUMNS),
            ('notifications', _NOTIFICATION_COLUMNS),
            ('interview_history', _INTERVIEW_HISTORY_COLUMNS),
        )
        for table, columns in plan:
            try:
                existing = {c['name'] for c in sa_inspect(engine).get_columns(table)}
            except Exception:
                continue
            for name, ddl in columns:
                if name in existing:
                    continue
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            'ALTER TABLE {0} ADD COLUMN {1} {2}'.format(
                                table, name, ddl)))
                    print('schema upgrade: added {0}.{1}'.format(table, name))
                except Exception as exc:  # pragma: no cover
                    print('schema upgrade skipped {0}.{1}: {2}'.format(
                        table, name, exc))



class UserSession(db.Model):
    __tablename__ = 'user_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    session_token = db.Column(db.String(256), unique=True, nullable=False, index=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='sessions')

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(64)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(100), nullable=False, index=True)
    resource_type = db.Column(db.String(100), nullable=True)
    resource_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)  # JSON data
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='audit_logs')

    __table_args__ = (
        db.Index('idx_audit_user_action', 'user_id', 'action'),
    )


class PasswordResetToken(db.Model):
    __tablename__ = 'password_reset_tokens'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    token = db.Column(db.String(256), unique=True, nullable=False, index=True)
    is_used = db.Column(db.Boolean, default=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @staticmethod
    def generate_token():
        return secrets.token_urlsafe(48)


class Feedback(db.Model):
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_helpful = db.Column(db.Integer, default=0)
    is_not_helpful = db.Column(db.Integer, default=0)
    status = db.Column(db.String(50), default='new')
    admin_response = db.Column(db.Text, nullable=True)
    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref='feedback')
    
    __table_args__ = (
        db.Index('idx_feedback_rating', 'rating'),
        db.Index('idx_feedback_created', 'created_at'),
        db.Index('idx_feedback_status', 'status'),
    )


class CareerInsightCache(db.Model):
    __tablename__ = 'career_insight_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    role_key = db.Column(db.String(200), unique=True, nullable=False, index=True)
    data = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    @staticmethod
    def get(role_key: str) -> Optional[Dict]:
        cached = CareerInsightCache.query.filter(
            CareerInsightCache.role_key == role_key,
            CareerInsightCache.expires_at > datetime.utcnow()
        ).first()
        
        if cached:
            return json.loads(cached.data)
        return None
    
    @staticmethod
    def set(role_key: str, data: Dict, source: str = 'internal', ttl_hours: int = 24):
        existing = CareerInsightCache.query.filter_by(role_key=role_key).first()
        
        expires_at = datetime.utcnow() + timedelta(hours=ttl_hours)
        
        if existing:
            existing.data = json.dumps(data)
            existing.source = source
            existing.expires_at = expires_at
            existing.updated_at = datetime.utcnow()
        else:
            cached = CareerInsightCache(
                role_key=role_key,
                data=json.dumps(data),
                source=source,
                expires_at=expires_at
            )
            db.session.add(cached)
        
        db.session.commit()


class Notification(db.Model):
    """In-app re-engagement notifications: new matching jobs, interview
    prep reminders, etc. Generated lazily (no background scheduler yet)
    whenever a user's notifications are fetched - see
    services/notifications/engine.py. is_sent/sent_at are already here
    for when an email/push channel gets added later (see the note at
    the bottom of engine.py)."""
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(300), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link_url = db.Column(db.String(1000), nullable=True)
    dedupe_key = db.Column(db.String(300), nullable=True)  # prevents re-notifying the same job/event
    data = db.Column(db.Text, nullable=True)
    is_read = db.Column(db.Boolean, default=False, index=True)
    is_sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', backref='notifications')
    
    __table_args__ = (
        db.Index('idx_notification_user_read', 'user_id', 'is_read'),
        db.Index('idx_notification_user_dedupe', 'user_id', 'dedupe_key'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'title': self.title,
            'message': self.message,
            'link_url': self.link_url,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class InterviewSession(db.Model):
    """Conversational interview session."""
    __tablename__ = 'interview_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    anon_session_id = db.Column(db.String(64), nullable=True, index=True)
    target_role = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=True)
    job_id = db.Column(db.Integer, nullable=True)
    job_description = db.Column(db.Text, nullable=True)
    resume_version_id = db.Column(db.String(64), nullable=True)
    experience_level = db.Column(db.String(20), default='mid')
    interview_mode = db.Column(db.String(20), default='standard')
    status = db.Column(db.String(20), default='active')
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    question_count = db.Column(db.Integer, default=0)
    turn_count = db.Column(db.Integer, default=0)
    overall_score = db.Column(db.Float, nullable=True)
    current_topic = db.Column(db.String(100), nullable=True)
    current_skill = db.Column(db.String(200), nullable=True)
    difficulty = db.Column(db.String(20), default='medium')
    state_json = db.Column(db.Text, nullable=True)

    messages = db.relationship('InterviewMessage', backref='session', cascade='all, delete-orphan', lazy='dynamic')

    __table_args__ = (
        db.Index('idx_interview_session_user', 'user_id', 'status'),
    )


class InterviewMessage(db.Model):
    """Individual message in an interview conversation."""
    __tablename__ = 'interview_messages'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('interview_sessions.id', ondelete='CASCADE'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'interviewer' or 'candidate'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    question_type = db.Column(db.String(50), nullable=True)
    question_id = db.Column(db.String(64), nullable=True)
    evaluation_json = db.Column(db.Text, nullable=True)
    token_count = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        db.Index('idx_interview_msg_session', 'session_id', 'timestamp'),
    )


class Analytics(db.Model):
    __tablename__ = 'analytics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    event_type = db.Column(db.String(100), nullable=False, index=True)
    event_data = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    user_agent = db.Column(db.String(500), nullable=True)
    session_id = db.Column(db.String(100), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    user = db.relationship('User', backref='analytics')
    
    __table_args__ = (
        db.Index('idx_analytics_event_type', 'event_type', 'created_at'),
    )
