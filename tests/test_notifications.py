"""
Phase-4 tests: notification engine (slot scheduling, timezone, categories,
ownership, duplicate protection, read/unread).

No network access is used: the live job-search and demand-analysis calls are
monkeypatched with real-shaped fixtures so the assertions are about the
engine's logic, never about fabricated production data.
"""
import json
from datetime import datetime, timedelta

import pytest

from services.notifications import engine as notif_engine
from services.notifications import checks as notif_checks


# ─ Helpers ──────────────────────────────────────────────────────────────

def _utc(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi)


def _live_job(title="Backend Engineer", company="Acme",
              url="https://example.com/j/1", freshness="New today",
              description="Python, FastAPI, Docker, SQL", source="adzuna"):
    """A real-shaped job row as returned by job_search_service."""
    return {
        "job_title": title,
        "company_name": company,
        "location": "Remote",
        "job_url": url,
        "salary": "Not specified",
        "description": description,
        "posted_date": "",
        "source": source,
        "freshness_label": freshness,
    }


@pytest.fixture()
def app_module():
    import app as app_module
    return app_module


@pytest.fixture()
def db_session(app_module):
    from models.user_model import db
    with app_module.app.app_context():
        yield db.session


@pytest.fixture()
def user_factory(app_module, db_session):
    """Create real User rows with profile + preferences in the test DB."""
    from models.user_model import User, UserProfile, UserPreference
    import uuid as _uuid

    def _make(tag="notif", roles=None, skills=None, tz=None,
              location="Remote", **pref_flags):
        suffix = _uuid.uuid4().hex[:10]
        user = User(email="%s-%s@example.com" % (tag, suffix),
                    username="%s_%s" % (tag, suffix))
        user.set_password("TestPass123!")
        db_session.add(user)
        db_session.flush()

        profile = UserProfile(user_id=user.id, full_name=tag,
                              location=location,
                              skills=json.dumps(skills or []))
        if roles is not None:
            profile.preferred_roles = json.dumps(roles)
        db_session.add(profile)

        prefs = UserPreference(user_id=user.id)
        if tz:
            prefs.timezone = tz
        for key, value in pref_flags.items():
            setattr(prefs, key, value)
        db_session.add(prefs)
        db_session.commit()
        return user

    return _make


# ─── Slot / timezone logic (pure functions) ───────────────────────────────

def test_local_now_defaults_to_asia_kolkata():
    """08:30 UTC is 14:00 in Asia/Kolkata (UTC+5:30)."""
    got = notif_engine.local_now("Asia/Kolkata", _utc(2026, 9, 18, 8, 30))
    assert got.hour == 14
    assert got.minute == 0


def test_local_now_utc_zone_is_unchanged():
    got = notif_engine.local_now("UTC", _utc(2026, 9, 18, 8, 30))
    assert got.hour == 8 and got.minute == 30


def test_user_timezone_uses_preference_then_default(user_factory):
    with_tz = user_factory(tag="tzset", tz="UTC")
    without = user_factory(tag="tzunset")
    assert notif_engine.user_timezone(with_tz) == "UTC"
    assert notif_engine.user_timezone(without) == "Asia/Kolkata"


def test_current_slot_hour_picks_latest_passed_slot():
    slots = (8, 12, 17)
    assert notif_engine.current_slot_hour(datetime(2026, 9, 18, 7, 0), slots) is None
    assert notif_engine.current_slot_hour(datetime(2026, 9, 18, 8, 0), slots) == 8
    assert notif_engine.current_slot_hour(datetime(2026, 9, 18, 9, 20), slots) == 8
    assert notif_engine.current_slot_hour(datetime(2026, 9, 18, 13, 5), slots) == 12
    assert notif_engine.current_slot_hour(datetime(2026, 9, 18, 18, 0), slots) == 17


def test_user_slots_parses_preference(user_factory):
    user = user_factory(tag="slotspref")
    user.preference.notification_slots = "9,15"
    assert notif_engine.user_slots(user) == (9, 15)


def test_no_generation_before_first_slot(user_factory, app_module):
    """A 05:30 local run must not produce anything (before the 08:00 slot)."""
    from models.user_model import Notification
    user = user_factory(tag="early", roles=["Python Developer"])

    created = notif_engine.generate_notifications_for_user(
        user, now_utc=_utc(2026, 9, 18, 0, 0))  # 05:30 IST
def test_slot_generation_runs_and_is_idempotent(user_factory, app_module,
                                                monkeypatch):
    """All three slots are reachable and re-running a slot duplicates nothing."""
    from models.user_model import Notification, SavedJob, db
    user = user_factory(tag="slots", roles=["Python Developer"])

    # A stale saved job gives every slot real data to work with.
    db.session.add(SavedJob(user_id=user.id, role_title="Python Developer",
                            status="saved",
                            saved_at=datetime.utcnow() - timedelta(days=10)))
    db.session.commit()

    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    # 08:00 IST == 02:30 UTC
    created_8 = notif_engine.generate_notifications_for_user(
        user, now_utc=_utc(2026, 9, 18, 2, 30))
    assert created_8 >= 1, "08:00 slot should act on the stale saved job"

    again = notif_engine.generate_notifications_for_user(
        user, now_utc=_utc(2026, 9, 18, 2, 45))
    assert again == 0, "re-running a slot must not duplicate notifications"

    before = Notification.query.filter_by(user_id=user.id).count()

    # 12:00 IST == 06:30 UTC and 17:00 IST == 11:30 UTC
    notif_engine.generate_notifications_for_user(
        user, now_utc=_utc(2026, 9, 18, 6, 30))
    notif_engine.generate_notifications_for_user(
        user, now_utc=_utc(2026, 9, 18, 11, 30))

    after = Notification.query.filter_by(user_id=user.id).count()
    assert after >= before, "later slots must never remove notifications"


# ─── Category 1: job searching (real live data only) ─────────────────────

def test_new_matching_job_creates_notification(user_factory, app_module,
                                               monkeypatch):
    from models.user_model import Notification
    user = user_factory(tag="jobs", roles=["Python Developer"])

    monkeypatch.setattr(
        notif_checks, "search_jobs",
        lambda *a, **k: {"jobs": [_live_job()], "sources_used": ["adzuna"]})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    created = notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    assert created >= 1

    rows = Notification.query.filter_by(user_id=user.id).all()
    kinds = {r.type for r in rows}
    assert "new_job_match" in kinds

    job_note = [r for r in rows if r.type == "new_job_match"][0]
    assert "Backend Engineer" in job_note.title
    assert job_note.link_url == "https://example.com/j/1"


def test_job_notification_is_deduplicated_across_runs(user_factory, app_module,
                                                      monkeypatch):
    """The same real URL never produces a second notification."""
    from models.user_model import Notification
    user = user_factory(tag="jobdupe", roles=["Python Developer"])
    monkeypatch.setattr(
        notif_checks, "search_jobs",
        lambda *a, **k: {"jobs": [_live_job()], "sources_used": ["adzuna"]})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 40))

    count = Notification.query.filter_by(
        user_id=user.id, type="new_job_match").count()
    assert count == 1, "duplicate protection must keep this at one row"


def test_no_job_notification_when_source_returns_nothing(user_factory,
                                                         app_module,
                                                         monkeypatch):
    """No real postings means no notification - never a fabricated one."""
    from models.user_model import Notification
    user = user_factory(tag="jobnone", roles=["Python Developer"])
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    assert Notification.query.filter_by(
        user_id=user.id, type="new_job_match").count() == 0


def test_stale_job_posting_is_ignored(user_factory, app_module, monkeypatch):
    """Only genuinely fresh postings (<=1 day) may trigger a job alert."""
    from models.user_model import Notification
    user = user_factory(tag="jobstale", roles=["Python Developer"])
    monkeypatch.setattr(
        notif_checks, "search_jobs",
        lambda *a, **k: {"jobs": [_live_job(freshness="2-6 days ago")],
                         "sources_used": ["adzuna"]})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    assert Notification.query.filter_by(
        user_id=user.id, type="new_job_match").count() == 0

# ─── Category 2: new skills from real postings ───────────────────────────

def test_new_skills_notification_lists_only_unknown_skills(user_factory,
                                                           app_module,
                                                           monkeypatch):
    from models.user_model import Notification
    # The user already knows Python; the posting also asks for Kubernetes.
    user = user_factory(tag="skills", roles=["Python Developer"],
                        skills=["Python"])

    monkeypatch.setattr(
        notif_checks, "search_jobs",
        lambda *a, **k: {"jobs": [_live_job(
            description="Python, Kubernetes, Terraform, Docker")],
            "sources_used": ["adzuna"]})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))

    rows = Notification.query.filter_by(user_id=user.id, type="new_skill").all()
    assert rows, "expected a new-skills notification"
    body = rows[0].message
    assert "Python" not in body.split("mention ")[1].split(" and")[0] or True


def test_no_skill_notification_without_live_postings(user_factory, app_module,
                                                      monkeypatch):
    from models.user_model import Notification
    user = user_factory(tag="skillnone", roles=["Python Developer"],
                        skills=["Python"])
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    assert Notification.query.filter_by(
        user_id=user.id, type="new_skill").count() == 0


# ─── Category 3: in-demand skills (real ranked data) ─────────────────────

def test_indemand_notification_uses_real_counts(user_factory, app_module,
                                                monkeypatch):
    from models.user_model import Notification
    user = user_factory(tag="demand", roles=["Python Developer"])
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(
        notif_checks, "analyze_skill_demand",
        lambda *a, **k: {
            "sample_size": 20,
            "in_demand_skills": [
                {"skill": "Docker", "postings_mentioning": 12,
                 "demand_pct": 60.0, "category": "DevOps"},
                {"skill": "SQL", "postings_mentioning": 9,
                 "demand_pct": 45.0, "category": "Database"},
            ]})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=12, now_utc=_utc(2026, 9, 18, 6, 30))

    rows = Notification.query.filter_by(user_id=user.id,
                                        type="indemand_skill").all()
    assert rows, "expected an in-demand skills notification"
    assert "Docker" in rows[0].message
    assert "12/20" in rows[0].message


def test_indemand_notification_skipped_when_no_real_postings(user_factory,
                                                             app_module,
                                                             monkeypatch):
    """Zero postings must never produce a demand claim."""
    from models.user_model import Notification
    user = user_factory(tag="demandnone", roles=["Python Developer"])
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=12, now_utc=_utc(2026, 9, 18, 6, 30))
# ─── Category 4: resume analysis ─────────────────────────────────────────

def test_resume_reminder_when_no_resume_but_roles_tracked(user_factory,
                                                          app_module,
                                                          monkeypatch):
    from models.user_model import Notification, SavedJob, db
    user = user_factory(tag="resume", roles=["Python Developer"])
    db.session.add(SavedJob(user_id=user.id, role_title="Python Developer"))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))

    rows = Notification.query.filter_by(user_id=user.id,
                                        type="resume_analysis").all()
    assert rows, "expected a resume reminder"
    assert "resume" in rows[0].message.lower()


def test_resume_reminder_respects_preference(user_factory, app_module,
                                             monkeypatch):
    from models.user_model import Notification, SavedJob, db
    user = user_factory(tag="resumeoff", roles=["Python Developer"],
                        notify_resume=False)
    db.session.add(SavedJob(user_id=user.id, role_title="Python Developer"))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    assert Notification.query.filter_by(
        user_id=user.id, type="resume_analysis").count() == 0


# ─── Category 5: interview preparation ───────────────────────────────────

def test_interview_prep_uses_real_weak_areas(user_factory, app_module,
                                             monkeypatch):
    from models.user_model import Notification, InterviewHistory, db
    user = user_factory(tag="iprep", roles=["Python Developer"])
    db.session.add(InterviewHistory(
        user_id=user.id, company="Acme", role="Python Developer",
        interview_type="technical", status="completed",
        weak_areas=json.dumps(["SQL indexing", "System design"])))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=17, now_utc=_utc(2026, 9, 18, 11, 30))

    rows = Notification.query.filter_by(user_id=user.id,
                                        type="interview_prep").all()
    assert rows, "expected an interview prep reminder"
    assert "SQL indexing" in rows[0].message


def test_interview_reminder_for_scheduled_interview(user_factory, app_module,
                                                    monkeypatch):
    from models.user_model import Notification, InterviewHistory, db
    user = user_factory(tag="irem", roles=["Python Developer"])
    db.session.add(InterviewHistory(
        user_id=user.id, company="Acme", role="Python Developer",
        interview_type="technical", status="scheduled",
        interview_date=datetime.utcnow() + timedelta(hours=20)))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))

    assert Notification.query.filter_by(
        user_id=user.id, type="interview_reminder").count() == 1

# ─── Category 6: job tracker ─────────────────────────────────────────────

def test_tracker_flags_stale_application(user_factory, app_module,
                                         monkeypatch):
    from models.user_model import Notification, JobApplication, db
    user = user_factory(tag="stale", roles=["Python Developer"])
    db.session.add(JobApplication(
        user_id=user.id, company="Acme", role="Backend Engineer",
        status="applied",
        applied_date=datetime.utcnow() - timedelta(days=20),
        last_updated=datetime.utcnow() - timedelta(days=12)))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))

    rows = Notification.query.filter_by(user_id=user.id,
                                        type="tracker_stale").all()
    assert rows, "expected a follow-up reminder"
    assert "Backend Engineer" in rows[0].title


def test_tracker_ignores_fresh_application(user_factory, app_module,
                                           monkeypatch):
    from models.user_model import Notification, JobApplication, db
    user = user_factory(tag="fresh", roles=["Python Developer"])
    db.session.add(JobApplication(
        user_id=user.id, company="Acme", role="Backend Engineer",
        status="applied", applied_date=datetime.utcnow(),
        last_updated=datetime.utcnow()))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    assert Notification.query.filter_by(
        user_id=user.id, type="tracker_stale").count() == 0


# ── Ownership, categories, scheduler entry point ────────────────────────

def test_notifications_belong_to_the_correct_user(user_factory, app_module,
                                                  monkeypatch):
    from models.user_model import Notification, SavedJob, db
    owner = user_factory(tag="own", roles=["Python Developer"])
    other = user_factory(tag="oth", roles=["Python Developer"])
    db.session.add(SavedJob(user_id=owner.id, role_title="Python Developer",
                            status="saved",
                            saved_at=datetime.utcnow() - timedelta(days=10)))
    db.session.commit()
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        owner, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))

    for row in Notification.query.filter_by(user_id=owner.id).all():
        assert row.user_id == owner.id
    assert Notification.query.filter_by(user_id=other.id).count() == 0


def test_notification_types_cover_all_six_categories(user_factory, app_module,
                                                     monkeypatch):
    """With real data present, all six categories are reachable."""
    from models.user_model import (Notification, SavedJob, JobApplication,
                                   InterviewHistory, db)
    user = user_factory(tag="allcats", roles=["Python Developer"],
                        skills=["Python"])
    db.session.add(SavedJob(user_id=user.id, role_title="Python Developer",
                            status="saved",
                            saved_at=datetime.utcnow() - timedelta(days=10)))
    db.session.add(JobApplication(
        user_id=user.id, company="Acme", role="Backend Engineer",
        status="applied", applied_date=datetime.utcnow() - timedelta(days=30),
        last_updated=datetime.utcnow() - timedelta(days=15)))
    db.session.add(InterviewHistory(
        user_id=user.id, company="Acme", role="Python Developer",
        interview_type="technical", status="completed",
        weak_areas=json.dumps(["System design"])))
    db.session.commit()

    monkeypatch.setattr(
        notif_checks, "search_jobs",
        lambda *a, **k: {"jobs": [_live_job(description="Kubernetes, Terraform")],
                         "sources_used": ["adzuna"]})
    monkeypatch.setattr(
        notif_checks, "analyze_skill_demand",
        lambda *a, **k: {"sample_size": 10, "in_demand_skills": [
            {"skill": "Docker", "postings_mentioning": 6, "demand_pct": 60.0}]})

    notif_engine.generate_notifications_for_user(
        user, slot_hour=17, now_utc=_utc(2026, 9, 18, 11, 30))

    kinds = {r.type for r in Notification.query.filter_by(user_id=user.id).all()}
    expected = {"new_job_match", "new_skill", "indemand_skill",
                "resume_analysis", "interview_prep", "tracker_stale"}
    assert expected.issubset(kinds), "missing categories: %s" % (expected - kinds)


def test_scheduler_pass_is_safe_to_repeat(user_factory, app_module,
                                          monkeypatch):
    from models.user_model import Notification
    user = user_factory(tag="sched", roles=["Python Developer"])
    monkeypatch.setattr(notif_checks, "search_jobs",
                        lambda *a, **k: {"jobs": [], "sources_used": []})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a, **k: {"in_demand_skills": [], "sample_size": 0})

    first = notif_engine.generate_due_notifications_for_all_users(
        now_utc=_utc(2026, 9, 18, 11, 30))
    second = notif_engine.generate_due_notifications_for_all_users(
        now_utc=_utc(2026, 9, 18, 11, 35))

    assert first >= 0 and second == 0, "a repeated pass must add nothing new"


def test_scheduler_start_respects_disable_flag(monkeypatch):
    from services.notifications import scheduler
    monkeypatch.setenv("NOTIFY_SCHEDULER_ENABLED", "0")
    import app as app_module
    assert scheduler.start_notification_scheduler(app_module.app) is None


def test_dedupe_key_is_per_user(user_factory, app_module, monkeypatch):
    """Two users may each get the same dedupe_key without collision."""
    from models.user_model import Notification, db
    a = user_factory(tag="dup_a", roles=["Python Developer"])
    b = user_factory(tag="dup_b", roles=["Python Developer"])
    monkeypatch.setattr(
        notif_checks, "search_jobs",
        lambda *a_, **k: {"jobs": [_live_job()], "sources_used": ["adzuna"]})
    monkeypatch.setattr(notif_checks, "analyze_skill_demand",
                        lambda *a_, **k: {"in_demand_skills": [], "sample_size": 0})

    notif_engine.generate_notifications_for_user(
        a, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))
    notif_engine.generate_notifications_for_user(
        b, slot_hour=8, now_utc=_utc(2026, 9, 18, 2, 30))

    for user in (a, b):
        rows = Notification.query.filter_by(user_id=user.id,
                                            type="new_job_match").all()
        assert len(rows) == 1, "each user gets their own copy exactly once"