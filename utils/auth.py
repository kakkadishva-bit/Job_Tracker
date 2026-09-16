"""
JobAgent - Authentication Utilities
Enterprise-grade auth with session management, rate limiting, and security.
"""
import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from flask import request, session, current_app
from email_validator import validate_email, EmailNotValidError

from models.user_model import (
    db, User, UserProfile, UserPreference, UserSession,
    AuditLog, PasswordResetToken
)


# ─── Password Validation ──────────────────────────────────────────────

def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    Returns (is_valid, message).
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if len(password) > 128:
        return False, "Password must be less than 128 characters"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;~`]', password):
        return False, "Password must contain at least one special character"
    # Check for common patterns
    common_patterns = ['password', '123456', 'qwerty', 'abc123', 'letmein', 'admin']
    if any(p in password.lower() for p in common_patterns):
        return False, "Password contains a common pattern. Choose something more unique"
    return True, "Password is strong"


def validate_email_address(email: str) -> Tuple[bool, str]:
    """
    Validate email format.
    Returns (is_valid, message).
    """
    try:
        validated = validate_email(email, check_deliverability=False)
        return True, validated.email
    except EmailNotValidError as e:
        return False, str(e)


def sanitize_input(text: str) -> str:
    """Santize user input to prevent XSS."""
    if not text:
        return ""
    # Strip HTML tags
    text = re.sub(r'<[^>]*>', '', text)
    # Remove script tags
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    # Remove event handlers
    text = re.sub(r'\bon\w+\s*=\s*["\'][^"\']*["\']', '', text, flags=re.IGNORECASE)
    return text.strip()


def sanitize_json(data: Any) -> Any:
    """Recursively sanitize JSON data."""
    if isinstance(data, str):
        return sanitize_input(data)
    elif isinstance(data, dict):
        return {k: sanitize_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json(item) for item in data]
    return data


# ─── Account Management ───────────────────────────────────────────────

def create_user_account(email: str, username: str, password: str) -> Tuple[bool, str, Optional[User]]:
    """
    Create a new user account with profile and preferences.
    Returns (success, message, user_object).
    """
    # Validate email
    valid_email, email_msg = validate_email_address(email)
    if not valid_email:
        return False, f"Invalid email: {email_msg}", None

    # Validate password
    valid_pw, pw_msg = validate_password(password)
    if not valid_pw:
        return False, pw_msg, None

    # Validate username
    username = sanitize_input(username).strip()
    if len(username) < 3:
        return False, "Username must be at least 3 characters", None
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores", None

    # Check for existing user
    existing = User.query.filter(
        (User.email == email) | (User.username == username)
    ).first()
    if existing:
        if existing.email == email:
            return False, "An account with this email already exists", None
        return False, "This username is already taken", None

    # Create user
    user = User(
        email=email.lower().strip(),
        username=username,
        is_verified=True  # Auto-verified for now (email verification can be added)
    )
    user.set_password(password)

    try:
        db.session.add(user)
        db.session.flush()  # Get user.id

        # Create profile
        profile = UserProfile(
            user_id=user.id,
            full_name=username
        )
        db.session.add(profile)

        # Create preferences
        prefs = UserPreference(user_id=user.id)
        db.session.add(prefs)

        # Create session record
        user_session = UserSession(
            user_id=user.id,
            session_token=UserSession.generate_token(),
            ip_address=request.remote_addr or '0.0.0.0',
            user_agent=request.user_agent.string if request.user_agent else None,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(user_session)

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action='account_created',
            resource_type='user',
            resource_id=user.id,
            details=json.dumps({'email': email, 'username': username}),
            ip_address=request.remote_addr or '0.0.0.0',
            user_agent=request.user_agent.string if request.user_agent else None
        )
        db.session.add(audit)

        db.session.commit()
        return True, "Account created successfully!", user

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create user account: {str(e)}")
        return False, "An error occurred while creating your account. Please try again.", None


def authenticate_user(email: str, password: str, remember: bool = False) -> Tuple[bool, str, Optional[User]]:
    """
    Authenticate a user with email and password.
    Handles rate limiting and account locking.
    """
    email = email.lower().strip()
    user = User.query.filter_by(email=email).first()

    if not user:
        return False, "No account found with this email address", None

    if not user.is_active:
        return False, "This account has been deactivated. Please contact support.", None

    if user.is_locked():
        remaining = (user.locked_until - datetime.utcnow()).seconds // 60
        return False, f"Account is temporarily locked due to too many failed attempts. Try again in {remaining} minutes.", None

    if user.check_password(password):
        # Successful login
        user.record_login_attempt(success=True)

        # Create or update session
        user_session = UserSession(
            user_id=user.id,
            session_token=UserSession.generate_token(),
            ip_address=request.remote_addr or '0.0.0.0',
            user_agent=request.user_agent.string if request.user_agent else None,
            expires_at=datetime.utcnow() + timedelta(days=30 if remember else 1),
            is_active=True
        )
        db.session.add(user_session)

        # Audit log
        audit = AuditLog(
            user_id=user.id,
            action='login',
            resource_type='user',
            resource_id=user.id,
            details=json.dumps({'remember': remember}),
            ip_address=request.remote_addr or '0.0.0.0'
        )
        db.session.add(audit)
        db.session.commit()

        return True, "Login successful!", user

    else:
        # Failed attempt
        user.record_login_attempt(success=False)
        db.session.commit()

        remaining_attempts = 5 - user.login_attempts
        if remaining_attempts > 0:
            return False, f"Invalid password. {remaining_attempts} attempt(s) remaining before account is locked.", None
        else:
            return False, "Account has been locked for 15 minutes due to too many failed attempts.", None


def logout_user_session(user: User) -> bool:
    """Log out user by deactivating active sessions."""
    try:
        UserSession.query.filter_by(user_id=user.id, is_active=True).update({'is_active': False})
        audit = AuditLog(
            user_id=user.id,
            action='logout',
            resource_type='user',
            resource_id=user.id,
            ip_address=request.remote_addr or '0.0.0.0'
        )
        db.session.add(audit)
        db.session.commit()

        # Clear Flask session
        session.clear()
        return True
    except Exception as e:
        current_app.logger.error(f"Logout error: {str(e)}")
        db.session.rollback()
        return False


def initiate_password_reset(email: str) -> Tuple[bool, str]:
    """
    Initiate password reset flow.
    Returns (success, message).
    """
    user = User.query.filter_by(email=email.lower().strip()).first()
    if not user:
        # Don't reveal if email exists (security best practice)
        return True, "If an account exists with this email, you will receive a password reset link."

    # Invalidate old tokens
    PasswordResetToken.query.filter_by(user_id=user.id, is_used=False).update({'is_used': True})

    # Create new token
    token = PasswordResetToken.generate_token()
    reset = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.utcnow() + timedelta(hours=1)
    )
    db.session.add(reset)

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action='password_reset_requested',
        resource_type='user',
        resource_id=user.id,
        ip_address=request.remote_addr or '0.0.0.0'
    )
    db.session.add(audit)
    db.session.commit()

    # In production, send email here with the reset link
    # For now, we log the token
    current_app.logger.info(f"Password reset token for {email}: {token}")

    return True, "If an account exists with this email, you will receive a password reset link."


def reset_password(token: str, new_password: str) -> Tuple[bool, str]:
    """
    Reset password using a valid token.
    """
    reset = PasswordResetToken.query.filter_by(token=token, is_used=False).first()
    if not reset:
        return False, "Invalid or expired reset token."

    if datetime.utcnow() > reset.expires_at:
        return False, "Reset token has expired. Please request a new one."

    # Validate password
    valid_pw, pw_msg = validate_password(new_password)
    if not valid_pw:
        return False, pw_msg

    user = User.query.get(reset.user_id)
    if not user:
        return False, "User not found."

    user.set_password(new_password)
    user.login_attempts = 0
    user.locked_until = None
    reset.is_used = True

    # Invalidate all sessions
    UserSession.query.filter_by(user_id=user.id, is_active=True).update({'is_active': False})

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action='password_reset_completed',
        resource_type='user',
        resource_id=user.id,
        ip_address=request.remote_addr or '0.0.0.0'
    )
    db.session.add(audit)
    db.session.commit()

    return True, "Password has been reset successfully. You can now log in with your new password."


def get_user_by_id(user_id: int) -> Optional[User]:
    """Get user by ID."""
    return User.query.get(user_id)


def get_user_dashboard_data(user: User) -> Dict[str, Any]:
    """Get comprehensive dashboard data for a user."""
    from models.user_model import SavedJob, JobApplication, InterviewHistory

    saved_jobs = SavedJob.query.filter_by(user_id=user.id).order_by(SavedJob.saved_at.desc()).all()
    applications = JobApplication.query.filter_by(user_id=user.id).order_by(JobApplication.applied_date.desc()).all()
    interviews = InterviewHistory.query.filter_by(user_id=user.id).order_by(InterviewHistory.created_at.desc()).all()

    # Stats
    stats = {
        'total_saved': len(saved_jobs),
        'total_applications': len(applications),
        'total_interviews': len(interviews),
        'active_applications': sum(1 for a in applications if a.status in ('applied', 'screening', 'interview')),
        'offers': sum(1 for a in applications if a.status in ('offer', 'accepted')),
    }

    return {
        'user': user.to_dict(),
        'profile': user.profile.to_dict() if user.profile else {},
        'stats': stats,
        'saved_jobs': [{
            'id': j.id,
            'role_title': j.role_title,
            'company': j.company,
            'status': j.status,
            'saved_at': j.saved_at.isoformat() if j.saved_at else None,
        } for j in saved_jobs],
        'applications': [{
            'id': a.id,
            'company': a.company,
            'role': a.role,
            'status': a.status,
            'applied_date': a.applied_date.isoformat() if a.applied_date else None,
        } for a in applications],
        'interviews': [{
            'id': i.id,
            'company': i.company,
            'role': i.role,
            'type': i.interview_type,
            'date': i.interview_date.isoformat() if i.interview_date else None,
            'status': i.status,
        } for i in interviews],
    }