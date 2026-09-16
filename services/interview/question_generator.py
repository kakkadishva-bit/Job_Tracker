"""services/interview/question_generator.py - Generates adaptive interview questions."""
import random
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

INTRODUCTION_MESSAGES = [
    "Hi! I'm your AI interviewer. I'll be asking you questions based on your background and the target role. Let's get started!",
    "Welcome to your interview practice. I'm here to simulate a real technical interview based on your resume and the role you're targeting.",
    "Thanks for joining us today. I have some questions prepared based on your experience and the target position.",
]

BEHAVIORAL_OPENERS = [
    "Tell me about yourself and walk me through your resume.",
    "Walk me through your background and why you're interested in this role.",
    "Start by telling me about your journey and what excites you about this position.",
]

QUESTION_TEMPLATES: Dict[str, Dict[str, List[str]]] = {
    "technical": {
        "python": [
            "What are Python's key strengths and when would you choose it over other languages?",
            "Explain the difference between a list and a tuple in Python.",
            "How do Python's decorators work, and can you give a practical example?",
            "What is the GIL and how does it affect multi-threaded Python programs?",
            "How do Python context managers work and when would you use them?",
        ],
        "machine_learning": [
            "Can you explain the difference between supervised and unsupervised learning?",
            "What is overfitting and how can you prevent it in a machine learning model?",
            "Walk me through how you would approach building a recommendation system.",
            "How do you evaluate the performance of a classification model?",
            "What are some techniques to handle imbalanced datasets?",
        ],
        "docker": [
            "What is Docker and how does containerization differ from virtualization?",
            "How would you reduce the size of a Docker image?",
            "Explain Docker networking and how containers communicate.",
        ],
        "fastapi": [
            "What are the main advantages of FastAPI over Flask or Django REST framework?",
            "How do you handle dependency injection in FastAPI?",
            "How would you implement authentication in a FastAPI application?",
        ],
        "rag": [
            "Explain how RAG (Retrieval-Augmented Generation) works and its key components.",
            "Why would you use RAG instead of just fine-tuning a language model?",
            "How would you reduce hallucinations in a RAG system?",
            "How do you evaluate whether a RAG system is actually improving answer quality?",
        ],
        "kubernetes": [
            "What is Kubernetes and what problems does it solve?",
            "Explain the difference between a Pod, Deployment, and Service in Kubernetes.",
            "How does Kubernetes handle scaling of applications?",
        ],
        "sql": [
            "What is the difference between INNER JOIN and LEFT JOIN?",
            "Explain the difference between WHERE and HAVING clauses.",
            "What are database indexes and when should you use them?",
            "How would you optimize a slow-running SQL query?",
        ],
        "aws": [
            "What are the core services you would use to deploy a web application on AWS?",
            "Explain how you would set up CI/CD on AWS.",
            "How does auto-scaling work in AWS?",
        ],
    },
    "behavioral": {
        "general": [
            "Tell me about a time you had to work with a difficult team member.",
            "Describe a situation where you had to learn a new technology quickly.",
            "Tell me about a challenging bug you fixed and how you approached it.",
            "Give me an example of a time you had to make a trade-off between quality and speed.",
        ],
    },
    "system_design": {
        "general": [
            "Design a URL shortening service like bit.ly.",
            "How would you design a system that handles millions of concurrent users?",
            "Design a notification system that pushes real-time alerts.",
            "How would you design a rate limiter for an API?",
        ],
    },
    "problem_solving": {
        "general": [
            "How would you debug a production issue where API response times have doubled?",
            "How would you design a system to detect spam in real-time?",
        ],
    },
}

# Resume-claim-specific follow-up questions
RESUME_FOLLOWUPS = {
    "Built a RAG chatbot": "You mentioned building a RAG chatbot. Can you explain how the retrieval component worked?",
    "Built a RAG chatbot using LangChain": "You mentioned building a RAG chatbot with LangChain. How did you structure your documents and chunks?",
    "FastAPI": "You've used FastAPI. How do you handle error handling and validation in your APIs?",
    "Docker": "You listed Docker experience. How do you structure multi-container applications?",
    "Machine Learning": "You listed Machine Learning experience. What was the most interesting ML project you've worked on?",
    "Kubernetes": "You have Kubernetes experience. How do you handle rolling updates and rollbacks?",
    "AWS": "You deployed on AWS. Which services did you use and why?",
    "PostgreSQL": "You used PostgreSQL. How do you approach query optimization and indexing?",
    "Python": "You have Python experience. What is the most complex Python application you have built?",
    "ML": "You listed ML experience. What was the most interesting ML project you've worked on?",
}


class QuestionGenerator:
    """Generates adaptive interview questions based on context."""

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider
        # Real reason the LLM path was not used (empty when it worked). Surfaced
        # on fallback payloads so a fallback is never mistaken for LLM output.
        self.last_llm_error = ""

    def _provider_error(self) -> str:
        """Last error reported by the LLM provider, for diagnostics."""
        return (getattr(self.llm_provider, "last_error", "") or "no reason reported")

    def _mark_fallback(self, question: Dict[str, Any]) -> Dict[str, Any]:
        """Tag a deterministic question with why the LLM was not used."""
        if isinstance(question, dict):
            question.setdefault("llm_generated", False)
            question.setdefault(
                "fallback_reason",
                self.last_llm_error or "llm_not_configured_or_unavailable")
        return question

    # ── Entry point: opening question ─────────────────────────────
    def get_first_question(self, state, resume_skills=None, required_skills=None,
                           job_context=None, context_str="") -> Dict[str, Any]:
        """Opening question: LLM-first (structured JSON), deterministic fallback."""
        resume_skills = self._normalize_resume_skills(resume_skills)
        required_skills = self._normalize_skill_list(required_skills)
        jd = self._skills_from_job(job_context)
        required_skills = required_skills or jd["required"]

        if self.llm_provider and context_str:
            q = self._llm_structured(context_str + "\nThis is TURN 1: ask a resume/project-grounded opener.", state)
            if q:
                return q
        if self.llm_provider:
            role = state.target_role or "this role"
            resume_str = ", ".join(s["skill"] for s in resume_skills[:10]) or "not provided"
            req_str = ", ".join(required_skills[:10]) or "not provided"
            try:
                raw = self.llm_provider.generate_json(
                    f"Role: {role}. Resume: {resume_str}. Required: {req_str}. "
                    "Return JSON: question, question_type, topic, skill, difficulty, follow_up, reason. "
                    "TURN 1 opener grounded in their resume/project. ONE question ending with '?'.",
                    system_prompt="You are a friendly technical interviewer. Output ONLY valid JSON.",
                    max_tokens=400)
                good = self._validate_llm_q(raw, state)
                if good:
                    return good
            except Exception:
                pass

        opener = random.choice(BEHAVIORAL_OPENERS)
        focus = required_skills[0] if required_skills else (resume_skills[0].get("skill", "") if resume_skills else "")
        if focus:
            opener = f"{opener} I'd also like to hear about your experience with {focus}."
        if not self.last_llm_error:
            self.last_llm_error = "llm_not_called: no context string was available for the LLM"
        logger.warning("Opening question: using deterministic opener (reason: %s)",
                       self.last_llm_error)
        return self._mark_fallback({"question": opener, "type": "behavioral",
                                    "skill": "", "source": "opener"})

    def _match_resume_followup(self, skill_name: str) -> Optional[str]:
        """Return a resume-grounded follow-up template for a skill, if known."""
        if not skill_name:
            return None
        key = skill_name.strip().lower()
        mapping = {
            "python": "You list Python on your resume — walk me through a recent Python feature or script you built and the trade-offs you made.",
            "machine learning": "Your resume mentions machine learning — describe a model you trained, how you evaluated it, and what you would improve.",
            "machine_learning": "Your resume mentions machine learning — describe a model you trained, how you evaluated it, and what you would improve.",
            "docker": "You mention Docker on your resume — how did you containerize one of your projects and what broke the first time?",
            "fastapi": "Your resume mentions FastAPI — explain how you structured one of your APIs and handled auth or validation.",
            "rag": "Your resume touches RAG — walk me through your retrieval pipeline and how you reduced hallucinations.",
            "kubernetes": "You mention Kubernetes — how did you deploy or scale a workload on it?",
            "sql": "Your resume mentions SQL — describe a complex query or optimization you did and why it was needed.",
            "aws": "You mention AWS — which services did you use on a real project and how did they fit together?",
        }
        if key in mapping:
            return mapping[key]
        # Generic resume-grounded fallback (never empty).
        return f"You mention {skill_name} on your resume — tell me about a time you used it on a real project and what the outcome was."

    def _asked_questions(self, state) -> set:
        asked = set()
        for qa in getattr(state, "questions_asked", []) or []:
            q = (qa.get("question") if isinstance(qa, dict) else qa) or ""
            if q:
                asked.add(self._norm_q(q))
        return asked

    def _norm_q(self, q: str) -> str:
        q = (q or "").strip().lower()
        q = re.sub(r"\s+", " ", q)
        return re.sub(r"[^\w\s?]", "", q)

    def _semantic_dup(self, q: str, state) -> bool:
        nq = self._norm_q(q)
        if not nq:
            return True
        words = set(nq.split())
        for prev in self._asked_questions(state):
            if nq == prev:
                return True
            pw = set(prev.split())
            if not pw:
                continue
            overlap = len(words & pw) / max(len(words | pw), 1)
            if overlap > 0.82 and abs(len(nq) - len(prev)) < 30:
                return True
        return False

    def _normalize_skill_list(self, skills) -> List[str]:
        result: List[str] = []
        if not skills:
            return result
        seen = set()
        for s in skills:
            if isinstance(s, dict):
                s = s.get("skill") or s.get("name") or ""
            if isinstance(s, str) and s.strip():
                s = s.strip()
                if s.lower() not in seen:
                    seen.add(s.lower())
                    result.append(s)
        return result

    def _normalize_resume_skills(self, resume_skills) -> List[Dict]:
        if isinstance(resume_skills, dict):
            if resume_skills.get("skills"):
                resume_skills = resume_skills["skills"]
            elif isinstance(resume_skills.get("skill_intelligence"), dict) and resume_skills["skill_intelligence"].get("skills"):
                resume_skills = resume_skills["skill_intelligence"]["skills"]
            else:
                text = resume_skills.get("text") or resume_skills.get("raw_text") or ""
                resume_skills = self._extract_skills_from_text(text)
        if not isinstance(resume_skills, list):
            return []
        result: List[Dict] = []
        for s in resume_skills:
            if isinstance(s, str):
                if s.strip():
                    result.append({"skill": s.strip(), "strength": "MEDIUM", "confidence": 0.5, "evidence": ""})
            elif isinstance(s, dict):
                name = s.get("skill") or s.get("name")
                if name and str(name).strip():
                    result.append({
                        "skill": str(name).strip(),
                        "strength": s.get("strength", "MEDIUM"),
                        "confidence": s.get("confidence", 0.5),
                        "evidence": s.get("evidence") or "",
                    })
        return result

    def _extract_skills_from_text(self, text: str) -> List[Dict]:
        text = (text or "").strip()
        if not text:
            return []
        try:
            from services.resume import extract_skills
            skills = extract_skills(text)
            if isinstance(skills, list):
                return skills
        except Exception:
            pass
        return []

    def _skills_from_job(self, job_context) -> Dict[str, List[str]]:
        required: List[str] = []
        preferred: List[str] = []
        if isinstance(job_context, dict):
            for key in ("required_skills", "skills"):
                required += self._normalize_skill_list(job_context.get(key) or [])
            preferred = self._normalize_skill_list(job_context.get("preferred_skills") or [])
            if not required and job_context.get("description"):
                try:
                    from services.matching.jd_analyzer import analyze_job_description
                    jd = analyze_job_description(job_context.get("description", ""))
                    required = self._normalize_skill_list(getattr(jd, "skills", []) or [])
                except Exception:
                    pass
        return {"required": required, "preferred": preferred}
    def _build_context_str(self, state, resume_skills, required_skills, job_context, conversation, rag_results) -> str:
        parts = [f"Target role: {state.target_role or 'Unknown'}"]
        names = [s.get("skill") for s in resume_skills if s.get("skill")]
        if names:
            parts.append(f"Candidate skills from resume: {', '.join(names[:20])}")
        if required_skills:
            parts.append(f"Required JD skills: {', '.join(required_skills[:20])}")
        if isinstance(job_context, dict) and job_context.get("description"):
            parts.append(f"Job description excerpt: {str(job_context['description'])[:300]}")
        if conversation:
            lines = [f"{m.get('role', 'unknown')}: {str(m.get('content', ''))[:200]}" for m in conversation[-4:]]
            parts.append("Recent conversation:\n" + "\n".join(lines))
        if rag_results:
            parts.append(f"Reference knowledge: {str(rag_results[0].get('content', ''))[:250]}")
        return "\n".join(parts)

    def _is_duplicate(self, question: str, state) -> bool:
        return self._semantic_dup(question, state)

    def _validate_llm_q(self, data: Any, state) -> Optional[Dict[str, Any]]:
        if not isinstance(data, dict):
            return None
        q = str(data.get("question") or data.get("next_question") or "").strip()
        if len(q) < 15 or "?" not in q:
            return None
        if self._semantic_dup(q, state):
            return None
        skill = str(data.get("skill") or state.current_skill or "").strip()
        topic = str(data.get("topic") or skill or "general").strip()
        qtype = str(data.get("question_type") or data.get("type") or "technical").strip()
        diff = str(data.get("difficulty") or state.difficulty or "MEDIUM").upper()
        if diff not in ("EASY", "MEDIUM", "HARD", "EXPERT"):
            diff = state.difficulty or "MEDIUM"
        return {"question": q[:500], "type": qtype[:30], "skill": skill[:60],
                "topic": topic[:80], "difficulty": diff,
                "follow_up": bool(data.get("follow_up", False)),
                "reason": str(data.get("reason", ""))[:300],
                "source": "llm_structured", "llm_generated": True}

    def _llm_structured(self, context_str: str, state) -> Optional[Dict[str, Any]]:
        """Ask Grok/LLM for structured adaptive question JSON. Retry once on invalid.

        Never fails silently: the exact reason the LLM path could not be used is
        stored in self.last_llm_error and logged, so the API response and the UI
        can state why a deterministic question was served instead.
        """
        self.last_llm_error = ""
        if not self.llm_provider:
            self.last_llm_error = ("no_llm_provider: QuestionGenerator was created "
                                   "without an LLM provider")
            logger.error("LLM question generation skipped: %s", self.last_llm_error)
            return None
        asked = [q.get("question", "") for q in (getattr(state, "questions_asked", []) or [])][-6:]
        prompt = (
            f"{context_str}\n\nPreviously asked (NEVER repeat or paraphrase these):\n"
            + ("\n".join("- " + str(a)[:150] for a in asked) if asked else "(none)")
            + "\n\nGenerate the next adaptive interview question as JSON with keys: "
            "question, question_type, topic, skill, difficulty, follow_up, reason. "
            "Rules: next question MUST depend on the last answer (deeper if strong, "
            "clarify if weak, re-test if incorrect, practical/system-design if excellent). "
            "Ground resume questions ONLY in stated resume facts; never invent project details. "
            "Prefer untested JD required skills unless a follow-up is justified. "
            "Ask exactly ONE question ending with '?'."
        )
        system = ("You are a sharp adaptive technical interviewer. "
                  "Output ONLY valid JSON with the required keys.")
        try:
            raw = self.llm_provider.generate_json(prompt, system_prompt=system, max_tokens=600)
        except Exception as exc:
            self.last_llm_error = "llm_exception: %s: %s" % (type(exc).__name__, exc)
            logger.error("LLM question generation raised: %s", self.last_llm_error)
            return None
        if raw is None:
            self.last_llm_error = ("llm_call_failed: %s produced no JSON (%s)"
                                   % (type(self.llm_provider).__name__,
                                      self._provider_error()))
            logger.error("LLM question generation failed: %s", self.last_llm_error)
            return None
        good = self._validate_llm_q(raw, state)
        if good:
            logger.info("LLM generated question (skill=%s, difficulty=%s)",
                        good.get("skill"), good.get("difficulty"))
            return good
        try:
            repair = self.llm_provider.generate_json(
                prompt + "\nPrevious output invalid or duplicate. Return ONLY valid non-duplicate JSON.",
                system_prompt=system, max_tokens=600)
        except Exception as exc:
            self.last_llm_error = ("llm_exception: repair call failed: %s: %s"
                                   % (type(exc).__name__, exc))
            logger.error("LLM question generation raised: %s", self.last_llm_error)
            return None
        repaired = self._validate_llm_q(repair, state)
        if repaired:
            logger.info("LLM generated question after repair (skill=%s)",
                        repaired.get("skill"))
            return repaired
        self.last_llm_error = ("llm_invalid_question: model replied but no usable "
                               "non-duplicate question JSON was returned")
        logger.error("LLM question generation failed: %s", self.last_llm_error)
        return None
    def _ensure_not_empty(self, candidate, state, resume_skills) -> Dict[str, Any]:
        if candidate and candidate.get("question") and not self._semantic_dup(candidate["question"], state):
            return candidate
        return self._mark_fallback(self._fallback_question(state, resume_skills))

    def get_next_question(self, state, resume_skills=None, required_skills=None,
                          preferred_skills=None, conversation=None, rag_results=None,
                          context_str="", evaluation=None) -> Dict[str, Any]:
        """LLM-first adaptive question; deterministic ladder only as fallback."""
        resume_skills = self._normalize_resume_skills(resume_skills)
        required_skills = self._normalize_skill_list(required_skills)
        preferred_skills = self._normalize_skill_list(preferred_skills)
        conversation = conversation or []
        rag_results = rag_results or []

        # 1) Grok/LLM structured question grounded in the FULL context
        #    (resume evidence + JD + state + recent history + RAG + last answer).
        if self.llm_provider and context_str:
            q = self._llm_structured(context_str, state)
            if q:
                return q
            logger.warning("Interview question %d: LLM unavailable, using the "
                           "deterministic ladder (reason: %s)",
                           state.turn_count + 1, self.last_llm_error)
        elif not self.llm_provider:
            self.last_llm_error = ("no_llm_provider: QuestionGenerator was created "
                                   "without an LLM provider")

        # 2) Deterministic adaptive ladder (offline-safe, never repeats).
        #    Every return below is explicitly tagged as a fallback with the reason.
        if evaluation:
            q = self._follow_up_question(state, evaluation, resume_skills, required_skills)
            if q:
                return self._mark_fallback(q)

        # 3) Resume-based claim questions.
        q = self._try_resume_claim_question(state, resume_skills)
        if q:
            return self._mark_fallback(q)

        # 4) Required JD skills not yet tested.
        q = self._try_required_skill_question(state, required_skills)
        if q:
            return self._mark_fallback(q)

        # 5) Preferred JD skills.
        q = self._try_preferred_skill_question(state, preferred_skills)
        if q:
            return self._mark_fallback(q)

        # 6) RAG knowledge probing.
        q = self._try_rag_question(state, rag_results)
        if q:
            return self._mark_fallback(q)

        # 7) Continue an unfinished topic.
        q = self._try_topic_continuation(state, resume_skills, required_skills)
        if q:
            return self._mark_fallback(q)

        # 8) Never-empty deterministic fallback.
        return self._mark_fallback(self._fallback_question(state, resume_skills))

    def _follow_up_question(self, state, evaluation, resume_skills, required_skills):
        """Answer-dependent deterministic follow-up (used when LLM is absent).

        weak/incorrect -> clarify fundamentals; strong -> deepen trade-offs;
        excellent -> practical/system-design application.
        """
        skill = state.current_skill or (required_skills[0] if required_skills
                                        else (resume_skills[0].get("skill") if resume_skills else ""))
        if not skill:
            return None
        total = evaluation.get("overall_score")
        if not isinstance(total, (int, float)):
            total = evaluation.get("total_score")
        if not isinstance(total, (int, float)):
            total = evaluation.get("score")
        if not isinstance(total, (int, float)):
            total = 50
        follow_up_needed = evaluation.get("follow_up_needed", False)

        if total < 50 or (follow_up_needed and total < 60):
            q = ("Let's back up on %s: explain the core idea in simple terms and give one small example?") % skill
            fu = "clarification"
        elif total < 70 or follow_up_needed:
            q = ("What part of %s was trickiest in practice, and how did you verify your approach worked?") % skill
            fu = "clarification"
        elif total >= 85:
            q = ("Excellent answer on %s - now apply it to a production system: what would you design "
                 "differently at scale and which trade-offs matter most?") % skill
            fu = "practical_application"
        else:
            q = ("Good - let's go deeper on %s: walk me through the trade-offs, edge cases, "
                 "and how you would optimize it.") % skill
            fu = "deeper_technical"

        if self._is_duplicate(q, state):
            return None
        source = "weak_followup" if total < 70 else "strong_followup"
        return {"question": q, "type": "technical", "skill": skill,
                "topic": skill, "source": source, "follow_up": fu,
                "follow_up_reason": str(evaluation.get("reason", ""))[:200]}
    def generate_question(self, state, resume_skills: List[Dict],
                          required_skills: List[str], preferred_skills: List[str],
                          rag_results: List[Dict], conversation: List[Dict],
                          context_str: str = "") -> Dict[str, Any]:
        """Backward-compatible alias for get_next_question."""
        return self.get_next_question(state, resume_skills, required_skills,
                                      preferred_skills, conversation, rag_results,
                                      context_str=context_str)

    def _try_resume_claim_question(self, state, resume_skills) -> Optional[Dict[str, Any]]:
        if not resume_skills:
            return None
        for skill in resume_skills:
            skill_name = skill.get("skill", "")
            if not skill_name:
                continue
            if skill_name.lower() in [s.lower() for s in state.skills_covered]:
                continue
            followup = self._match_resume_followup(skill_name)
            if followup and not self._semantic_dup(followup, state):
                return {"question": followup, "type": "resume", "skill": skill_name, "source": "resume_claim"}
            templates = self._get_templates_for_skill(skill_name)
            if templates:
                for template in templates:
                    if not self._semantic_dup(template, state):
                        return {"question": template, "type": "resume",
                                "skill": skill_name, "source": "resume_claim"}
        return None

    def _get_templates_for_skill(self, skill: str) -> List[str]:
        """Get question templates for a skill, trying various normalizations."""
        skill_lower = skill.lower()
        if skill_lower in QUESTION_TEMPLATES["technical"]:
            return QUESTION_TEMPLATES["technical"][skill_lower]
        for key in QUESTION_TEMPLATES["technical"]:
            if key in skill_lower or skill_lower in key:
                return QUESTION_TEMPLATES["technical"][key]
        return []

    def _try_required_skill_question(self, state, required_skills) -> Optional[Dict[str, Any]]:
        if not required_skills:
            return None
        untested = [s for s in required_skills if s not in state.required_skills_tested]
        for skill in untested:
            templates = self._get_templates_for_skill(skill)
            if templates:
                for template in templates:
                    if not self._semantic_dup(template, state):
                        state.mark_required_skill_tested(skill)
                        return {"question": template, "type": "technical",
                                "skill": skill, "source": "required_jd"}
            fallback = f"Can you tell me about your experience with {skill}?"
            if not self._semantic_dup(fallback, state):
                state.mark_required_skill_tested(skill)
                return {"question": fallback, "type": "technical", "skill": skill, "source": "required_jd"}
        return None

    def _try_preferred_skill_question(self, state, preferred_skills) -> Optional[Dict[str, Any]]:
        if not preferred_skills:
            return None
        untested = [s for s in preferred_skills if s not in state.preferred_skills_tested]
        for skill in untested:
            templates = self._get_templates_for_skill(skill)
            if templates:
                for template in templates:
                    if not self._semantic_dup(template, state):
                        state.mark_preferred_skill_tested(skill)
                        return {"question": template, "type": "technical",
                                "skill": skill, "source": "preferred_jd"}
            fallback = f"Have you worked with {skill} before?"
            if not self._semantic_dup(fallback, state):
                state.mark_preferred_skill_tested(skill)
                return {"question": fallback, "type": "technical", "skill": skill, "source": "preferred_jd"}
        return None

    def _try_rag_question(self, state, rag_results) -> Optional[Dict[str, Any]]:
        if not rag_results:
            return None
        for chunk in rag_results[:3]:
            content = chunk.get("content", "")
            question = self._derive_question_from_rag(content)
            if question and not self._semantic_dup(question, state):
                return {"question": question, "type": "technical",
                        "skill": state.current_skill or "general", "source": "rag"}
        return None

    def _derive_question_from_rag(self, content: str) -> Optional[str]:
        """Derive a question from RAG chunk content."""
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("### ") or stripped.startswith("## "):
                concept = re.sub(r"^#+\s*", "", stripped).strip()
                if concept and len(concept) > 5:
                    return f"Tell me about {concept}"
        for line in lines:
            if len(line.strip()) > 50:
                return f"Based on your background, how would you apply {line[:50].strip()}?"
        return None

    def _try_topic_continuation(self, state, resume_skills: List[Dict], required_skills: List[str]) -> Optional[Dict[str, Any]]:
        """Try to continue an existing topic with a follow-up."""
        all_skills = required_skills + [s.get("skill", "") for s in resume_skills if s.get("strength") == "STRONG"]
        for skill in all_skills:
            if not skill or skill in state.skills_covered or skill in state.skills_not_tested:
                continue
            templates = self._get_templates_for_skill(skill)
            if templates:
                for template in templates:
                    if not self._semantic_dup(template, state):
                        state.mark_skill_tested(skill)
                        return {"question": template, "type": "technical", "skill": skill, "source": "topic_continuation"}
        return None

    def _fallback_question(self, state, resume_skills: List[Dict]) -> Dict[str, Any]:
        """Deterministic, never-empty fallback that also avoids duplicates."""
        pool = QUESTION_TEMPLATES.get("behavioral", {}).get("general", [])[:]
        pool += QUESTION_TEMPLATES.get("problem_solving", {}).get("general", [])[:]
        asked = self._asked_questions(state)
        for q in pool:
            if q.strip().lower() not in asked:
                return {"question": q, "type": "behavioral", "skill": "general", "source": "fallback"}
        skill = resume_skills[-1].get("skill", "a recent project") if resume_skills else "a recent project"
        base = f"Let's discuss {skill} in more detail."
        if base.strip().lower() in asked:
            base = f"Continuing our interview: could you share another example involving {skill}?"
        return {"question": base, "type": "behavioral", "skill": skill if skill != "a recent project" else "general", "source": "fallback"}
