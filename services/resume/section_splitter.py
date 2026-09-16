"""
services/resume/section_splitter.py
Splits resume text into canonical sections (experience, education,
skills, projects, certifications, summary, achievements) so downstream
extractors can scope their patterns and evidence to the right region.
"""
import re
from collections import OrderedDict
from typing import Dict, List

SECTION_ALIASES = {
    "experience": re.compile(
        r"^(professional\s+|work\s+|employment\s+|career\s+)?"
        r"(experience|work\s+history|employment|career\s+history)\s*:?$", re.I),
    "education": re.compile(
        r"^(education(al)?(\s+background|\s+qualifications)?|academics)"
        r"\s*:?$", re.I),
    "skills": re.compile(
        r"^((technical|core|key)\s+)?(skills|competencies|technologies|"
        r"technical\s+proficiencies|skills\s*(&|and)\s*"
        r"(tools|technologies))\s*:?$", re.I),
    "projects": re.compile(
        r"^((personal|academic|key|selected)\s+)?projects\s*:?$", re.I),
    "certifications": re.compile(
        r"^(certifications?|certificates?|licenses?|courses\s*(&|and)\s*"
        r"certifications?)\s*:?$", re.I),
    "summary": re.compile(
        r"^((professional\s+)?(summary|profile)|objective|about\s*me)"
        r"\s*:?$", re.I),
    "achievements": re.compile(
        r"^(achievements|accomplishments|awards(\s*(&|and)\s*honors)?)"
        r"\s*:?$", re.I),
}

_MAX_HEADER_LEN = 60


def _is_section_header(line: str) -> str:
    """Return canonical name if line looks like a section header, else ''."""
    cleaned = line.strip().strip("*#-_ ").strip()
    if not cleaned or len(cleaned) > _MAX_HEADER_LEN:
        return ""
    # A header is a short line, typically title-case/upper-case, no verbs.
    words = cleaned.split()
    if len(words) > 6:
        return ""
    for canonical, pattern in SECTION_ALIASES.items():
        if pattern.match(cleaned):
            # Exclude sentence-like lines (e.g. "skills required: python")
            if cleaned.lower().startswith(("with ", "including ", "such as ")):
                return ""
            return canonical
    return ""


def split_sections(text: str) -> "OrderedDict[str, List[str]]":
    """
    Split raw resume text into canonical sections.

    Returns an OrderedDict canonical_name -> list of lines. Lines before
    the first recognised header go under "header" (name/title/contact
    zone). Unknown headers keep their own key so no text is dropped.
    """
    sections: "OrderedDict[str, List[str]]" = OrderedDict()
    current = "header"
    sections[current] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            # Preserve blank lines: entry separators for downstream parsers
            sections.setdefault(current, []).append("")
            continue
        header = _is_section_header(line)
        if header:
            current = header
            if current not in sections:
                sections[current] = []
            continue
        sections.setdefault(current, []).append(line.strip())

    return sections


def section_text(sections: Dict[str, List[str]], canonical: str) -> str:
    """Join a section's lines back into text ('' if absent)."""
    return "\n".join(sections.get(canonical, []))


def section_or_rest(sections: Dict[str, List[str]], canonical: str,
                    fallback: str = "") -> str:
    """Section text if present, else the fallback text."""
    return section_text(sections, canonical) or fallback