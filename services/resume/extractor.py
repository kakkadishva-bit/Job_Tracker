"""
services/resume/extractor.py
Main resume extraction pipeline -> normalized structure:

{
  "profile":         {name, headline, summary, years_experience},
  "contact":         {email, phone, linkedin, github, portfolio, location},
  "skills":          [{skill, category, confidence, evidence, source, strength}],
  "experience":      [{job_title, company, location, start, end, duration,
                       highlights}],
  "education":       [{degree, institution, year, details}],
  "projects":        [{name, description, technologies}],
  "certifications":  [{name, issuer, year}],
  "raw_text":        str,
  "meta":            {parser_engine, ner_backend, warnings}
}

100% local: pdfplumber / python-docx for documents, regex (+ optional
local NER models) for entities. No paid or cloud AI APIs.
"""
import re
from typing import Dict, List, Optional

from services.resume import ner
from services.resume.section_splitter import split_sections, section_text
from services.resume.skill_extractor import extract_skills_with_evidence
from utils.resume_parser import extract_resume_text, is_extraction_available

RE_BULLET = re.compile(r"^[\-\*\u2022\u25cf\u00b7\d.)\]]+\s*")
RE_RANGE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}"
    r"|\d{1,2}/\d{4}|\b(?:19|20)\d{2}\b)\s*(?:-|\u2013|\u2014|to)\s*"
    r"((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*"
    r"\d{4})|\d{1,2}/\d{4}|(?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)")
_RE_EMAIL = ner.RE_EMAIL
_RE_PHONE = ner.RE_PHONE
_RE_DEGREE = ner.RE_DEGREE
_RE_INSTITUTION = ner.RE_INSTITUTION
_RE_ROLE = ner.RE_ROLE
_RE_COMPANY_SUFFIX = ner.RE_COMPANY_SUFFIX

_PROFILE_NOISE = re.compile(
    r"(email|phone|@\w+\.\w+|linkedin|github|https?://|curriculum|resume)",
    re.I)
_ROLE_NOUNS = re.compile(
    r"\b(engineer|developer|scientist|analyst|manager|designer|architect|"
    r"administrator|consultant|intern|associate|lead)\b", re.I)


def _clean_line(line: str) -> str:
    return RE_BULLET.sub("", line).strip()


def _split_blocks(lines: List[str]) -> List[List[str]]:
    """Split section lines into entries at blank lines or new dates."""
    blocks, current = [], []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        # A new date range only starts a new entry when the current block
        # already holds a complete entry (itself containing a date) --
        # otherwise it belongs with the title line above it.
        if (RE_RANGE.search(stripped) and current
                and RE_RANGE.search(" ".join(current))):
            blocks.append(current)
            current = []
            continue
        # Title-like line (not a bullet) after a completed entry also
        # starts a new entry (covers resumes with no blank lines).
        clean = _clean_line(stripped)
        if (current and RE_RANGE.search(" ".join(current))
                and not RE_BULLET.match(stripped)
                and (ner.RE_ROLE.search(clean) or _ROLE_NOUNS.search(clean))):
            blocks.append(current)
            current = []
        current.append(stripped)
    if current:
        blocks.append(current)
    return blocks


def _extract_profile(header_lines: List[str], full_text: str,
                     entities: List[Dict]) -> Dict:
    profile: Dict = {"name": None, "headline": None, "summary": None,
                     "years_experience": None}
    for line in header_lines[:5]:
        candidate = _clean_line(line)
        if not candidate or _PROFILE_NOISE.search(candidate):
            continue
        words = candidate.split()
        if 2 <= len(words) <= 4 and all(w[:1].isupper() for w in words
                                        if w[:1].isalpha()):
            profile["name"] = candidate
            break
    for line in header_lines:
        m = _RE_ROLE.search(line)
        if m:
            profile["headline"] = _clean_line(line[:m.end()]).strip(" -|\u2022")
            break
    if not profile["name"]:
        for e in entities:
            if e["label"] == "PERSON" and not _PROFILE_NOISE.search(e["value"]):
                profile["name"] = e["value"].strip()
                break
    m = re.search(r"(\d{1,2})\+?\s*years?\s+(?:of\s+)?"
                  r"(?:professional\s+|relevant\s+|hands[- ]on\s+)?experience",
                  full_text, re.I)
    if m:
        profile["years_experience"] = int(m.group(1))
    return profile


def _extract_contact(entities: List[Dict]) -> Dict:
    contact: Dict = {"email": None, "phone": None, "linkedin": None,
                     "github": None, "portfolio": None, "location": None}
    for e in entities:
        v = e["value"]
        if contact["email"] is None and "@" in v and "://" not in v \
                and not v.lower().startswith("linkedin"):
            contact["email"] = v
        elif contact["phone"] is None and e["label"] == "PHONE":
            contact["phone"] = v
        elif contact["location"] is None and e["label"] == "LOCATION":
            contact["location"] = v
        elif e["label"] == "URL":
            lv = v.lower()
            if contact["linkedin"] is None and "linkedin.com" in lv:
                contact["linkedin"] = v
            elif contact["github"] is None and "github.com" in lv:
                contact["github"] = v
            elif (contact["portfolio"] is None
                  and "linkedin.com" not in lv and "github.com" not in lv):
                contact["portfolio"] = v
    return contact
def _parse_experience_block(block: List[str]) -> Optional[Dict]:
    joined = " | ".join(block)
    entry: Dict = {"job_title": None, "company": None, "location": None,
                   "start": None, "end": None, "duration": None,
                   "highlights": []}
    m = RE_RANGE.search(joined)
    if m:
        entry["start"], entry["end"] = m.group(1).strip(), m.group(2).strip()

    # Prefer "Title at Company" / "Title | Company" / "Title - Company"
    # splits BEFORE assigning the whole line as the title.
    for line in block:
        clean = _clean_line(line)
        if not clean:
            continue
        m2 = (re.search(r"^(.{3,60}?)\s+at\s+(.+)$", clean, re.I)
              or re.search(r"^(.{3,60}?)\s*[|\u2022]\s*(.+)$", clean)
              or re.search(r"^(.{3,60}?)\s+-\s+(.+)$", clean))
        if m2 and _ROLE_NOUNS.search(m2.group(1) or "") and not entry["job_title"]:
            entry["job_title"] = m2.group(1).strip()
            comp = m2.group(2).strip()
            comp = re.sub(r"\s*\((?:19|20)\d{2}.*$", "", comp).strip(" -|\u2022")
            entry["company"] = comp or None
            continue
        if not entry["job_title"] and _RE_ROLE.search(clean):
            entry["job_title"] = clean
            continue
        if not entry["company"] and _RE_COMPANY_SUFFIX.search(clean):
            entry["company"] = clean
            continue
        if not entry["job_title"] and _ROLE_NOUNS.search(clean):
            entry["job_title"] = clean
            continue
        entry["highlights"].append(clean)

    # Title-only fallback: "Senior Software Engineer" alone in the block
    if entry["job_title"] and not entry["company"]:
        title = entry["job_title"]
        m3 = (re.search(r"^(.{3,60}?)\s+at\s+(.+)$", title, re.I)
              or re.search(r"^(.{3,60}?)\s*[|\u2022]\s*(.+)$", title)
              or re.search(r"^(.{3,60}?)\s+-\s+(.+)$", title))
        if m3:
            entry["job_title"] = m3.group(1).strip()
            comp = m3.group(2).strip()
            comp = re.sub(r"\s*\((?:19|20)\d{2}.*$", "", comp).strip(" -|\u2022")
            entry["company"] = comp or None

    if not (entry["job_title"] or entry["company"]):
        return None
    if entry["start"] and entry["end"]:
        entry["duration"] = f"{entry['start']} - {entry['end']}"
    return entry


def _extract_experience(sections: Dict[str, List[str]]) -> List[Dict]:
    text = section_text(sections, "experience")
    if not text:
        return []
    entries = []
    for block in _split_blocks(text.splitlines()):
        parsed = _parse_experience_block(block)
        if parsed:
            entries.append(parsed)
    return entries


def _parse_education_block(block: List[str]) -> Optional[Dict]:
    entry: Dict = {"degree": None, "institution": None, "year": None,
                   "details": []}
    for line in block:
        clean = _clean_line(line)
        if not clean:
            continue
        m = _RE_DEGREE.search(clean)
        if m and not entry["degree"]:
            entry["degree"] = m.group(0).strip()
        m = _RE_INSTITUTION.search(clean)
        if m and not entry["institution"]:
            entry["institution"] = m.group(0).strip(" ,|-")
        m = re.search(r"\b(19|20)\d{2}\b", clean)
        if m and not entry["year"]:
            entry["year"] = m.group(0)
        if clean not in entry["details"]:
            entry["details"].append(clean)
    return entry if entry["degree"] or entry["institution"] else None


def _extract_education(sections: Dict[str, List[str]]) -> List[Dict]:
    text = section_text(sections, "education")
    if not text:
        return []
    out = []
    for block in _split_blocks(text.splitlines()):
        parsed = _parse_education_block(block)
        if parsed:
            out.append(parsed)
    return out


_PROJECT_NAME_COLON = re.compile(r"^([A-Z][\w\s&/+.,\-]{2,45}):\s+(.+)$")


def _extract_projects(sections: Dict[str, List[str]]) -> List[Dict]:
    text = section_text(sections, "projects")
    if not text:
        return []
    # "Project Name: description" on one line starts a new project even
    # without blank lines between entries (common resume format).
    blocks: List[List[str]] = []
    current: List[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append(current)
                current = []
            continue
        m = _PROJECT_NAME_COLON.match(_clean_line(stripped))
        if m and current:
            blocks.append(current)
            current = []
        current.append(stripped)
    if current:
        blocks.append(current)

    projects = []
    for block in blocks:
        if not block:
            continue
        first = _clean_line(block[0])
        m = _PROJECT_NAME_COLON.match(first)
        if m:
            name = m.group(1).strip()
            description_parts = [m.group(2).strip()]
            description_parts += [_clean_line(l) for l in block[1:]]
        else:
            name = re.sub(r"^project\s*[:\-]\s*", "", first, flags=re.I)
            description_parts = [_clean_line(l) for l in block[1:]]
        description = " ".join(p for p in description_parts if p).strip()
        tech = [s["skill"] for s in
                extract_skills_with_evidence(" | ".join(block),
                                             {"projects": block})][:8]
        projects.append({"name": name, "description": description,
                         "technologies": tech})
    return projects


def _extract_certifications(sections: Dict[str, List[str]],
                            entities: List[Dict]) -> List[Dict]:
    text = section_text(sections, "certifications")
    out: List[Dict] = []
    if text:
        for line in text.splitlines():
            clean = _clean_line(line)
            if not clean or len(clean) < 3:
                continue
            year = None
            m = re.search(r"\b(19|20)\d{2}\b", clean)
            if m:
                year = m.group(0)
            out.append({"name": clean, "issuer": None, "year": year})
    else:
        for e in entities:
            if e["label"] == "CERTIFICATION":
                out.append({"name": e["value"], "issuer": None, "year": None})
    return out
def extract_resume(filename: Optional[str] = None,
                   content: Optional[bytes] = None,
                   text: Optional[str] = None) -> Dict:
    """
    Full local pipeline: file/text -> sections -> entities ->
    normalized resume structure. Never raises.
    """
    warnings: List[str] = []
    meta: Dict = {"parser_engine": "text", "ner_backend": None,
                  "warnings": warnings}

    if not text:
        if content is None:
            return {"profile": {}, "contact": {}, "skills": [],
                    "experience": [], "education": [], "projects": [],
                    "certifications": [], "raw_text": "",
                    "meta": {"parser_engine": None, "ner_backend": None,
                             "warnings": ["no input provided"]}}
        text, pmeta = extract_resume_text(filename or "", content)
        meta["parser_engine"] = pmeta.get("engine")
        if not text:
            warnings.append("extraction_failed:%s" % (pmeta.get("engine"),))

    meta["ner_backend"] = ner.ner_backend_name()
    sections = split_sections(text)
    entities = ner.extract_entities(text)

    return {
        "profile": _extract_profile(sections.get("header", []),
                                    text, entities),
        "contact": _extract_contact(entities),
        "skills": extract_skills_with_evidence(text, sections),
        "experience": _extract_experience(sections),
        "education": _extract_education(sections),
        "projects": _extract_projects(sections),
        "certifications": _extract_certifications(sections, entities),
        "raw_text": text,
        "meta": meta,
    }


def extraction_capabilities() -> Dict[str, bool]:
    return is_extraction_available()