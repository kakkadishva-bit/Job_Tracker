"""
services/notifications/engine.py

In-app-only notification generation (no email/push infra exists yet -
see the note at the bottom of this file for how to extend it later).

Because there's no background scheduler (no Celery/APScheduler in this
project), notifications are generated lazily: every time a logged-in
user hits GET /api/notifications, we run these checks, write any new
rows, and return the full unread list. This means a user only "sees" a
new-job alert or interview reminder the next time they open the app -
that's an honest MVP limitation, not a silent bug, and is called out
explicitly in the chat response this was built from.
"""
import json
from datetime import datetime, timedelta
from typing import List

from models.user_model import db, Notification, InterviewHistory, UserProfile
from services.jobs.job_search_service import search_jobs
from utils.logger import get_logger

logger = get_logger()

INTERVIEW_REMINDER_WINDOW_HOURS = 48
MAX_NEW_JOB_NOTIFICATIONS_PER_RUN = 3
JOB_MATCH_LOOKUP_LIMIT = 15


def generate_notifications_for_user(user) -> int:
    """Runs all checks for one user, persists any new notifications,
    and returns how many were newly created this run."""
    created = 0
    try:
        created += _check_interview_reminders(user)
    except Exception as exc:  # pragma: no cover - one bad check shouldn't break the others
        logger.warning("Interview reminder check failed for user %s: %s", user.id, exc)
    try:
        created += _check_new_matching_jobs(user)
    except Exception as exc:  # pragma: no cover
        logger.warning("New-job-match check failed for user %s: %s", user.id, exc)

    if created:
        db.session.commit()
    return created


def _already_notified(user_id: int, dedupe_key: str) -> bool:
    return db.session.query(Notification.id).filter_by(
        user_id=user_id, dedupe_key=dedupe_key
    ).first() is not None


def _check_interview_reminders(user) -> int:
    """Notifies about interviews scheduled in the next 48 hours."""
    window_end = datetime.utcnow() + timedelta(hours=INTERVIEW_REMINDER_WINDOW_HOURS)
    upcoming = InterviewHistory.query.filter(
        InterviewHistory.user_id == user.id,
        InterviewHistory.status == 'scheduled',
        InterviewHistory.interview_date.isnot(None),
        InterviewHistory.interview_date >= datetime.utcnow(),
        InterviewHistory.interview_date <= window_end,
    ).all()

    created = 0
    for interview in upcoming:
        dedupe_key = f"interview_reminder:{interview.id}"
        if _already_notified(user.id, dedupe_key):
            continue
        when = interview.interview_date.strftime("%a %b %d, %I:%M %p")
        db.session.add(Notification(
            user_id=user.id,
            type='interview_reminder',
            title=f"Upcoming interview: {interview.role} at {interview.company}",
            message=f"Your {interview.interview_type or ''} interview is on {when}. "
                    f"Want to run a mock interview to prepare?",
            link_url="/interview-prep",
            dedupe_key=dedupe_key,
        ))
        created += 1
    return created


def _check_new_matching_jobs(user) -> int:
    """Notifies about fresh postings matching the user's saved preferred roles."""
    profile: UserProfile = user.profile
    if not profile or not profile.preferred_roles:
        return 0

    try:
        roles: List[str] = json.loads(profile.preferred_roles)
    except (json.JSONDecodeError, TypeError):
        return 0
    if not roles:
        return 0

    created = 0
    for role in roles[:2]:  # cap roles checked per run to keep this fast
        if created >= MAX_NEW_JOB_NOTIFICATIONS_PER_RUN:
            break
        result = search_jobs(
            role,
            location=profile.location or "",
            limit=JOB_MATCH_LOOKUP_LIMIT,
            include_slow_sources=False,  # keep this check fast; it runs on every page load
            max_age_days=3,  # only care about genuinely new postings here
        )
        for job in result["jobs"]:
            if created >= MAX_NEW_JOB_NOTIFICATIONS_PER_RUN:
                break
            if job.get("freshness_label") not in ("New today", "1 day ago"):
                continue
            dedupe_key = f"new_job:{job.get('job_url')}"
            if not job.get("job_url") or _already_notified(user.id, dedupe_key):
                continue
            db.session.add(Notification(
                user_id=user.id,
                type='new_job_match',
                title=f"New: {job['job_title']} at {job['company_name']}",
                message=f"A new {job['job_title']} posting matching your saved role "
                        f"'{role}' just went up on {job.get('source', 'a job board')}.",
                link_url=job.get("job_url"),
                dedupe_key=dedupe_key,
            ))
            created += 1
    return created


# ── Extending to email/push later ───────────────────────────────────
# The Notification row already carries everything an email/push sender
# would need (title, message, link_url). To add a channel later:
#   1. Add UserPreference.email_notifications (already exists!) as the
#      opt-in check.
#   2. Add a delivery function that queries unsent Notifications and
#      sends them via SMTP or a push provider.
#   3. Run generate_notifications_for_user() + delivery on a schedule
#      (APScheduler or a cron-triggered script) instead of lazily on
#      page load - that's the only way to reach a user who isn't
#      currently in the app.
