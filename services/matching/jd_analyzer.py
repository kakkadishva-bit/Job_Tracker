"""Combined JD analyzer module."""
import re
import logging
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from services.resume.skill_registry import (
    CATEGORIES, aliases_for, canonical_for, category_for,
)

logger = logging.getLogger(__name__)

# Section headers commonly found in JDs
_SECTION_HEADERS = {
    "required": [
        r"required\s*(?:skills?|qualifications?|requirements?)",
        r"must\s*have",
        r"essential\s*(?:skills?|qualifications?)",
        r"minimum\s*(?:requirements?|qualifications?)",
        r"basic\s*(?:requirements?|qualifications?)",
        r"core\s*(?:skills?|competenc(?:y|ies))",
        r"technical\s*requirements?",
    ],
    "preferred": [
        r"preferred\s*(?:skills?|qualifications?)",
        r"nice\s*to\s*have",
        r"desired\s*(?:skills?|qualifications?)",
        r"bonus\s*(?:skills?|points?)",
        r"ideal\s*(?:candidate|profile)",
        r"additional\s*(?:skills?|qualifications?)",
    ],
    "responsibilities": [
        r"responsibilit(?:y|ies)",
        r"role\s*and\s*responsibilit(?:y|ies)",
        r"what\s*you(?:'ll|\s+will)\s*(?:do|be\s+doing)",
        r"job\s*description",
        r"duties",
        r"key\s*deliverables?",
    ],
    "experience": [
        r"experience\s*(?:required|needed)?",
        r"years?\s*of\s*experience",
        r"work\s*experience",
        r"professional\s*experience",
    ],
    "education": [
        r"education(?:al)?\s*(?:qualifications?|requirements?)?",
        r"degree\s*(?:required|needed)?",
        r"academic\s*(?:background|qualifications?)",
    ],
    "certifications": [
        r"certifications?",
        r"professional\s*certifications?",
        r"licenses?",
    ],
}

_SENIORITY_PATTERNS = [
    (r"\b(?:principal|distinguished|staff|chief|head\s+of|director|vp|vice\s+president)\b", "lead"),
    (r"\b(?:senior|sr\.?|lead|principal|architect)\b", "senior"),
    (r"\b(?:mid[\s-]?level|intermediate|experienced)\b", "mid"),
    (r"\b(?:junior|jr\.?|entry[\s-]?level|graduate|intern|fresher|trainee|associate)\b", "junior"),
]

_WORK_MODE_PATTERNS = {
    "remote": [r"\bremote\b", r"\bwork\s+from\s+home\b", r"\bwfh\b", r"\bfully\s+remote\b"],
    "hybrid": [r"\bhybrid\b", r"\bpartial(?:ly)?\s+remote\b"],
    "onsite": [r"\bonsite\b", r"\bon[\s-]?site\b", r"\bin[\s-]?office\b", r"\boffice\s+based\b"],
}

_EXP_YEAR_PATTERN = re.compile(
    r"(\d+)\+?\s*(?:-\s*(\d+)\+?\s*)?(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)",
    re.I,
)


@dataclass
class JobDescription:
    """Structured analysis of a job description."""
    raw_text: str = ""
    title: str = ""
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    experience_years_min: Optional[int] = None
    experience_years_max: Optional[int] = None
    seniority: Optional[str] = None
    education: List[str] = field(default_factory=list)
    certifications: List[str] = field(default_factory=list)
    work_mode: Optional[str] = None
    location: str = ""
    all_skills: List[str] = field(default_factory=list)


def _skill_in_text(skill: str, text: str) -> bool:
    if skill in {"ML", "AI", "NLP", "CV", "JS", "TS", "SQL", "R", "C", "Go", "CI"}:
        pattern = r"\b" + re.escape(skill) + r"\b"
        return bool(re.search(pattern, text, re.I if skill.islower() else 0))
    if " " in skill or "-" in skill:
        return skill.lower() in text.lower()
    pattern = r"\b" + re.escape(skill.lower()) + r"\b"
    return bool(re.search(pattern, text.lower()))


def _extract_skills_from_text(text: str) -> List[str]:
    found = set()
    for canonical in CATEGORIES:
        if _skill_in_text(canonical, text):
            found.add(canonical)
            continue
        for alias in aliases_for(canonical):
            if _skill_in_text(alias, text):
                found.add(canonical)
                break
    return sorted(found)


def _find_section_boundaries(text: str, patterns: List[str]) -> List[Tuple[int, int]]:
    boundaries = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.I):
            start = m.start()
            end = len(text)
            next_section = re.search(
                r"\n\s*(?:[A-Z][A-Z\s]{2,}|(?:"
                + "|".join(p for pats in _SECTION_HEADERS.values() for p in pats)
                + r"))",
                text[m.end():],
                re.I,
            )
            if next_section:
                end = m.end() + next_section.start()
            boundaries.append((start, end))
    return boundaries


def _extract_seniority(text: str) -> str:
    text_lower = text.lower()
    for pattern, level in _SENIORITY_PATTERNS:
        if re.search(pattern, text_lower):
            return level
    return None


def _extract_experience_years(text: str):
    for m in _EXP_YEAR_PATTERN.finditer(text):
        return int(m.group(1)), int(m.group(2)) if m.group(2) else None
    return None, None


def _extract_work_mode(text: str) -> str:
    text_lower = text.lower()
    for mode, patterns in _WORK_MODE_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return mode
    return None


def _extract_responsibilities(text: str) -> list:
    responsibilities = []
    boundaries = _find_section_boundaries(text, _SECTION_HEADERS["responsibilities"])
    if not boundaries:
        for line in text.split("\n"):
            stripped = line.strip()
            if re.match(r"^[\-\*•\d.)\]]+\s+", stripped) and len(stripped) > 15:
                clean = re.sub(r"^[\-\*•\d.)\]]+\s+", "", stripped)
                responsibilities.append(clean)
        return responsibilities[:10]
    for start, end in boundaries:
        section_text = text[start:end]
        for line in section_text.split("\n"):
            stripped = line.strip()
            if re.match(r"^[\-\*•\d.)\]]+\s+", stripped) and len(stripped) > 15:
                clean = re.sub(r"^[\-\*•\d.)\]]+\s+", "", stripped)
                responsibilities.append(clean)
    return responsibilities[:10]


def _extract_education(text: str) -> list:
    education = []
    degree_patterns = [
        r"\b(?:b\.?tech|b\.?e\.?|bachelor(?:'?s)?(?:\s+of\s+(?:technology|engineering|science))?)\b",
        r"\b(?:m\.?tech|m\.?e\.?|master(?:'?s)?(?:\s+of\s+(?:technology|engineering|science))?)\b",
        r"\b(?:ph\.?d|doctorate|doctoral)\b",
        r"\b(?:b\.?sc|m\.?sc|b\.?s\.?|m\.?s\.?)\b",
        r"\b(?:b\.?ca|m\.?ca|b\.?com|m\.?com)\b",
    ]
    for pattern in degree_patterns:
        m = re.search(pattern, text, re.I)
        if m:
            education.append(m.group(0))
    return education


def _extract_certifications(text: str) -> list:
    certs = []
    cert_patterns = [
        r"\b(?:aws\s+(?:certified|solutions?\s+architect|developer|sysops))\b",
        r"\b(?:azure\s+(?:certified|administrator|developer|architect|fundamentals))\b",
        r"\b(?:gcp\s+(?:certified|cloud|professional))\b",
        r"\b(?:certified\s+(?:kubernetes|cka|ckad|cks))\b",
        r"\b(?:pmp|prince2|itil|scrum\s+master|csm)\b",
        r"\b(?:tensorflow\s+developer|google\s+cloud\s+professional)\b",
    ]
    for pattern in cert_patterns:
        for m in re.finditer(pattern, text, re.I):
            certs.append(m.group(0))
    return certs


def _extract_title(text: str) -> str:
    lines = text.strip().split("\n")
    for line in lines[:5]:
        stripped = line.strip()
        if stripped and len(stripped) < 100 and not stripped.startswith(("http", "www", "company")):
            if not re.match(r"^(?:about|role|job|position|description|overview)", stripped, re.I):
                return stripped
            if ":" in stripped:
                return stripped.split(":", 1)[1].strip()
    return ""


def analyze_job_description(text: str) -> JobDescription:
    if not text or not text.strip():
        return JobDescription(raw_text="")

    text = text.strip()
    jd = JobDescription(raw_text=text)
    jd.title = _extract_title(text)

    required_boundaries = _find_section_boundaries(text, _SECTION_HEADERS["required"])
    preferred_boundaries = _find_section_boundaries(text, _SECTION_HEADERS["preferred"])

    required_text = " ".join(text[s:e] for s, e in required_boundaries) if required_boundaries else ""
    preferred_text = " ".join(text[s:e] for s, e in preferred_boundaries) if preferred_boundaries else ""

    if not required_text:
        required_text = text

    jd.required_skills = _extract_skills_from_text(required_text)
    jd.preferred_skills = _extract_skills_from_text(preferred_text)
    jd.preferred_skills = [s for s in jd.preferred_skills if s not in jd.required_skills]
    jd.all_skills = sorted(set(jd.required_skills + jd.preferred_skills))

    jd.seniority = _extract_seniority(text)
    jd.experience_years_min, jd.experience_years_max = _extract_experience_years(text)
    jd.work_mode = _extract_work_mode(text)
    jd.responsibilities = _extract_responsibilities(text)
    jd.education = _extract_education(text)
    jd.certifications = _extract_certifications(text)

    return jd

