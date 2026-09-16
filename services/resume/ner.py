"""
services/resume/ner.py
Named-entity extraction for resumes with a CPU-friendly backend chain:

  1. transformers + oksomu/resume-ner  (only if transformers+torch are
     installed; env RESUME_NER_BACKEND=transformers or "auto")
  2. spaCy en_core_web_sm              (only if spaCy + model installed)
  3. Built-in regex NER                (always available, zero deps)

The regex layer also supplies resume-specific labels the generic models
do not emit (EMAIL, PHONE, DEGREE, INSTITUTION, CERTIFICATION), and it
runs for every backend to fill gaps. All model labels are mapped onto
the canonical label set:

PERSON EMAIL PHONE LOCATION JOB_TITLE COMPANY DATE EDUCATION DEGREE
INSTITUTION SKILL CERTIFICATION PROJECT EXPERIENCE
"""
import os
import re
from typing import Dict, List, Optional

try:  # reuse the existing Indian-city knowledge base
    from utils.query_parser import QueryParser
    _INDIAN_CITIES = QueryParser.INDIAN_CITIES
except Exception:  # pragma: no cover - defensive
    _INDIAN_CITIES = ["bangalore", "bengaluru", "mumbai", "delhi", "pune",
                      "hyderabad", "chennai", "kolkata", "gurgaon", "noida"]

# ── Canonical labels ────────────────────────────────────────────────
LABELS = {"PERSON", "EMAIL", "PHONE", "LOCATION", "JOB_TITLE", "COMPANY",
          "DATE", "EDUCATION", "DEGREE", "INSTITUTION", "SKILL",
          "CERTIFICATION", "PROJECT", "EXPERIENCE"}

# Map HF token-classifier labels (model-specific) to canonical.
HF_LABEL_MAP = {
    "person": "PERSON", "per": "PERSON",
    "email": "EMAIL", "phone": "PHONE", "phone_number": "PHONE",
    "loc": "LOCATION", "location": "LOCATION", "gpe": "LOCATION",
    "address": "LOCATION",
    "job_title": "JOB_TITLE", "title": "JOB_TITLE", "role": "JOB_TITLE",
    "org": "COMPANY", "organization": "COMPANY", "company": "COMPANY",
    "employer": "COMPANY",
    "date": "DATE",
    "degree": "DEGREE", "education": "EDUCATION",
    "university": "INSTITUTION", "college": "INSTITUTION",
    "skills": "SKILL", "skill": "SKILL", "hard_skill": "SKILL",
    "soft_skill": "SKILL",
    "certification": "CERTIFICATION",
    "project": "PROJECT", "experience": "EXPERIENCE",
}

# ── Regex patterns (always-on layer) ────────────────────────────────
RE_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
RE_PHONE = re.compile(
    r"(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)[\s.-]?)?"
    r"\d{3}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)"
    r"|\+\d{1,3}[\s.-]?\d{5}[\s.-]?\d{5}(?!\d)")
RE_LINKEDIN = re.compile(
    r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-/%]+", re.I)
RE_GITHUB = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+", re.I)
RE_DATE = re.compile(
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\s*\d{4}\b"
    r"|\b(?:19|20)\d{2}\s*(?:-|\u2013|\u2014|to)\s*"
    r"(?:(?:19|20)\d{2}|present|current|date)\b"
    r"|\b(?:19|20)\d{2}\b", re.I)
RE_DEGREE = re.compile(
    r"\b(B\.?Tech|B\.?E\.?|B\.?Sc\.?|B\.?C\.?A\.?|B\.?Com\.?|"
    r"Bachelor(?:'s)?(?:\s+of\s+\w+)?|M\.?Tech|M\.?E\.?|M\.?Sc\.?|"
    r"M\.?C\.?A\.?|M\.?S\.?|Master(?:'s)?(?:\s+of\s+\w+)?|M\.?B\.?A\.?|"
    r"Ph\.?D\.?|Doctorate|Diploma|Associate(?:'s)?\s+degree|"
    r"High\s+School|Intermediate)(?![A-Za-z])", re.I)
RE_INSTITUTION = re.compile(
    r"\b[\w.'&\-\s]*\b(?:University|College|Institute|School|Academy|"
    r"IIT|NIT|IIIT|Polytechnic)\b[\w.'&\-\s]*", re.I)
RE_LOCATION = re.compile(
    r"\b([A-Z][a-zA-Z]+(?:[ \t][A-Z][a-zA-Z]+)?),[ \t]*"
    r"([A-Z]{2}\b|[A-Z][a-zA-Z]+)\b")
# Values that look like locations but are really roles/degrees/etc.
_LOCATION_FALSE_POSITIVE = re.compile(
    r"\b(engineer|developer|manager|analyst|scientist|designer|"
    r"bachelor|master|b\.?tech|m\.?tech|ph\.?d)\b", re.I)
RE_URL = re.compile(
    r"(?:https?://)?(?:www\.)?[\w\-]+\.(?:com|io|dev|me|app)"
    r"(?:/[\w\-./%?]*)?", re.I)
RE_CERT = re.compile(
    r"\b((?:AWS|Azure|GCP|Google)\s+Certified[\w\s.&+\-]*|"
    r"Certified\s+[A-Z][\w\s.&+\-]{2,40}|[\w\s.&+\-]{2,40}\s+Certified|"
    r"PMP|CCNA|CCNP|CISSP|CEH|OCA|OCP|SCJP|RHCE|CKA)\b")
RE_ROLE = re.compile(
    r"\b(Senior|Junior|Lead|Staff|Principal|Associate|Chief)?\s*"
    r"(Software|Frontend|Backend|Full[\s\-]?Stack|Web|Mobile|Data|"
    r"Machine\s+Learning|ML|AI|DevOps|Cloud|Systems|Security|Network|"
    r"QA|Test|Product|Project|Program|Business|Marketing|Sales|HR|"
    r"Finance|Graphic|UI|UX)\s+"
    r"(Developer|Engineer|Scientist|Analyst|Manager|Designer|Architect|"
    r"Administrator|Consultant|Intern|Associate)\b", re.I)
RE_COMPANY_SUFFIX = re.compile(
    r"\b[\w.&'\-]+(?:\s+[\w.&'\-]+){0,3}\s+"
    r"(?:Technologies|Technology|Labs|Laboratories|Solutions|Systems|"
    r"Software|Services|Consulting|Consultancy|Infotech|Digital|Media|"
    r"Analytics|Corp(?:oration)?|Inc\.?|LLC|Ltd\.?|Pvt\.?\s+Ltd\.?|"
    r"Limited|Group|Partners|Ventures|Studio)\b", re.I)
_ROLE_NOUNS = re.compile(
    r"\b(engineer|developer|scientist|analyst|manager|designer|architect|"
    r"administrator|consultant|intern|associate|lead)\b", re.I)


def _norm_hf_label(label: str) -> Optional[str]:
    """Map a model label (possibly B-/I- prefixed) to a canonical label."""
    base = label.lower()
    for prefix in ("b-", "i-"):
        if base.startswith(prefix):
            base = base[2:]
    return HF_LABEL_MAP.get(base)


# ── Backend loaders (lazy, cached, never fatal) ─────────────────────

_HF_NER = {"loaded": False, "pipeline": None}
_SPACY_NLP = {"loaded": False, "nlp": None}


def _wants_model_backend() -> bool:
    return os.getenv("RESUME_NER_BACKEND", "auto").lower() in (
        "auto", "transformers", "spacy")


def load_hf_ner():
    """oksomu/resume-ner via transformers, or None if unavailable."""
    if _HF_NER["loaded"]:
        return _HF_NER["pipeline"]
    _HF_NER["loaded"] = True
    if not _wants_model_backend():
        return None
    try:
        from transformers import pipeline  # type: ignore
        _HF_NER["pipeline"] = pipeline(
            "token-classification", model="oksomu/resume-ner",
            aggregation_strategy="simple")
    except Exception:
        _HF_NER["pipeline"] = None
    return _HF_NER["pipeline"]


def load_spacy():
    """spaCy small model, or None if unavailable."""
    if _SPACY_NLP["loaded"]:
        return _SPACY_NLP["nlp"]
    _SPACY_NLP["loaded"] = True
    if not _wants_model_backend():
        return None
    try:
        import spacy  # type: ignore
        _SPACY_NLP["nlp"] = spacy.load("en_core_web_sm")
    except Exception:
        _SPACY_NLP["nlp"] = None
    return _SPACY_NLP["nlp"]


def ner_backend_name() -> str:
    if load_hf_ner() is not None:
        return "transformers:oksomu/resume-ner"
    if load_spacy() is not None:
        return "spacy:en_core_web_sm"
    return "regex"


# ── Regex extraction layer (always on) ──────────────────────────────

def _dedupe(entities: List[Dict], key: str = "value") -> List[Dict]:
    seen = set()
    out = []
    for e in entities:
        k = (e.get("label"), str(e.get(key, "")).lower())
        if k in seen:
            continue
        seen.add(k)
        out.append(e)
    return out


def extract_regex_entities(text: str) -> List[Dict]:
    """Deterministic entity extraction; runs with or without a model."""
    entities: List[Dict] = []

    def add(label, value, section="header"):
        if value and str(value).strip():
            entities.append({"label": label, "value": str(value).strip(),
                             "section": section, "source": "regex"})

    for m in RE_EMAIL.finditer(text):
        add("EMAIL", m.group(0))
    for m in RE_PHONE.finditer(text):
        add("PHONE", m.group(0))
    for m in RE_LINKEDIN.finditer(text):
        add("URL", m.group(0))
    for m in RE_GITHUB.finditer(text):
        add("URL", m.group(0))
    for m in RE_DATE.finditer(text):
        add("DATE", m.group(0))
    for m in RE_DEGREE.finditer(text):
        add("DEGREE", m.group(0))
    for m in RE_INSTITUTION.finditer(text):
        v = m.group(0).strip()
        if len(v.split()) <= 8:
            add("INSTITUTION", v)
    for m in RE_CERT.finditer(text):
        add("CERTIFICATION", m.group(0))
    for m in RE_ROLE.finditer(text):
        add("JOB_TITLE", m.group(0).strip())
    for m in RE_COMPANY_SUFFIX.finditer(text):
        add("COMPANY", m.group(0).strip())

    # Locations: "City, ST/Country" plus known Indian cities
    for m in RE_LOCATION.finditer(text):
        candidate = f"{m.group(1)}, {m.group(2)}"
        if not _LOCATION_FALSE_POSITIVE.search(m.group(1)):
            add("LOCATION", candidate)
    lowered = text.lower()
    for city in _INDIAN_CITIES:
        if city in lowered:
            add("LOCATION", city.title())

    return _dedupe(entities)


# ── Model backends ──────────────────────────────────────────────────

def extract_hf_entities(text: str) -> List[Dict]:
    pipe = load_hf_ner()
    if pipe is None:
        return []
    out: List[Dict] = []
    try:
        for ent in pipe(text[:10000]):
            label = _norm_hf_label(ent.get("entity_group", ""))
            if not label or label not in LABELS:
                continue
            out.append({"label": label, "value": ent["word"].strip(),
                        "section": "text", "source": "transformers",
                        "confidence": round(float(ent.get("score", 0.0)), 3)})
    except Exception:
        return []
    return _dedupe(out)


def extract_spacy_entities(text: str) -> List[Dict]:
    nlp = load_spacy()
    if nlp is None:
        return []
    out: List[Dict] = []
    try:
        for ent in nlp(text[:10000]).ents:
            label = HF_LABEL_MAP.get(ent.label_.lower())
            if not label or label not in LABELS:
                continue
            out.append({"label": label, "value": ent.text.strip(),
                        "section": "text", "source": "spacy",
                        "confidence": 0.75})
    except Exception:
        return []
    return _dedupe(out)


# ── Public entry point ──────────────────────────────────────────────

def extract_entities(text: str) -> List[Dict]:
    """
    Run the backend chain: HF NER -> spaCy -> regex, then merge with
    regex results as the base (regex owns deterministic labels).
    """
    merged = extract_regex_entities(text)
    for backend in (extract_hf_entities, extract_spacy_entities):
        for ent in backend(text):
            merged.append(ent)
    return _dedupe(merged)