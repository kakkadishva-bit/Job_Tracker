"""
services/jobs/job_search_service.py

This is the missing link that actually makes /api/jobs/search return
real, current job listings instead of just links out to other sites.

Design notes (why it's built this way):

- Adzuna, JSearch, and RemoteOK are all plain HTTP calls (no browser),
  so they're safe to call synchronously inside a web request.
- Naukri and Wellfound depend on Selenium / Firecrawl, which are slow
  and can hang or fail if Chrome / the Firecrawl API isn't available
  on the server. Those run in a background thread pool with a hard
  per-source timeout, so a flaky source degrades the result set
  instead of taking the whole request down.
- Every result, regardless of source, gets normalized to the same
  Job shape, then deduped and freshness-sorted (services.jobs.freshness)
  before it's returned, so "new jobs on top, old/expired ones dropped"
  is a property of this layer, not something every caller has to redo.
"""
import concurrent.futures
from typing import Dict, List, Optional

from models.job_model import Job
from services.jobs.freshness import process_job_freshness
from utils.logger import get_logger

logger = get_logger()

FAST_SOURCE_TIMEOUT = 10
SLOW_SOURCE_TIMEOUT = 15


def _safe_job(data: Dict, fallback_source: str = "") -> Optional[Dict]:
    """Build a Job (which validates/cleans fields) from a loosely-shaped dict,
    without letting one malformed record blow up the whole search."""
    try:
        job = Job(
            job_title=data.get("job_title") or data.get("title") or "",
            company_name=data.get("company_name") or data.get("company") or "",
            location=data.get("location") or "Remote",
            job_url=data.get("job_url") or data.get("url") or "",
            salary=data.get("salary") or _format_salary_range(data) or "Not specified",
            description=data.get("description") or "",
            posted_date=data.get("posted_date") or "",
            source=data.get("source") or fallback_source,
        )
        if not job.job_title or not job.job_url:
            return None
        d = job.to_dict()
        d["external_id"] = data.get("external_id", "")
        return d
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Skipped malformed job record: %s", exc)
        return None


def _format_salary_range(data: Dict) -> str:
    lo, hi = data.get("salary_min"), data.get("salary_max")
    if lo and hi:
        try:
            return f"${int(lo):,} - ${int(hi):,}"
        except (TypeError, ValueError):
            return f"{lo} - {hi}"
    return ""


def _fetch_adzuna(job_title: str, location: str) -> List[Dict]:
    from utils.api_integrations import api_integrations
    raw = api_integrations.search_jobs_adzuna(job_title, location)
    return [j for j in (_safe_job(r, "Adzuna") for r in raw) if j]


def _fetch_jsearch(job_title: str, location: str) -> List[Dict]:
    from utils.api_integrations import api_integrations
    raw = api_integrations.search_jobs_jsearch(job_title, location)
    return [j for j in (_safe_job(r, "JSearch") for r in raw) if j]


def _fetch_remoteok(job_title: str, limit: int) -> List[Dict]:
    from scrapers.remoteok_scraper import RemoteOKScraper
    raw = RemoteOKScraper().scrape(job_title, limit=limit)
    return [j for j in (_safe_job(r, "RemoteOK") for r in raw) if j]


def _fetch_naukri(job_title: str, location: str, limit: int) -> List[Dict]:
    from scrapers.naukri_scraper import NaukriScraper
    raw = NaukriScraper().scrape(job_title, limit=limit, location=location or None)
    return [j for j in (_safe_job(r, "Naukri") for r in raw) if j]


def _fetch_wellfound(job_title: str, limit: int) -> List[Dict]:
    from scrapers.wellfound_scraper import WellfoundScraper
    raw = WellfoundScraper().scrape(job_title, limit=limit)
    return [j for j in (_safe_job(r, "Wellfound") for r in raw) if j]


def _run_with_timeout(fn, timeout: int, *args) -> List[Dict]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn, *args)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            logger.warning("%s timed out after %ss - skipping", fn.__name__, timeout)
            return []
        except Exception as exc:
            logger.warning("%s failed: %s", fn.__name__, exc)
            return []


def search_jobs(
    job_title: str,
    location: str = "",
    limit: int = 30,
    include_slow_sources: bool = True,
    max_age_days: int = 30,
) -> Dict:
    """Search all configured live sources and return a single, deduped,
    freshness-sorted list of real job postings.

    Returns a dict (not just a list) so the caller can see which sources
    actually returned data - important for being honest with the user
    when e.g. no API keys are configured and results are thin.
    """
    if not job_title or not job_title.strip():
        return {"jobs": [], "sources_used": [], "sources_failed": [], "total": 0}

    job_title = job_title.strip()
    all_jobs: List[Dict] = []
    sources_used: List[str] = []
    sources_failed: List[str] = []

    # Fast sources run inline with their own short timeout - they're
    # plain HTTP calls so this should be quick even run one after another.
    fast_sources = [
        ("Adzuna", _fetch_adzuna, (job_title, location)),
        ("JSearch", _fetch_jsearch, (job_title, location)),
        ("RemoteOK", _fetch_remoteok, (job_title, limit)),
    ]
    for name, fn, args in fast_sources:
        results = _run_with_timeout(fn, FAST_SOURCE_TIMEOUT, *args)
        if results:
            sources_used.append(name)
            all_jobs.extend(results)
        else:
            sources_failed.append(name)

    # Slow/fragile sources: only attempt if asked to, and never let them
    # block the fast sources from being returned.
    if include_slow_sources:
        slow_sources = [
            ("Naukri", _fetch_naukri, (job_title, location, limit)),
            ("Wellfound", _fetch_wellfound, (job_title, limit)),
        ]
        for name, fn, args in slow_sources:
            results = _run_with_timeout(fn, SLOW_SOURCE_TIMEOUT, *args)
            if results:
                sources_used.append(name)
                all_jobs.extend(results)
            else:
                sources_failed.append(name)

    processed = process_job_freshness(all_jobs, max_age_days=max_age_days)
    return {
        "jobs": processed[:limit] if limit else processed,
        "sources_used": sources_used,
        "sources_failed": sources_failed,
        "total": len(processed),
    }
