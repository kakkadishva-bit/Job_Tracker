"""Combined matcher module."""
import logging
from typing import Dict, List, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Complete result of resume-to-job matching."""
    score: float = 0.0
    recommendation: str = "LOW PRIORITY"
    matched_required: List[str] = field(default_factory=list)
    missing_required: List[str] = field(default_factory=list)
    matched_preferred: List[str] = field(default_factory=list)
    missing_preferred: List[str] = field(default_factory=list)
    experience_match: str = "unknown"
    seniority_match: str = "unknown"
    evidence: Dict[str, Any] = field(default_factory=dict)
    explanation: List[str] = field(default_factory=list)
    breakdown: Any = None
    jd: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": round(self.score, 1),
            "recommendation": self.recommendation,
            "matched_required": self.matched_required,
            "missing_required": self.missing_required,
            "matched_preferred": self.matched_preferred,
            "missing_preferred": self.missing_preferred,
            "experience_match": self.experience_match,
            "seniority_match": self.seniority_match,
            "evidence": self.evidence,
            "explanation": self.explanation,
        }


def _get_recommendation(score: float, missing_critical: int) -> str:
    """Determine recommendation based on score and critical gaps."""
    if score >= 70 and missing_critical == 0:
        return "APPLY"
    elif score >= 50 and missing_critical <= 2:
        return "APPLY WITH PREPARATION"
    else:
        return "LOW PRIORITY"


def _compute_skill_gaps(resume: dict, jd) -> Dict[str, List[str]]:
    """Compute matched and missing required/preferred skills.

    Uses exact matching plus semantic similarity so "AWS" also satisfies
    "Amazon Web Services" style requirements. False-match pairs
    (Java/JavaScript, C/C++, React/React Native, AWS/Azure,
    MySQL/PostgreSQL, Go/R) are never considered matches.
    """
    from services.matching.scorer import _is_skill_match
    resume_skills = resume.get("skills", [])
    if not isinstance(resume_skills, list):
        resume_skills = []

    resume_names: List[str] = []
    for s in resume_skills:
        name = s.get("skill", s) if isinstance(s, dict) else s
        if isinstance(name, str) and name.strip():
            resume_names.append(name.strip())

    def _split(skill: str) -> List[str]:
        if not isinstance(skill, str):
            return []
        return [p.strip() for p in skill.split("/") if p.strip()]

    matched_required = []
    missing_required = []
    for skill in (jd.required_skills or []):
        parts = _split(skill) or [skill]
        hit_skill = None
        for part in parts:
            for rs in resume_names:
                if _is_skill_match(part, rs):
                    hit_skill = part
                    break
            if hit_skill:
                break
        if hit_skill:
            matched_required.append(skill)
        else:
            missing_required.append(skill)

    matched_preferred = []
    missing_preferred = []
    for skill in (jd.preferred_skills or []):
        parts = _split(skill) or [skill]
        hit_skill = None
        for part in parts:
            for rs in resume_names:
                if _is_skill_match(part, rs):
                    hit_skill = part
                    break
            if hit_skill:
                break
        if hit_skill:
            matched_preferred.append(skill)
        else:
            missing_preferred.append(skill)

    return {
        "matched_required": matched_required,
        "missing_required": missing_required,
        "matched_preferred": matched_preferred,
        "missing_preferred": missing_preferred,
    }


def _build_evidence(resume: dict, matched_required: List[str],
                    matched_preferred: List[str]) -> Dict[str, Any]:
    """Build evidence dict for matched skills."""
    resume_skills = resume.get("skills", [])
    evidence = {}

    for s in resume_skills:
        if isinstance(s, dict):
            skill_name = s.get("skill", "")
            if skill_name.lower() in [m.lower() for m in matched_required + matched_preferred]:
                evidence[skill_name] = {
                    "confidence": s.get("confidence", 0.0),
                    "strength": s.get("strength", "UNKNOWN"),
                    "source": s.get("source", "unknown"),
                    "evidence": s.get("evidence", [])[:2],
                }

    return evidence



def _build_explanation(breakdown, gaps: List[str], jd) -> List[str]:
    """Build human-readable explanation in the Step-5 report format."""
    explanation = []

    explanation.append("Match: " + str(round(getattr(breakdown, 'total', 0.0), 1)) + "/100")
    explanation.append("")

    for skill in gaps.get("matched_required", []):
        explanation.append("PASS " + skill + " - Required, evidence found")
    for skill in gaps.get("missing_required", []):
        explanation.append("FAIL " + skill + " - Required but missing")
    for skill in gaps.get("matched_preferred", []):
        explanation.append("PASS " + skill + " - Preferred, evidence found")
    for skill in gaps.get("missing_preferred", []):
        explanation.append("WARN " + skill + " - Preferred but not found")

    explanation.append("")
    explanation.append("Score breakdown:")
    explanation.append("  Job relevance: " + str(round(breakdown.job_relevance, 1)) + "/100")
    explanation.append("  Evidence strength: " + str(round(breakdown.evidence_strength, 1)) + "/100")
    explanation.append("  Technical skills: " + str(round(breakdown.technical_skills, 1)) + "/100")
    explanation.append("  Experience: " + str(round(breakdown.experience_relevance, 1)) + "/100")

    if gaps["matched_required"]:
        explanation.append("")
        explanation.append("Matched required skills:")
        for skill in gaps["matched_required"]:
            explanation.append("  [MATCH] " + skill)

    if gaps["missing_required"]:
        explanation.append("")
        explanation.append("Missing required skills:")
        for skill in gaps["missing_required"]:
            explanation.append("  [MISSING] " + skill)

    if gaps["matched_preferred"]:
        explanation.append("")
        explanation.append("Matched preferred skills:")
        for skill in gaps["matched_preferred"]:
            explanation.append("  [MATCH] " + skill)

    if gaps["missing_preferred"]:
        explanation.append("")
        explanation.append("Missing preferred skills (optional):")
        for skill in gaps["missing_preferred"]:
            explanation.append("  [OPTIONAL] " + skill)

    if jd.seniority:
        explanation.append("")
        explanation.append("Seniority required: " + jd.seniority)
    if jd.experience_years_min is not None:
        exp_str = str(jd.experience_years_min) + "+ years"
        if jd.experience_years_max:
            exp_str = str(jd.experience_years_min) + "-" + str(jd.experience_years_max) + " years"
        explanation.append("Experience required: " + exp_str)

    return explanation


def match_resume_to_job(resume, job_description):
    """
    Match a resume against a job description.

    Args:
        resume: Extracted resume structure (from services.resume.extractor).
        job_description: Raw job description text.

    Returns:
        MatchResult with score, gaps, recommendation, and explanation.
    """
    from services.matching.jd_analyzer import analyze_job_description
    from services.matching.scorer import calculate_match_score

    result = MatchResult()

    jd = analyze_job_description(job_description)
    result.jd = jd

    breakdown = calculate_match_score(resume, jd)
    result.breakdown = breakdown
    result.score = breakdown.total

    gaps = _compute_skill_gaps(resume, jd)
    result.matched_required = gaps["matched_required"]
    result.missing_required = gaps["missing_required"]
    result.matched_preferred = gaps["matched_preferred"]
    result.missing_preferred = gaps["missing_preferred"]

    result.evidence = _build_evidence(resume, result.matched_required, result.matched_preferred)

    missing_critical = len(result.missing_required)
    result.recommendation = _get_recommendation(result.score, missing_critical)

    if jd.experience_years_min is not None:
        result.experience_match = "matched" if result.score >= 60 else "partial"
    else:
        result.experience_match = "not_specified"

    if jd.seniority:
        result.seniority_match = "matched" if result.score >= 60 else "mismatch"
    else:
        result.seniority_match = "not_specified"

    result.explanation = _build_explanation(breakdown, gaps, jd)

    return result

