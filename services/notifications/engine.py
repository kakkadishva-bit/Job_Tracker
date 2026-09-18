"""
services/notifications/engine.py

Slot-based in-app notification generation (no email/push infra exists yet).

Scheduling model
----------------
Notifications are generated for three daily slots: 08:00, 12:00 and 17:00
in the user's configured timezone (default Asia/Kolkata). Generation is
IDEMPOTENT:

- every check writes notifications with a dedupe_key (unique per user),
  so re-running a slot never duplicates anything;
- daily digest checks embed the date in their dedupe key, so they run at
  most once per day even if several slots trigger them;
- if there is no real data for a check (no saved roles, no stale
  applications, no live postings), it simply produces nothing - we never
  fabricate filler notifications to fill a slot.

Everything is derived from real application data: live postings come from
services.jobs.job_search_service (real Adzuna/JSearch/RemoteOK queries),
demand percentages come from services.market.demand_analyzer over those
real postings, and tracker/interview/resume checks read the user's own
DB rows. If a source returns nothing, no notification is created.

Deployment note: an in-process scheduler thread (scheduler.py) covers
always-on deployments; for environments that spin workers down, run
``python schedule_notifications.py`` from a cron job - both call
generate_due_notifications_for_all_users() and are safe to run
concurrently (dedupe keys make every run idempotent).
"""
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:  # Python 3.9+: real IANA zones when the tzdata database is available
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

from models.user_model import (
    db, Notification, InterviewHistory, UserProfile, SavedJob, JobApplication,
)
from services.jobs.job_search_service import search_jobs
from services.market.demand_analyzer import (
    analyze_skill_demand, _skills_mentioned_in_text,
)
from utils.logger import get_logger


from services.notifications.checks import (
    check_new_matching_jobs_and_skills as _check_new_matching_jobs_and_skills,
    check_indemand_skills as _check_indemand_skills,
    check_resume_analysis as _check_resume_analysis,
    check_interview_prep as _check_interview_prep,
    check_tracker as _check_tracker,
)

logger = get_logger()

DEFAULT_TIMEZONE = 'Asia/Kolkata'
DEFAULT_SLOT_HOURS = (8, 12, 17)

INTERVIEW_REMINDER_WINDOW_HOURS = 48
MAX_NEW_JOB_NOTIFICATIONS_PER_RUN = 3
JOB_MATCH_LOOKUP_LIMIT = 15
DEMAND_SAMPLE_SIZE = 20
STALE_APPLICATION_DAYS = 7
STALE_SAVED_JOB_DAYS = 7
RESUME_REANALYZE_DAYS = 14
MAX_PREF_ROLES_PER_RUN = 2

# Fallback offsets (UTC) used only when zoneinfo/tzdata is unavailable
# on the host. Asia/Kolkata has no DST so this mapping is exact there;
# zones with DST are approximated and zoneinfo is preferred.
_TZ_FALLBACK_OFFSETS = {
    'Asia/Kolkata': timedelta(hours=5, minutes=30),
    'Asia/Calcutta': timedelta(hours=5, minutes=30),
    'UTC': timedelta(0),
    'Etc/UTC': timedelta(0),
    'Asia/Dubai': timedelta(hours=4),
    'Europe/London': timedelta(0),
    'America/New_York': timedelta(hours=-5),
    'America/Los_Angeles': timedelta(hours=-8),
    'Asia/Tokyo': timedelta(hours=9),
}


# ─── Timezone & slot helpers (pure, unit-testable) ───────────────────

def local_now(tz_name: Optional[str], now_utc: Optional[datetime] = None) -> datetime:
    """Naive wall-clock datetime in the given IANA zone."""
    tz_name = (tz_name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    if now_utc is None:
        if ZoneInfo is not None:
            try:
                return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
            except Exception:
                pass
        now_utc = datetime.utcnow()
    else:
        now_utc = now_utc.replace(tzinfo=None)
    return _shift(now_utc, tz_name)


def _shift(now_utc: datetime, tz_name: str) -> datetime:
    """Convert a naive-UTC datetime to zone-local naive time."""
    if ZoneInfo is not None:
        try:
            zone = ZoneInfo(tz_name)
            aware = now_utc.replace(tzinfo=ZoneInfo('UTC'))
            return aware.astimezone(zone).replace(tzinfo=None)
        except Exception:
            pass
    offset = _TZ_FALLBACK_OFFSETS.get(tz_name)
    if offset is None:
        offset = _TZ_FALLBACK_OFFSETS[DEFAULT_TIMEZONE]
    return now_utc + offset


def user_timezone(user) -> str:
    """The user's configured timezone, defaulting to Asia/Kolkata."""
    pref = getattr(user, 'preference', None)
    tz = getattr(pref, 'timezone', None) if pref is not None else None
    return (tz or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE


def user_slots(user) -> tuple:
    """The notification hours (0-23) the user opted into."""
    pref = getattr(user, 'preference', None)
    raw = getattr(pref, 'notification_slots', None) if pref is not None else None
    if not raw:
        return DEFAULT_SLOT_HOURS
    slots = []
    for part in str(raw).split(','):
        part = part.strip()
        if part.isdigit() and 0 <= int(part) <= 23:
            slots.append(int(part))
    return tuple(sorted(set(slots))) or DEFAULT_SLOT_HOURS


def current_slot_hour(now_local: datetime,
                      slots=DEFAULT_SLOT_HOURS) -> Optional[int]:
    """The latest slot that has already passed today, or None if none has.

    e.g. slots=(8,12,17): at 09:20 -> 8, at 13:05 -> 12, at 07:00 -> None.
    """
    for hour in sorted(slots, reverse=True):
        if now_local.hour >= hour:
            return hour
    return None


def _pref_flag(user, attr: str) -> bool:
    pref = getattr(user, 'preference', None)
    value = getattr(pref, attr, None) if pref is not None else None
    return True if value is None else bool(value)



# ─── Core entry points ────────────────────────────────────────────────

def generate_notifications_for_user(user, slot_hour=None, now_utc=None) -> int:
    """Run all due checks for one user; returns how many rows were added.

    slot_hour=None means "the slot that is currently due in the user's
    timezone" (nothing runs before the first slot of the day). Passing an
    explicit slot is used by tests and by the cron entry point.
    """
    tz_name = user_timezone(user)
    now_local = local_now(tz_name, now_utc)
    slot = slot_hour if slot_hour is not None else current_slot_hour(
        now_local, user_slots(user))
    if slot is None:
        return 0

    created = 0
    checks = (
        _check_interview_reminders,
        _check_new_matching_jobs_and_skills,
        _check_indemand_skills,
        _check_resume_analysis,
        _check_interview_prep,
        _check_tracker,
    )
    for check in checks:
        try:
            created += check(user, now_local=now_local, slot=slot)
        except Exception as exc:  # one bad check must not break the others
            logger.warning("Notification check %s failed for user %s: %s",
                           check.__name__, user.id, exc)

    if created:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            logger.warning("Notification commit failed for user %s", user.id)
    return created


def generate_due_notifications_for_all_users(app=None, now_utc=None) -> int:
    """Scheduler entry point: generate due notifications for every active
    user. Idempotent - safe to run concurrently or repeatedly."""
    from models.user_model import User
    users = User.query.filter_by(is_active=True).all()
    total = 0
    for user in users:
        try:
            total += generate_notifications_for_user(user, now_utc=now_utc)
        except Exception as exc:  # pragma: no cover
            logger.warning("Slot generation failed for user %s: %s", user.id, exc)
    return total


def _already_notified(user_id: int, dedupe_key: str) -> bool:
    return db.session.query(Notification.id).filter_by(
        user_id=user_id, dedupe_key=dedupe_key
    ).first() is not None


def _add_notification(user_id, ntype, title, message, link_url,
                      dedupe_key, data=None) -> bool:
    """Insert a notification unless its dedupe_key already exists for the
    user. Returns True when a row was actually created."""
    if _already_notified(user_id, dedupe_key):
        return False
    db.session.add(Notification(
        user_id=user_id,
        type=ntype,
        title=(title or '')[:300],
        message=message,
        link_url=(link_url or '')[:1000] or None,
        dedupe_key=(dedupe_key or '')[:300],
        data=json.dumps(data) if data else None,
    ))
    return True


def _pref_roles(profile):
    if not profile or not profile.preferred_roles:
        return []
    try:
        roles = json.loads(profile.preferred_roles)
    except (json.JSONDecodeError, TypeError):
        return []
    return [r for r in roles if isinstance(r, str) and r.strip()]


def _profile_skills(profile):
    if not profile or not profile.skills:
        return set()
    try:
        skills = json.loads(profile.skills)
    except (json.JSONDecodeError, TypeError):
        return set()
    return {str(s).strip().lower() for s in skills if str(s).strip()}


def _already_notified(user_id: int, dedupe_key: str) -> bool:
    return db.session.query(Notification.id).filter_by(
        user_id=user_id, dedupe_key=dedupe_key
    ).first() is not None


def _check_interview_reminders(user, now_local=None, slot=None) -> int:
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
