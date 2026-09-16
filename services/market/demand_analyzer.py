"""
services/market/demand_analyzer.py

Answers "which skills are ACTUALLY in demand for this role right now",
by pulling a sample of live job postings (via job_search_service) and
counting how many of them mention each known skill - not a static,
hand-written list.

This is deliberately a frequency count over real postings, not an LLM
guess: "Python appeared in 41 of 52 postings (79%)" is a claim you can
defend to a user, and it updates automatically as the market does.
"""
from collections import Counter
from typing import Dict, List, Optional

from services.jobs.job_search_service import search_jobs
from services.resume.taxonomy import all_skills, skill_category
from services.resume.skill_extractor import extract_skills_with_evidence
from utils.logger import get_logger

logger = get_logger()

MIN_SAMPLE_SIZE = 5  # below this, a demand percentage is misleading


def _skills_mentioned_in_text(text: str) -> set:
    """Which canonical skills appear anywhere in a single job posting's text.

    Reuses the same evidence-based extractor the resume side uses, just
    fed the whole posting as a single 'description' section, since for
    demand-counting we only care about presence, not resume-strength.
    """
    if not text or not text.strip():
        return set()
    sections = {"description": [text]}
    found = extract_skills_with_evidence(text, sections)
    return {item["skill"] for item in found if item.get("skill")}


def analyze_skill_demand(
    job_title: str,
    location: str = "",
    sample_size: int = 40,
    include_slow_sources: bool = False,
) -> Dict:
    """Pulls a live sample of postings for job_title and returns skills
    ranked by what fraction of real postings actually mention them.
    """
    search_result = search_jobs(
        job_title,
        location=location,
        limit=sample_size,
        include_slow_sources=include_slow_sources,
        max_age_days=60,  # wider window here - we want sample size, not just today's postings
    )
    postings = search_result["jobs"]
    sample_count = len(postings)

    if sample_count == 0:
        return {
            "job_title": job_title,
            "location": location,
            "sample_size": 0,
            "sources_used": search_result["sources_used"],
            "in_demand_skills": [],
            "warning": (
                "Couldn't pull any live postings for this role right now "
                "(no job-search API keys configured, or no results for this "
                "query) - showing no demand data rather than guessing."
            ),
        }

    counts: Counter = Counter()
    for posting in postings:
        text = f"{posting.get('job_title','')} {posting.get('description','')}"
        for skill in _skills_mentioned_in_text(text):
            counts[skill] += 1

    ranked = []
    for skill, count in counts.most_common():
        ranked.append({
            "skill": skill,
            "category": skill_category(skill),
            "postings_mentioning": count,
            "demand_pct": round(100 * count / sample_count, 1),
        })

    result = {
        "job_title": job_title,
        "location": location,
        "sample_size": sample_count,
        "sources_used": search_result["sources_used"],
        "in_demand_skills": ranked,
    }
    if sample_count < MIN_SAMPLE_SIZE:
        result["warning"] = (
            f"Only {sample_count} live postings found for this role/location - "
            "percentages below are based on a small sample and may not "
            "reflect the broader market."
        )
    return result


def compare_resume_to_demand(resume_skills: List[str], demand_result: Dict, top_n: int = 15) -> Dict:
    """Cross-references a user's resume skills against the top in-demand
    skills for the role, so the gap is expressed against real market data
    instead of a fixed taxonomy list.
    """
    resume_set = {s.strip().lower() for s in resume_skills if s and s.strip()}
    top_skills = demand_result.get("in_demand_skills", [])[:top_n]

    have, missing = [], []
    for entry in top_skills:
        if entry["skill"].strip().lower() in resume_set:
            have.append(entry)
        else:
            missing.append(entry)

    return {
        "job_title": demand_result.get("job_title"),
        "sample_size": demand_result.get("sample_size"),
        "skills_you_have": have,
        "missing_in_demand_skills": missing,
    }
