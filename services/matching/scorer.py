"""Combined scorer module."""
import logging
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

WEIGHTS = {
    "job_relevance": 0.30,
    "evidence_strength": 0.20,
    "technical_skills": 0.15,
    "experience_relevance": 0.15,
    "ats_compatibility": 0.10,
    "achievements": 0.05,
    "education_certs": 0.05,
}

# False-match guard pairs (lowercased; never merge these technologies)
_FALSE_MATCH_PAIRS = [
    ("java", "javascript"),
    ("c", "c++"),
    ("c", "c#"),
    ("c++", "c#"),
    ("react", "react native"),
    ("amazon web services", "microsoft azure"),
    ("aws", "azure"),
    ("mysql", "postgresql"),
    ("go", "r"),
    ("vue", "react"),
    ("angular", "react"),
    ("tensorflow", "pytorch"),
    ("docker", "kubernetes"),
]


def _check_false_match(skill_a: str, skill_b: str) -> bool:
    """True when two skill names must never be merged.

    Guards: Java/JavaScript, C/C++/C#, React/React Native, AWS/Azure,
    MySQL/PostgreSQL, Go/R.
    """
    a = (skill_a or "").strip().lower()
    b = (skill_b or "").strip().lower()
    if not a or not b or a == b:
        return False
    for s1, s2 in _FALSE_MATCH_PAIRS:
        if (a == s1 and b == s2) or (a == s2 and b == s1):
            return True
    return False


@dataclass
class ScoreBreakdown:
    job_relevance: float = 0.0
    evidence_strength: float = 0.0
    technical_skills: float = 0.0
    experience_relevance: float = 0.0
    ats_compatibility: float = 0.0
    achievements: float = 0.0
    education_certs: float = 0.0
    total: float = 0.0
    explanation: List[str] = field(default_factory=list)


# ── Semantic similarity (CPU-friendly, cached, no LLM) ────────────────────
_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_SEMANTIC_THRESHOLD = 0.55
_embedding_cache: Dict[str, object] = {}
_model_instance = None


def _embedding_model():
    global _model_instance
    if _model_instance is not None:
        return _model_instance
    try:
        from services.rag.embeddings import EmbeddingGenerator
        _model_instance = EmbeddingGenerator(model_name=_MODEL_NAME)
    except Exception:
        _model_instance = None
    return _model_instance


def _token_overlap(a: str, b: str) -> float:
    ta = set(re.findall(r"[a-z0-9+#.]+", a.lower()))
    tb = set(re.findall(r"[a-z0-9+#.]+", b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def semantic_similarity(a: str, b: str) -> float:
    """Similarity in [0,1] for two skill phrases.

    Exact equality -> 1.0. False-match pairs (Java/JavaScript, C/C++,
    React/React Native, AWS/Azure, MySQL/PostgreSQL, Go/R) -> 0.0 so
    confusable technologies are never merged.
    """
    if not a or not b:
        return 0.0
    if a.strip().lower() == b.strip().lower():
        return 1.0
    if _check_false_match(a, b):
        return 0.0
    gen = _embedding_model()
    if gen is not None and getattr(gen, "model", None) is not None:
        try:
            import numpy as np
            ka, kb = a.strip().lower(), b.strip().lower()
            if ka not in _embedding_cache:
                _embedding_cache[ka] = gen.embed([a])[0]
            if kb not in _embedding_cache:
                _embedding_cache[kb] = gen.embed([b])[0]
            va, vb = _embedding_cache[ka], _embedding_cache[kb]
            denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
            if denom > 0:
                return max(0.0, min(1.0, float(np.dot(va, vb)) / denom))
        except Exception:
            pass
    return _token_overlap(a, b)


def _is_skill_match(jd_skill: str, resume_skill: str) -> bool:
    """True if a resume skill satisfies a JD skill (exact or semantic)."""
    if not jd_skill or not resume_skill:
        return False
    if jd_skill.strip().lower() == resume_skill.strip().lower():
        if _check_false_match(jd_skill, resume_skill):
            return False
        return True
    if _check_false_match(jd_skill, resume_skill):
        return False
    return semantic_similarity(jd_skill, resume_skill) >= _SEMANTIC_THRESHOLD


def _match_jd_skill(jd_skill: str, resume_skills: List[str]) -> bool:
    for rs in resume_skills:
        if _is_skill_match(jd_skill, rs):
            return True
    return False


def _compute_job_relevance(resume: dict, jd_skills: List[str]) -> Tuple[float, List[str]]:
    explanation = []
    resume_skills = resume.get("skills", [])
    if not isinstance(resume_skills, list):
        resume_skills = []

    if not jd_skills:
        return 50.0, ["No job skills to match against"]

    resume_names = []
    for s in resume_skills:
        name = s.get("skill", s) if isinstance(s, dict) else s
        if isinstance(name, str) and name.strip():
            resume_names.append(name.strip())

    matched = 0
    false_matches = 0
    semantic_hits = 0
    for jd_skill in jd_skills:
        hit = False
        exact = False
        for rs in resume_names:
            if jd_skill.strip().lower() == rs.lower():
                if _check_false_match(jd_skill, rs):
                    false_matches += 1
                    hit = False
                    exact = True
                    break
                hit = True
                exact = True
                break
        if not exact:
            for rs in resume_names:
                if _check_false_match(jd_skill, rs):
                    continue
                if semantic_similarity(jd_skill, rs) >= _SEMANTIC_THRESHOLD:
                    hit = True
                    semantic_hits += 1
                    break
        if hit:
            matched += 1

    total_required = len(jd_skills)
    score = (matched / total_required * 100) if total_required > 0 else 0.0

    explanation.append("Matched " + str(matched) + "/" + str(total_required) + " required skills")
    if semantic_hits > 0:
        explanation.append("Semantic matches: " + str(semantic_hits))
    if false_matches > 0:
        explanation.append("Prevented " + str(false_matches) + " false match(es)")

    return min(100.0, score), explanation


def _compute_evidence_strength(resume: dict, jd_skills: List[str]) -> Tuple[float, List[str]]:
    explanation = []
    resume_skills = resume.get("skills", [])
    if not isinstance(resume_skills, list):
        resume_skills = []

    if not jd_skills or not resume_skills:
        return 0.0, ["No skill evidence available"]

    evidence_scores = {}
    evidence_names = []
    for s in resume_skills:
        if isinstance(s, dict):
            raw = s.get("skill", "")
            if not isinstance(raw, str) or not raw.strip():
                continue
            skill_name = raw.strip().lower()
            try:
                confidence = float(s.get("confidence", 0.0))
            except Exception:
                confidence = 0.0
            strength = s.get("strength", "UNKNOWN")
            try:
                mentions = int(s.get("mentions", 1))
            except Exception:
                mentions = 1
            # Keyword-stuffing guard: repeated mentions give diminishing
            # returns and a bare skill word without projects/experience
            # evidence is capped.
            mention_factor = min(max(mentions, 1), 5) / 5.0
            strength_multiplier = {"STRONG": 1.0, "DEVELOPING": 0.7, "LIMITED": 0.4, "UNKNOWN": 0.2}.get(str(strength).upper(), 0.2)
            raw_evidence = s.get("evidence", []) or []
            if not raw_evidence and str(strength).upper() in ("UNKNOWN", "LIMITED"):
                confidence = min(confidence, 0.3)
            evidence_scores[skill_name] = confidence * strength_multiplier * mention_factor
            evidence_names.append(raw.strip())

    if not evidence_scores:
        return 0.0, ["No evidence scores computed"]

    total_evidence = 0.0
    matched_count = 0
    for jd_skill in jd_skills:
        best = 0.0
        for rs_name, ev in zip(evidence_names, [evidence_scores[n.lower()] for n in evidence_names]):
            if _check_false_match(jd_skill, rs_name):
                continue
            if jd_skill.strip().lower() == rs_name.lower():
                best = max(best, ev)
            elif semantic_similarity(jd_skill, rs_name) >= _SEMANTIC_THRESHOLD:
                best = max(best, ev * 0.85)
        if best > 0:
            total_evidence += best
            matched_count += 1

    if matched_count == 0:
        return 0.0, ["No matched skills with evidence"]

    avg_evidence = total_evidence / matched_count
    score = avg_evidence * 100

    explanation.append("Average evidence strength: " + str(round(avg_evidence, 2)))
    explanation.append("Skills with evidence: " + str(matched_count))

    return min(100.0, score), explanation


def _compute_technical_skills(resume: dict, jd_skills: List[str]) -> Tuple[float, List[str]]:
    explanation = []
    resume_skills = resume.get("skills", [])

    if not jd_skills:
        return 50.0, ["No technical skills required"]

    technical_categories = {"Language", "Framework", "Tool", "Database", "Cloud", "ML Library", "Practice", "Field"}

    resume_technical = set()
    for s in resume_skills:
        if isinstance(s, dict):
            skill_name = s.get("skill", "").lower()
            category = s.get("category", "")
            if category in technical_categories:
                resume_technical.add(skill_name)

    matched_tech = 0
    for jd_skill in jd_skills:
        if jd_skill.lower() in resume_technical:
            matched_tech += 1

    total_tech = len(jd_skills)
    score = (matched_tech / total_tech * 100) if total_tech > 0 else 0.0

    explanation.append("Technical skills matched: " + str(matched_tech) + "/" + str(total_tech))

    return min(100.0, score), explanation


def _compute_experience_relevance(resume: dict, jd_seniority: Optional[str],
                                  jd_exp_min: Optional[int]) -> Tuple[float, List[str]]:
    explanation = []
    profile = resume.get("profile", {})
    experience = resume.get("experience", [])

    total_years = 0
    for exp in experience:
        if isinstance(exp, dict):
            duration = exp.get("duration", "")
            m = re.search(r"(\d+)\s*(?:years?|yrs?)", duration, re.I)
            if m:
                total_years += int(m.group(1))
            else:
                m = re.search(r"(\d+)\s*months?", duration, re.I)
                if m:
                    total_years += int(m.group(1)) / 12

    if total_years == 0 and isinstance(profile, dict):
        total_years = profile.get("years_experience", 0)

    score = 50.0
    if jd_exp_min is not None:
        if total_years >= jd_exp_min:
            score = min(100.0, 70 + (total_years - jd_exp_min) * 5)
            explanation.append("Experience: " + str(int(total_years)) + " years >= " + str(jd_exp_min))
        else:
            deficit = jd_exp_min - total_years
            score = max(0.0, 50 - deficit * 15)
            explanation.append("Experience: " + str(int(total_years)) + " years < " + str(jd_exp_min))
    else:
        score = 60.0
        explanation.append("No explicit experience requirement")

    if jd_seniority and total_years > 0:
        seniority_years = {"junior": 1, "mid": 3, "senior": 5, "lead": 8}
        expected_years = seniority_years.get(jd_seniority, 3)
        if total_years >= expected_years:
            score = min(100.0, score + 10)
            explanation.append("Seniority match: " + jd_seniority)
        else:
            score = max(0.0, score - 10)
            explanation.append("Seniority mismatch: " + jd_seniority)

    return min(100.0, score), explanation


def _compute_ats_compatibility(resume: dict) -> Tuple[float, List[str]]:
    explanation = []

    checks = [
        (resume.get("experience"), "Experience section present"),
        (resume.get("education"), "Education section present"),
        (resume.get("skills"), "Skills section present"),
        (resume.get("projects"), "Projects section present"),
        (resume.get("contact", {}).get("email"), "Email present"),
        (resume.get("contact", {}).get("phone"), "Phone present"),
    ]

    passed = sum(1 for val, _ in checks if val)
    score = passed / len(checks) * 100

    for val, desc in checks:
        if val:
            explanation.append("OK: " + desc)
        else:
            explanation.append("MISSING: " + desc)

    return min(100.0, score), explanation


def _compute_achievements(resume: dict) -> Tuple[float, List[str]]:
    explanation = []
    raw_text = resume.get("raw_text", "")

    if not raw_text:
        return 0.0, ["No resume text available"]

    achievement_patterns = [
        r"\d+%\s*(?:increase|decrease|reduction|improvement|growth)",
        r"\$\d+[KkMm]?\s*(?:revenue|savings|cost|budget)",
        r"\d+x\s*(?:faster|improvement|increase)",
        r"(?:reduced|improved|increased|decreased|saved)\s+\d+",
    ]

    matches = 0
    for pattern in achievement_patterns:
        matches += len(re.findall(pattern, raw_text, re.I))

    score = min(100.0, matches * 20)
    explanation.append("Quantifiable achievements found: " + str(matches))

    return score, explanation


def _compute_education_certs(resume: dict, jd_education: List[str],
                              jd_certs: List[str]) -> Tuple[float, List[str]]:
    explanation = []
    score = 50.0

    if not jd_education and not jd_certs:
        return score, ["No education/cert requirements"]

    resume_edu = resume.get("education", [])
    resume_certs = resume.get("certifications", [])

    edu_score = 50.0
    if jd_education:
        if resume_edu:
            edu_score = 80.0
            explanation.append("Education requirement met")
        else:
            edu_score = 20.0
            explanation.append("Education requirement NOT met")

    cert_score = 50.0
    if jd_certs:
        if resume_certs:
            cert_score = 80.0
            explanation.append("Certifications present")
        else:
            cert_score = 20.0
            explanation.append("Required certifications missing")

    if jd_education and jd_certs:
        score = edu_score * 0.6 + cert_score * 0.4
    elif jd_education:
        score = edu_score
    elif jd_certs:
        score = cert_score

    return min(100.0, score), explanation


def calculate_match_score(resume: dict, jd) -> ScoreBreakdown:
    breakdown = ScoreBreakdown()

    breakdown.job_relevance, expl = _compute_job_relevance(resume, jd.required_skills)
    breakdown.explanation.extend(expl)

    breakdown.evidence_strength, expl = _compute_evidence_strength(resume, jd.all_skills)
    breakdown.explanation.extend(expl)

    breakdown.technical_skills, expl = _compute_technical_skills(resume, jd.all_skills)
    breakdown.explanation.extend(expl)

    breakdown.experience_relevance, expl = _compute_experience_relevance(
        resume, jd.seniority, jd.experience_years_min
    )
    breakdown.explanation.extend(expl)

    breakdown.ats_compatibility, expl = _compute_ats_compatibility(resume)
    breakdown.explanation.extend(expl)

    breakdown.achievements, expl = _compute_achievements(resume)
    breakdown.explanation.extend(expl)

    breakdown.education_certs, expl = _compute_education_certs(
        resume, jd.education, jd.certifications
    )
    breakdown.explanation.extend(expl)

    breakdown.total = (
        breakdown.job_relevance * WEIGHTS["job_relevance"]
        + breakdown.evidence_strength * WEIGHTS["evidence_strength"]
        + breakdown.technical_skills * WEIGHTS["technical_skills"]
        + breakdown.experience_relevance * WEIGHTS["experience_relevance"]
        + breakdown.ats_compatibility * WEIGHTS["ats_compatibility"]
        + breakdown.achievements * WEIGHTS["achievements"]
        + breakdown.education_certs * WEIGHTS["education_certs"]
    )

    breakdown.total = max(0.0, min(100.0, breakdown.total))

    return breakdown

