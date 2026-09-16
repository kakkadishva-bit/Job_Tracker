"""
services/resume/skill_intelligence.py
Evidence-based skill intelligence for JobAgent.

Determines per detected skill:
  - canonical name + category + aliases (normalization)
  - where it was found (section) and how many times (mentions)
  - confidence that the RESUME supports the skill
  - strength classification (STRONG / DEVELOPING / LIMITED / UNKNOWN)
  - estimated proficiency (beginner ... expert), clearly labelled as an
    ESTIMATE derived from resume evidence, not a verified assessment
  - real evidence sentences from the resume text (never invented)

100% local and deterministic: regex + taxonomy + section heuristics.
No OpenAI / Gemini / Claude / Ollama / LM Studio / Jan. No paid APIs.
"""
import re
from typing import Dict, List, Optional

from services.resume.section_splitter import split_sections, section_text
from services.resume.skill_registry import (
    ALIAS_TO_CANONICAL, CATEGORIES, CONTEXT_GATED, EXCLUSIONS,
    SPECIAL_PATTERNS, aliases_for, canonical_for, category_for,
)

# Where the skill is found ranks how strongly it supports "has skill".
SECTION_WEIGHTS: Dict[str, float] = {
    "experience": 0.92,      # 1. employment
    "projects": 0.88,        # 2. projects
    "certifications": 0.80,  # 3. certifications
    "education": 0.60,       # 4. education
    "skills": 0.38,          # 5. skills list
    "achievements": 0.70,
    "summary": 0.30,         # 6. summary/header
    "header": 0.30,
    "contact": 0.30,
    "other": 0.30,
}

ACTION_VERBS = {
    "built", "develop", "developed", "developing", "designed", "implement",
    "implemented", "implementing", "created", "automated", "deployed",
    "trained", "optimized", "migrated", "led", "managed", "maintained",
    "integrated", "architected", "engineered", "delivered", "improved",
    "scaled", "shipped", "wrote", "launched", "refactored", "streamlined",
    "reduced", "analysed", "analyzed", "modeled", "modelled", "processed",
    "built", "developed", "constructed", "programmed",
}

# Ambiguous skills that require corroborating words in the same sentence.
_GATE_WORDS: Dict[str, List[str]] = {
    "C": ["language", "programming", "compiler", "embedded", "developer",
          "code", "lens"],
    "R": ["language", "programming", "statistic", "analys", "data",
          "rstudio", "ggplot", "shiny", "cran"],
    "Go": ["language", "programming", "golang", "backend", "developer",
           "microservice", "concurrency"],
    "SQL": ["database", "quer", "join", "index", "schema", "relational",
            "server", "script"],
    "Computer Vision": ["computer", "vision", "image", "opencv",
                        "detection", "segmentation", "recognition"],
}

# Acronyms matched case-sensitively so "AI"/"ML" never match ordinary words.
ACRONYMS = {"ML", "AI", "NLP", "CV", "JS", "TS", "SQL", "R", "C", "Go", "CI"}
# Acronyms whose aliases must be matched case-sensitively even when the
# canonical name itself is also spelled out in full.
_STRICT_ACRONYM_ALIASES = {"ml", "ai", "nlp", "cv", "js", "ts", "sql"}

_MAX_EVIDENCE = 3
_MAX_SENTENCE_LEN = 160
_CONFIDENCE_CAP = 0.98

# ── Strength labels for resume-only analysis (no target job yet) ────
STRONG = "STRONG"
DEVELOPING = "DEVELOPING"
LIMITED = "LIMITED"
UNKNOWN = "UNKNOWN"

# ── Proficiency (estimate only) ─────────────────────────────────────
PROF_UNKNOWN = "unknown"
PROF_BEGINNER = "beginner"
PROF_DEVELOPING = "developing"
PROF_INTERMEDIATE = "intermediate"
PROF_ADVANCED = "advanced"
PROF_EXPERT = "expert"


def _trim(sentence: str, limit: int = _MAX_SENTENCE_LEN) -> str:
    s = " ".join(sentence.split())
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "\u2026"


_SENT_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def _sentences_per_section(sections: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for name, lines in sections.items():
        text = "\n".join(lines)
        out[name] = [s.strip() for s in _SENT_SPLIT.split(text) if s.strip()]
    return out
# ── Regex pattern building ──────────────────────────────────────────

def _pattern_for_alias(alias: str) -> str:
    if alias.lower() in SPECIAL_PATTERNS:
        return SPECIAL_PATTERNS[alias.lower()]
    core = re.escape(alias)
    core = core.replace(r"\ ", r"[\s\-_]?")
    return core


def _canonical_pattern(canonical: str) -> re.Pattern:
    """Primary matching pattern for a canonical skill (its aliases)."""
    # Ambiguous skills get hand-built patterns that cannot collide with
    # lookalikes: C != C++, R letter-only, Go != the verb "go".
    gated = {
        "C": r"(?<![A-Za-z0-9+#.])C(?![A-Za-z0-9+#])",
        "R": r"(?<![A-Za-z0-9+#.])R(?![A-Za-z0-9+#])",
        "Go": r"(?<![A-Za-z0-9+#.])Go(?![A-Za-z0-9+#])",
        "SQL": r"(?<![A-Za-z0-9+#.])SQL(?![A-Za-z0-9+#])",
    }
    if canonical in gated:
        return re.compile(gated[canonical])

    aliases = aliases_for(canonical)
    if not aliases:
        aliases = [canonical]
    parts = [_pattern_for_alias(a) for a in aliases]
    # Case sensitivity: acronym-style aliases (e.g. "ts" for TypeScript)
    # are matched loosely; the explicit canonical full name stays
    # case-insensitive via re.IGNORECASE on the whole alternation.
    filled = "(?:" + "|".join(parts) + ")"
    return re.compile(r"(?<![A-Za-z0-9+#.])" + filled + r"(?![A-Za-z0-9+#])",
                      re.IGNORECASE)


# Cache compiled patterns (registry is small; compile once).
_PATTERN_CACHE: Dict[str, re.Pattern] = {}


def _pattern(canonical: str) -> re.Pattern:
    if canonical not in _PATTERN_CACHE:
        _PATTERN_CACHE[canonical] = _canonical_pattern(canonical)
    return _PATTERN_CACHE[canonical]


def _has_gate_context(canonical: str, sentence: str) -> bool:
    """Verify an ambiguous skill appears in a genuine technical context."""
    words = _GATE_WORDS.get(canonical)
    if not words:
        return True
    lower = sentence.lower()
    return any(w in lower for w in words)


def _excluded_form(canonical: str, sentence: str) -> bool:
    """Reject lookalikes (Java!="JavaScript", React!="React Native")."""
    for frag in EXCLUSIONS.get(canonical, []):
        if re.search(r"(?i)" + frag, sentence):
            hits = list(_pattern(canonical).finditer(sentence))
            if hits and any(re.search(frag, sentence[max(0, m.start()-4):
                                                       m.end()+12])
                            for m in hits):
                return True
    return False


_SKILL_LIST_SEP = re.compile(r"[,;]|\bas\b|&|and")


def _looks_like_skill_list(sentence: str) -> bool:
    """Segment looks like a comma-separated skills line ("Python, SQL")."""
    tokens = [t.strip() for t in _SKILL_LIST_SEP.split(sentence) if t.strip()]
    # Each token must be a short label (<=20 chars), and the bulk of the
    # tokens must be recognisable taxonomy skills.
    if len(tokens) < 2:
        return False
    if any(len(t) > 20 for t in tokens):
        return False
    known = sum(1 for t in tokens if is_known_skill(t))
    return known >= 2 and known >= len(tokens) * 0.5


def _sentence_has_skill(canonical: str, sentence: str) -> bool:
    pat = _pattern(canonical)
    if not pat.search(sentence):
        return False
    if not _has_gate_context(canonical, sentence):
        # Gated skills may still be genuine when listed among other
        # known skills ("C, C++, Python") even without a context word.
        if not _looks_like_skill_list(sentence):
            return False
    if _excluded_form(canonical, sentence):
        return False
    return True


def normalize_skill(raw: str) -> Optional[str]:
    """Public helper: alias/token -> canonical name, or None."""
    return canonical_for(raw)


def is_known_skill(token: str) -> bool:
    return canonical_for(token) is not None
# ── Evidence collection per skill ───────────────────────────────────

def _collect_evidence(canonical: str,
                      sentences_by_section: Dict[str, List[str]]) -> Dict:
    """
    Returns per-skill evidence:
      sections_seen  list of sections the skill appears in
      mentions       total count across all sections
      evidence       up to 3 real sentences (trimmed, unique)
      action_verb    True if any evidence sentence uses an action verb
      _raw           per-section meta for scoring
    """
    sections_seen: List[str] = []
    mentions = 0
    evidence: List[str] = []
    has_action = False
    cert_evidence = False

    for section, sentences in sentences_by_section.items():
        local = 0
        for sentence in sentences:
            if not _sentence_has_skill(canonical, sentence):
                continue
            local += 1
            mentions += 1
            if len(evidence) < _MAX_EVIDENCE and sentence not in evidence:
                evidence.append(_trim(sentence))
            words = set(re.findall(r"[A-Za-z]+", sentence.lower()))
            if words & ACTION_VERBS:
                has_action = True
        if local:
            sections_seen.append(section)
            if section == "certifications":
                cert_evidence = True

    return {"sections_seen": sections_seen, "mentions": mentions,
            "evidence": evidence, "action_verb": has_action,
            "cert_evidence": cert_evidence}


def _confidence(section: str, sections_seen: int, mentions: int,
                action_verb: bool, cert_evidence: bool) -> float:
    """Confidence that the RESUME supports the skill (0..1, capped)."""
    conf = SECTION_WEIGHTS.get(section, 0.30)
    # Corroboration: appearing in more than one section adds weight
    conf += 0.02 * (sections_seen - 1) if sections_seen > 1 else 0.0
    # Repeated meaningful usage strengthens evidence
    conf += 0.01 * min(mentions - 1, 4)
    if action_verb:
        conf += 0.04
    if cert_evidence:
        conf += 0.05
    return round(min(conf, _CONFIDENCE_CAP), 3)


def _strength_label(confidence: float, sections_seen: List[str]) -> str:
    """Resume-only labels (no target job -> never gap labels)."""
    meaningful = any(s in ("experience", "projects", "achievements",
                           "certifications") for s in sections_seen)
    if confidence >= 0.75 and meaningful:
        return STRONG
    if confidence >= 0.50:
        return DEVELOPING
    if confidence >= 0.35:
        return LIMITED
    return UNKNOWN


def _proficiency(sections_seen: List[str], mentions: int,
                 action_verb: bool, cert_evidence: bool) -> Dict:
    """
    Conservative ESTIMATE from resume evidence, never a verified fact.
    Returns (level, reason).
    """
    meaningful = [s for s in sections_seen
                  if s in ("experience", "projects", "achievements",
                           "certifications")]
    n_meaningful = mentions if meaningful else 0

    if n_meaningful == 0:
        return PROF_UNKNOWN, "only listed, no usage context found"
    if n_meaningful <= 1 and not action_verb:
        return PROF_BEGINNER, "single mention with limited usage context"
    if n_meaningful <= 2:
        return PROF_DEVELOPING, f"{mentions} mentions, light usage context"
    if n_meaningful <= 4:
        return PROF_INTERMEDIATE, f"{mentions} mentions across " \
                                  f"{', '.join(meaningful)}"
    if n_meaningful <= 6:
        return PROF_ADVANCED, f"{mentions} mentions in " \
                              f"{', '.join(meaningful)} with repeated use"
    return PROF_EXPERT, f"{mentions} extensive mentions across " \
                        f"{', '.join(meaningful)}"
# ── Public API ──────────────────────────────────────────────────────

def extract_skills(resume_text: str,
                   sections: Optional[Dict[str, List[str]]] = None) -> List[Dict]:
    """
    Run the full skill intelligence pipeline over resume text.

    Returns a list of per-skill records:
      skill, category, aliases, confidence, strength, proficiency,
      proficiency_reason, source, mentions, sections_seen, evidence,
      action_verb, certification_evidence, gap (None until job matching)
    """
    if sections is None:
        sections = split_sections(resume_text or "")
    sentences = _sentences_per_section(sections)

    results: List[Dict] = []
    for canonical, cat in CATEGORIES.items():
        meta = _collect_evidence(canonical, sentences)
        if not meta["sections_seen"]:
            continue
        primary = max(meta["sections_seen"],
                      key=lambda s: SECTION_WEIGHTS.get(s, 0.30))
        confidence = _confidence(
            primary, len(meta["sections_seen"]), meta["mentions"],
            meta["action_verb"], meta["cert_evidence"])
        level, reason = _proficiency(
            meta["sections_seen"], meta["mentions"], meta["action_verb"],
            meta["cert_evidence"])

        results.append({
            "skill": canonical,
            "category": category_for(canonical),
            "aliases": aliases_for(canonical),
            "confidence": confidence,
            "strength": _strength_label(confidence, meta["sections_seen"]),
            "proficiency": level,
            "proficiency_reason": reason,
            "source": primary,
            "mentions": meta["mentions"],
            "sections_seen": meta["sections_seen"],
            "evidence": meta["evidence"],
            "action_verb": meta["action_verb"],
            "certification_evidence": meta["cert_evidence"],
            "gap": None,  # filled by the future job-matching layer only
        })

    results.sort(key=lambda r: (r["confidence"], r["mentions"]),
                 reverse=True)
    return results


def analyze_skills(extracted_resume: Dict) -> Dict:
    """
    Accept a service.resume.extractor.resume dict and return a skill
    intelligence summary suitable for ATS / matching / recommendations.
    """
    text = (extracted_resume or {}).get("raw_text", "")
    skills = extract_skills(text)
    known = [s for s in skills if s["strength"] in (STRONG, DEVELOPING)]
    return {
        "total_skills": len(skills),
        "skills": skills,
        "top_skills": [s["skill"] for s in known[:10]],
        "summary": {
            "strong": sum(1 for s in skills if s["strength"] == STRONG),
            "developing": sum(1 for s in skills
                              if s["strength"] == DEVELOPING),
            "limited": sum(1 for s in skills
                           if s["strength"] == LIMITED),
            "unknown": sum(1 for s in skills if s["strength"] == UNKNOWN),
            "gaps": [],  # no target job provided; gap analysis comes later
        },
    }
