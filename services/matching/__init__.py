"""
services/matching - Explainable Resume ↔ Job Matching Engine.

Deterministic, local matching using skill intelligence, evidence strength,
semantic similarity, and structured JD analysis. No cloud LLM required.

Pipeline:
    resume intelligence + job description
        -> JD analysis (required/preferred skills, experience, seniority)
        -> skill matching (exact + semantic)
        -> evidence scoring
        -> weighted score / 100
        -> recommendation + explanation
"""
from services.matching.matcher import match_resume_to_job, MatchResult
from services.matching.jd_analyzer import analyze_job_description, JobDescription
from services.matching.scorer import calculate_match_score

__all__ = [
    "match_resume_to_job",
    "MatchResult",
    "analyze_job_description",
    "JobDescription",
    "calculate_match_score",
]