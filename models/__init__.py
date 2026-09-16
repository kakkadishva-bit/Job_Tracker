"""Data models for Job Agent"""
from models.user_model import db, User, UserProfile, UserPreference, SavedJob, JobApplication, InterviewHistory, AuditLog, PasswordResetToken, Feedback, CareerInsightCache, Notification, Analytics, UserSession
from models.job_model import Job
from models.chat_model import ChatMessage, ChatUserStatus