"""
services/notifications/checks.py

Individual notification category checks. Every function returns the number
of Notification rows it created and ONLY uses real application data:

- Category 1 JOB SEARCHING   : real live postings for the user's saved
                               preferred roles (services.jobs.job_search_service)
- Category 2 NEW SKILLS      : evidence-based skill extraction over those
                               real postings, diffed against profile skills
- Category 3 IN-DEMAND SKILLS: real ranked demand data
                               (services.market.demand_analyzer)
- Category 4 RESUME ANALYSIS : the user's own profile resume state
- Category 5 INTERVIEW PREP  : the user's own InterviewHistory weak areas
- Category 6 JOB TRACKER     : the user's own JobApplication/SavedJob rows

No function ever invents jobs, companies, salaries, URLs, skills or
statistics. If the underlying data is missing, it creates nothing.
"""
import json
from datetime import datetime, timedelta

from models.user_model import (
    db, InterviewHistory, SavedJob, JobApplication,
)
from services.jobs.job_search_service import search_jobs
from services.market.demand_analyzer import (
    analyze_skill_demand, _skills_mentioned_in_text,
)
from utils.logger import get_logger

logger = get_logger()

MAX_NEW_JOB_NOTIFICATIONS_PER_RUN = 3
JOB_MATCH_LOOKUP_LIMIT = 15
DEMAND_SAMPLE_SIZE = 20
STALE_APPLICATION_DAYS = 7
STALE_SAVED_JOB_DAYS = 7
RESUME_REANALYZE_DAYS = 14
MAX_PREF_ROLES_PER_RUN = 2


def _today(now_local):
    return (now_local or datetime.utcnow()).strftime('%Y-%m-%d')


def _roles_of(user):
    """Import-free access to the shared helpers on the engine module."""
    from services.notifications.engine import _pref_roles
    return _pref_roles(user.profile)


def _flag(user, attr):
    from services.notifications.engine import _pref_flag
    return _pref_flag(user, attr)


def _note(user, ntype, title, message, link_url, dedupe_key, data=None):
    from services.notifications.engine import _add_notification
    return _add_notification(user.id, ntype, title, message, link_url,
                             dedupe_key, data)


# ─── Category 1+2: job searching & new skills (live, real data) ──────

def check_new_matching_jobs_and_skills(user, now_local=None, slot=None) -> int:
    """New postings for the user's saved preferred roles (real live
    search), plus genuinely-new skills those real postings ask for."""
    profile = user.profile
    roles = _roles_of(user)
    if not roles or not _flag(user, 'notify_job_search'):
        return 0

    today = _today(now_local)
    from services.notifications.engine import _profile_skills, _already_notified
    known_skills = _profile_skills(profile)
    created = 0
    new_skills_seen = {}

    for role in roles[:MAX_PREF_ROLES_PER_RUN]:
        if created >= MAX_NEW_JOB_NOTIFICATIONS_PER_RUN:
            break
        result = search_jobs(
            role,
            location=(profile.location or '') if profile else '',
            limit=JOB_MATCH_LOOKUP_LIMIT,
            include_slow_sources=False,  # keep runs fast
            max_age_days=3,
        )
        for job in result.get('jobs', []):
            if created >= MAX_NEW_JOB_NOTIFICATIONS_PER_RUN:
                break
            url = job.get('job_url')
            if not url:
                continue
            dedupe_key = "new_job:" + url
            already = _already_notified(user.id, dedupe_key)
            if not already and job.get('freshness_label') in ('New today', '1 day ago'):
                if _note(
                    user,
                    'new_job_match',
                    "New: " + job['job_title'] + " at " + job['company_name'],
                    "A new " + job['job_title'] + " posting matching your saved role "
                    "'" + role + "' just went up on " +
                    job.get('source', 'a job board') + ".",
                    url,
                    dedupe_key,
                ):
                    created += 1

            # NEW SKILLS: evidence-based extraction over the real posting text.
            if _flag(user, 'notify_new_skills'):
                text = job.get('job_title', '') + ' ' + job.get('description', '')
                for skill in _skills_mentioned_in_text(text):
                    if skill.lower() not in known_skills:
                        new_skills_seen[skill] = new_skills_seen.get(skill, 0) + 1

    if new_skills_seen and _flag(user, 'notify_new_skills'):
        top = sorted(new_skills_seen.items(), key=lambda kv: -kv[1])[:3]
        names = ', '.join(s for s, _ in top)
        postings = top[0][1]
        if _note(
            user,
            'new_skill',
            "Skills appearing in " + roles[0] + " postings",
            "Real " + roles[0] + " postings from the last few days mention " +
            names + " (" + str(postings) + " posting" +
            ("s" if postings != 1 else "") + " asked for " + top[0][0] +
            ") and your profile does not list them yet.",
            '/resume',
            "new_skills:" + today + ":" + roles[0].lower(),
        ):
            created += 1
    return created


# ─── Category 3: in-demand skills (real ranked demand data) ──────────

def check_indemand_skills(user, now_local=None, slot=None) -> int:
    """Top skills by real mention counts from live postings for the
    user's first preferred role - at most once per day."""
    profile = user.profile
    roles = _roles_of(user)
    if not roles or not _flag(user, 'notify_indemand_skills'):
        return 0
    today = _today(now_local)
    role = roles[0]
    from services.notifications.engine import _already_notified
    dedupe_key = "indemand:" + today + ":" + role.lower()
    if _already_notified(user.id, dedupe_key):
        return 0  # avoid even re-querying live sources within the same day

    demand = analyze_skill_demand(
        role, location=(profile.location or '') if profile else '',
        sample_size=DEMAND_SAMPLE_SIZE, include_slow_sources=False)
    ranked = [s for s in demand.get('in_demand_skills', [])
              if s.get('postings_mentioning', 0) > 0][:3]
    if not ranked:
        return 0  # no real postings -> no fabricated demand claims

    summary = '; '.join(
        s['skill'] + " (" + str(s['postings_mentioning']) + "/" +
        str(demand.get('sample_size')) + " postings)"
        for s in ranked)
    if _note(
        user,
        'indemand_skill',
        "Top skills in real " + role + " postings",
        "From " + str(demand.get('sample_size')) + " live postings: " +
        summary + ".",
        '/search',
        dedupe_key,
        data={'skills': [s['skill'] for s in ranked]},
    ):
        return 1
    return 0


# ─── Category 4: resume analysis (real profile state) ────────────────

def check_resume_analysis(user, now_local=None, slot=None) -> int:
    """Reminder when the stored resume is stale, or when the user tracks
    roles without ever having analyzed a resume."""
    if not _flag(user, 'notify_resume'):
        return 0
    profile = user.profile
    today = _today(now_local)
    created = 0

    resume_text = getattr(profile, 'resume_text', None) if profile else None
    if resume_text and resume_text.strip():
        updated = getattr(profile, 'updated_at', None)
        if updated and now_local is not None:
            days = (now_local.date() - updated.date()).days
            if days >= RESUME_REANALYZE_DAYS:
                if _note(
                    user,
                    'resume_analysis',
                    'Time to re-analyze your resume',
                    "Your resume was last updated " + str(days) + " days ago. "
                    "Re-run the ATS analysis to refresh your score and "
                    "skill gaps.",
                    '/resume',
                    "resume_reanalyze:" + today,
                ):
                    created += 1
    else:
        has_saved = db.session.query(SavedJob.id).filter_by(
            user_id=user.id).first() is not None
        has_apps = db.session.query(JobApplication.id).filter_by(
            user_id=user.id).first() is not None
        if has_saved or has_apps:
            if _note(
                user,
                'resume_analysis',
                'Analyze your resume to unlock skill-gap matching',
                "You have saved roles but no resume on file yet. Run the "
                "resume analyzer to see exactly which required skills you "
                "are missing.",
                '/resume',
                "resume_missing:" + today,
            ):
                created += 1
    return created


# ─── Category 5: interview preparation (real sessions & schedule) ────

def check_interview_prep(user, now_local=None, slot=None) -> int:
    """Daily prep reminder when nothing is scheduled, referencing the
    user's own weak areas from their last practice session."""
    if not _flag(user, 'notify_interview'):
        return 0
    roles = _roles_of(user)
    if not roles:
        return 0
    today = _today(now_local)

    has_scheduled = db.session.query(InterviewHistory.id).filter(
        InterviewHistory.user_id == user.id,
        InterviewHistory.status == 'scheduled',
        InterviewHistory.interview_date >= datetime.utcnow(),
    ).first() is not None
    if has_scheduled:
        return 0  # the scheduled-interview reminder already covers this

    # Real weak areas from the user's own last practice session.
    last = (InterviewHistory.query
            .filter_by(user_id=user.id)
            .order_by(InterviewHistory.created_at.desc())
            .first())
    weak = []
    if last and getattr(last, 'weak_areas', None):
        try:
            parsed = json.loads(last.weak_areas) if isinstance(last.weak_areas, str) \
                else last.weak_areas
            if isinstance(parsed, list):
                weak = [str(w) for w in parsed[:3] if str(w).strip()]
        except (json.JSONDecodeError, TypeError):
            weak = []

    if weak:
        message = ("Your last practice session flagged: " + ', '.join(weak) +
                   ". Run another mock interview for " + roles[0] +
                   " to close the gap.")
        key = "interview_prep_weak:" + today
    else:
        message = ("No interview scheduled yet - keep " + roles[0] +
                   " preparation sharp with a practice session on the "
                   "Interview page.")
        key = "interview_prep:" + today + ":" + roles[0].lower()

    if _note(
        user, 'interview_prep',
        "Interview prep: " + roles[0], message, '/interview', key,
        data={'weak_areas': weak} if weak else None,
    ):
        return 1
    return 0


# ─── Category 6: job tracker (real application/saved-job state) ──────

def check_tracker(user, now_local=None, slot=None) -> int:
    """Follow-up reminders for stale applications and unactioned saved
    jobs - only the user's own real rows."""
    if not _flag(user, 'notify_tracker'):
        return 0
    today = _today(now_local)
    created = 0

    stale_cutoff = datetime.utcnow() - timedelta(days=STALE_APPLICATION_DAYS)
    stale = JobApplication.query.filter(
        JobApplication.user_id == user.id,
        JobApplication.status.in_(('applied', 'screening', 'interview')),
        JobApplication.last_updated.isnot(None),
        JobApplication.last_updated <= stale_cutoff,
    ).all()
    for app_row in stale:
        days = STALE_APPLICATION_DAYS
        if now_local is not None and app_row.last_updated is not None:
            days = (now_local.date() - app_row.last_updated.date()).days
        if _note(
            user, 'tracker_stale',
            "Follow up: " + app_row.role + " at " + app_row.company,
            "Your " + app_row.role + " application at " + app_row.company +
            " has been '" + str(app_row.status) + "' for " + str(days) +
            " days with no update. A polite follow-up can help.",
            '/applications',
            "tracker_stale:" + str(app_row.id) + ":" + today,
        ):
            created += 1

    iso = now_local.isocalendar() if now_local else datetime.utcnow().isocalendar()
    week = str(iso.year) + '-W' + str(iso.week).zfill(2)
    cutoff_date = now_local.date() if now_local else datetime.utcnow().date()
    cutoff = cutoff_date - timedelta(days=STALE_SAVED_JOB_DAYS)
    saved = (SavedJob.query
             .filter(SavedJob.user_id == user.id,
                     SavedJob.status == 'saved',
                     SavedJob.saved_at.isnot(None))
             .all())
    for job in saved:
        if job.saved_at.date() > cutoff:
            continue
        already_applied = JobApplication.query.filter_by(
            user_id=user.id, company=job.company or '',
            role=job.role_title,
        ).first() is not None
        if already_applied:
            continue
        company_part = ' at ' + job.company if job.company else ''
        if _note(
            user, 'tracker_stale',
            "Ready to apply? " + job.role_title,
            "You saved " + job.role_title + company_part +
            " over a week ago and have not started an application yet.",
            '/applications',
            "tracker_saved:" + str(job.id) + ":" + week,
        ):
            created += 1
        if created >= 5:
            break
    return created
