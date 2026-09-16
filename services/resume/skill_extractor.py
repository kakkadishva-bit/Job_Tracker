"""
services/resume/skill_extractor.py
Evidence-based skill extraction.

Never trusts keyword matching alone: every skill carries
  - confidence : 0..1, blended from the strongest section it appears in
                 plus bonuses for corroboration in other sections
  - evidence   : up to 3 supporting sentences (trimmed)
  - source     : the strongest section it was found in
  - strength   : strong / medium / weak label
"""
import re
from typing import Dict, List

from services.resume.taxonomy import (
    SKILL_CATEGORIES, SOURCE_WEIGHTS, all_skills, canonical_skill,
    skill_category, strength_label,
)

_MAX_EVIDENCE = 3
_MAX_SENTENCE_LEN = 160

# Word-boundary-friendly variants for tokens that regex \b mishandles.
_SPECIAL_PATTERNS = {
    "c++": r"c\+\+",
    "c#": r"c#",
    "asp.net": r"asp\.net",
    ".net": r"\.net",
    "node.js": r"node\.?js",
    "vue.js": r"vue\.?js",
    "next.js": r"next\.?js",
    "nuxt.js": r"nuxt\.?js",
}


def _skill_pattern(skill: str) -> re.Pattern:
    key = skill.lower()
    core = _SPECIAL_PATTERNS.get(key, re.escape(key))
    # Allow e.g. "nodejs"/"node.js", "scikit-learn"/"scikit learn"
    core = core.replace(r"\ ", r"[\s\-_]?")
    return re.compile(r"(?<![A-Za-z0-9+#.])" + core + r"(?![A-Za-z0-9+#])",
                      re.IGNORECASE)


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?;])\s+|\n+")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]


def _trim(sentence: str, limit: int = _MAX_SENTENCE_LEN) -> str:
    s = " ".join(sentence.split())
    if len(s) <= limit:
        return s
    return s[: limit - 1].rstrip() + "\u2026"


def extract_skills_with_evidence(
        full_text: str, sections: Dict[str, List[str]]) -> List[Dict]:
    """
    Find taxonomy skills in the resume with evidence.

    Strategy per skill:
      1. scan every known section for matches
      2. record sentences as evidence per section
      3. source  = section with the highest SOURCE_WEIGHTS
      4. conf    = base(source) + corroboration bonuses, capped 0.98
    """
    flat = all_skills()
    section_texts = {name: "\n".join(lines)
                     for name, lines in sections.items()}
    # Include full text as its own "scope" for cross-section corroboration
    all_sentences = _sentences(full_text)

    results: List[Dict] = []
    for lookup, canonical in flat.items():
        pattern = _skill_pattern(canonical)
        per_section: Dict[str, List[str]] = {}

        for section, text in section_texts.items():
            if not text:
                continue
            hits = []
            for sentence in _sentences(text):
                if pattern.search(sentence):
                    hits.append(_trim(sentence))
            if hits:
                per_section[section] = hits

        if not per_section:
            continue

        # Strongest source section for this skill
        ranked = sorted(
            per_section.keys(),
            key=lambda s: SOURCE_WEIGHTS.get(s, 0.0),
            reverse=True)
        source = ranked[0]
        confidence = SOURCE_WEIGHTS.get(source, 0.35)

        # Corroboration: each additional distinct section adds weight
        confidence += 0.05 * (len(ranked) - 1)
        # Multiple distinct evidence sentences in the strongest section
        confidence += 0.02 * min(len(per_section[source]) - 1, 3)
        confidence = min(round(confidence, 2), 0.98)

        # Assemble evidence: prefer strongest section, then others
        evidence: List[str] = []
        for sec in ranked:
            for sent in per_section[sec]:
                if len(evidence) >= _MAX_EVIDENCE:
                    break
                if sent not in evidence:
                    evidence.append(sent)
            if len(evidence) >= _MAX_EVIDENCE:
                break

        results.append({
            "skill": canonical,
            "category": skill_category(canonical),
            "confidence": confidence,
            "evidence": evidence,
            "source": source,
            "strength": strength_label(confidence),
            "sections_seen": ranked,
        })

    results.sort(key=lambda s: s["confidence"], reverse=True)
    return results


__all__ = ["extract_skills_with_evidence", "canonical_skill",
           "SKILL_CATEGORIES"]