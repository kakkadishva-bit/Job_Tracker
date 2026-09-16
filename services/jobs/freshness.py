"""
services/jobs/freshness.py

Turns whatever messy "posted date" string a source gives us (an ISO
timestamp, "3 days ago", "Just posted", a Unix epoch, or nothing at
all) into a real datetime, then uses that to:

  - label how fresh each job is ("New today", "This week", ...)
  - drop expired/stale postings past a max age
  - dedupe the same job showing up from multiple sources
  - sort newest-first, with unknown-date jobs pushed to the end
    instead of accidentally sorting to the top or being dropped
"""
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Jobs older than this are treated as stale by default. Callers can
# override per search (e.g. a niche role may want a wider window).
DEFAULT_MAX_AGE_DAYS = 30

_RELATIVE_PATTERNS = [
    (re.compile(r"just\s*posted|today|new", re.I), 0),
    (re.compile(r"yesterday", re.I), 1),
    (re.compile(r"(\d+)\s*(?:hour|hr)s?\s*ago", re.I), "hours"),
    (re.compile(r"(\d+)\s*(?:minute|min)s?\s*ago", re.I), "minutes"),
    (re.compile(r"(\d+)\s*day s?\s*ago|(\d+)\s*days?\s*ago", re.I), "days"),
    (re.compile(r"(\d+)\s*weeks?\s*ago", re.I), "weeks"),
    (re.compile(r"(\d+)\s*months?\s*ago", re.I), "months"),
    (re.compile(r"(\d+)\+?\s*days?\s*ago", re.I), "days"),
]


def parse_posted_date(value, reference: Optional[datetime] = None) -> Optional[datetime]:
    """Best-effort parse of a posted-date field into a timezone-aware UTC datetime.

    Accepts ISO 8601 strings, Unix timestamps (int/float or numeric
    string), and common relative phrases ("2 days ago", "Just posted").
    Returns None when it genuinely can't be determined - callers should
    treat that as "unknown", not "old".
    """
    if value is None or value == "":
        return None

    ref = reference or datetime.now(timezone.utc)

    # Already a datetime
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    # Unix timestamp (int/float, or a numeric string)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None

    text = str(value).strip()
    if not text:
        return None

    if text.isdigit() and len(text) >= 9:
        try:
            return datetime.fromtimestamp(float(text), tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            pass

    # ISO 8601 (handles "...Z" suffix which fromisoformat rejects pre-3.11)
    iso_candidate = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_candidate)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # Common absolute formats
    for fmt in ("%Y-%m-%d", "%d %B %Y", "%B %d, %Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue

    # Relative phrases
    for pattern, unit in _RELATIVE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        if unit == 0 or unit == 1:
            return ref - timedelta(days=unit)
        num = next((g for g in m.groups() if g), None)
        if num is None:
            continue
        n = int(num)
        if unit == "hours":
            return ref - timedelta(hours=n)
        if unit == "minutes":
            return ref - timedelta(minutes=n)
        if unit == "days":
            return ref - timedelta(days=n)
        if unit == "weeks":
            return ref - timedelta(weeks=n)
        if unit == "months":
            return ref - timedelta(days=n * 30)

    return None


def freshness_label(posted_at: Optional[datetime], reference: Optional[datetime] = None) -> str:
    """Human label for the UI: 'New today', '3 days ago', 'Date unknown'."""
    if posted_at is None:
        return "Date unknown"
    ref = reference or datetime.now(timezone.utc)
    delta = ref - posted_at
    days = delta.days
    if delta.total_seconds() < 0:
        return "New today"
    if days <= 0:
        return "New today"
    if days == 1:
        return "1 day ago"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    months = days // 30
    return f"{months} month{'s' if months > 1 else ''} ago"


def _job_identity_key(job: Dict) -> str:
    """Identity used for deduping the same posting across sources."""
    url = (job.get("job_url") or "").strip().lower().rstrip("/")
    if url:
        return url
    title = (job.get("job_title") or "").strip().lower()
    company = (job.get("company_name") or "").strip().lower()
    return f"{title}::{company}"


def annotate_freshness(jobs: List[Dict], reference: Optional[datetime] = None) -> List[Dict]:
    """Adds posted_at_iso / days_old / freshness_label to each job dict in place-safe copies."""
    ref = reference or datetime.now(timezone.utc)
    annotated = []
    for job in jobs:
        job = dict(job)
        posted_at = parse_posted_date(job.get("posted_date"), reference=ref)
        job["posted_at_iso"] = posted_at.isoformat() if posted_at else None
        job["days_old"] = (ref - posted_at).days if posted_at else None
        job["freshness_label"] = freshness_label(posted_at, reference=ref)
        job["_posted_at_sort"] = posted_at
        annotated.append(job)
    return annotated


def dedupe_jobs(jobs: List[Dict]) -> List[Dict]:
    """Keeps the first (freshest, since caller sorts before deduping ideally) copy of each posting."""
    seen = set()
    result = []
    for job in jobs:
        key = _job_identity_key(job)
        if key in seen:
            continue
        seen.add(key)
        result.append(job)
    return result


def drop_stale(jobs: List[Dict], max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> List[Dict]:
    """Drops jobs older than max_age_days. Jobs with an unknown date are kept
    (better to show an undated real listing than to silently hide it), but
    they'll sort to the bottom via sort_by_freshness.
    """
    kept = []
    for job in jobs:
        days_old = job.get("days_old")
        if days_old is not None and days_old > max_age_days:
            continue
        kept.append(job)
    return kept


def sort_by_freshness(jobs: List[Dict]) -> List[Dict]:
    """Newest first. Jobs with no parseable date sort after all dated ones,
    instead of before (which is what a naive `sort by date descending with
    None-as-lowest` would accidentally do wrong in Python 3, since None
    can't be compared to datetime at all)."""
    dated = [j for j in jobs if j.get("_posted_at_sort") is not None]
    undated = [j for j in jobs if j.get("_posted_at_sort") is None]
    dated.sort(key=lambda j: j["_posted_at_sort"], reverse=True)
    ordered = dated + undated
    for j in ordered:
        j.pop("_posted_at_sort", None)
    return ordered


def process_job_freshness(jobs: List[Dict], max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> List[Dict]:
    """Full pipeline: annotate -> dedupe -> drop stale -> sort newest-first."""
    annotated = annotate_freshness(jobs)
    deduped = dedupe_jobs(annotated)
    fresh = drop_stale(deduped, max_age_days=max_age_days)
    return sort_by_freshness(fresh)
