"""services/interview/context_builder.py - Compact grounded interview context."""
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class InterviewContextBuilder:
    """Builds compact LLM context: resume evidence + JD + state + history + RAG."""

    MAX_RECENT_TURNS = 6
    MAX_HISTORY_CHARS = 350

    def __init__(self, rag_pipeline=None):
        self.rag_pipeline = rag_pipeline

    def build_context(self, resume_context: Dict, job_context: Dict,
                      conversation: List[Dict], current_state: Dict,
                      current_query: str = "", evaluations: List[Dict] = None,
                      rag_results: List[Dict] = None) -> Dict[str, Any]:
        sections = []
        sections.append(self._build_resume_section(resume_context))
        if job_context and job_context.get("analyzed"):
            sections.append(self._build_job_section(job_context))
        sections.append(self._build_state_section(current_state))
        sections.append(self._build_conversation_section(conversation))
        if evaluations:
            sections.append(self._build_eval_section(evaluations))

        rag_used = False
        rag_chunks = 0
        results = list(rag_results or [])
        if current_query and not results and self.rag_pipeline:
            try:
                results = self.rag_pipeline.retrieve(current_query, top_k=3) or []
            except Exception:
                results = []
        if results:
            sections.append(self._build_rag_section(results))
            rag_used = True
            rag_chunks = len(results)

        return {"context": "\n\n".join(sections), "rag_used": rag_used,
                "rag_chunks": rag_chunks, "rag_results": results}

    def _build_resume_section(self, resume: Dict) -> str:
        if not resume:
            return "=== RESUME FACTS (grounded, never invent) ===\n(None)\n"
        lines = ["=== RESUME FACTS (grounded, never invent) ==="]
        if isinstance(resume, dict) and resume.get("text"):
            lines.append("Resume excerpt: " + str(resume["text"])[:700])
        skills = []
        if isinstance(resume, dict):
            si = resume.get("skill_intelligence") or {}
            skills = si.get("skills", []) or resume.get("skills", []) or []
        if skills:
            lines.append("Skills w/ evidence:")
            for s in skills[:12]:
                if isinstance(s, dict):
                    ev = ""
                    try:
                        evs = s.get("evidence") or []
                        if evs:
                            ev = " | e.g. " + str(evs[0])[:120]
                    except Exception:
                        ev = ""
                    lines.append("  - %s (%s)%s" % (s.get("skill"), s.get("strength", "?"), ev))
                else:
                    lines.append("  - %s" % s)
        for key in ("experience", "projects", "claims", "evidence"):
            vals = resume.get(key, []) if isinstance(resume, dict) else []
            if vals:
                lines.append(key.capitalize() + ":")
                for v in vals[:4]:
                    lines.append("  - " + str(v if isinstance(v, str) else v.get("description", v.get("name", v)))[:220])
        if isinstance(resume, dict) and resume.get("claims_tested") is not None:
            pass
        lines.append("")
        return "\n".join(lines)

    def _build_job_section(self, job: Dict) -> str:
        lines = ["=== TARGET JD REQUIREMENTS ==="]
        if not job:
            lines.append("(None)")
            return "\n".join(lines)
        lines.append(f"Job Title: {job.get('title', 'N/A')}")
        req = job.get("required_skills", []) or []
        pref = job.get("preferred_skills", []) or []
        if req:
            lines.append(f"Required Skills: {', '.join(req[:15])}")
        if pref:
            lines.append(f"Preferred Skills: {', '.join(pref[:10])}")
        desc = job.get("description", "") or job.get("text", "")
        if desc:
            lines.append(f"Description: {str(desc)[:500]}")
        lines.append("")
        return "\n".join(lines)

    def _build_state_section(self, state: Dict) -> str:
        lines = ["=== INTERVIEW STATE (deterministic tracker) ==="]
        lines.append(f"Topic: {state.get('current_topic', 'N/A')} | Skill: {state.get('current_skill', 'N/A')}")
        lines.append(f"Difficulty: {state.get('difficulty', 'MEDIUM')} | Turn: {state.get('turn_count', 0)}")
        for k in ("skills_covered", "skills_remaining", "required_skills_not_tested",
                  "resume_claims_tested", "strong_areas", "weak_areas", "previous_questions"):
            v = state.get(k, [])
            if v:
                lines.append(f"{k}: {', '.join([str(x)[:60] for x in v][-8:])}")
        if state.get("previous_evaluations"):
            lines.append("Prev scores: " + ", ".join([str(e.get("score", "?")) for e in state["previous_evaluations"][-4:]]))
        lines.append("")
        return "\n".join(lines)

    def _build_conversation_section(self, conversation: List[Dict]) -> str:
        if not conversation:
            return "=== RECENT CONVERSATION ===\n(None - interview just started)\n"
        lines = ["=== RECENT CONVERSATION (compressed) ==="]
        # Older turns compressed to one line each; last 2 kept fuller.
        older = conversation[:-4] if len(conversation) > 4 else []
        if older:
            lines.append("Earlier: " + " | ".join(
                ["%s: %s" % (m.get("role", "?"), str(m.get("content", ""))[:80]) for m in older[-4:]]))
        for msg in conversation[-4:]:
            lines.append("%s: %s" % (str(msg.get("role", "?")).upper(), str(msg.get("content", ""))[:self.MAX_HISTORY_CHARS]))
        lines.append("")
        return "\n".join(lines)

    def _build_eval_section(self, evals: List[Dict]) -> str:
        lines = ["=== PREVIOUS EVALUATIONS ==="]
        for e in evals[-3:]:
            lines.append("score=%s strengths=%s weak=%s reason=%s" % (
                e.get("score", e.get("overall_score", "?")),
                str(e.get("strengths", []))[:120], str(e.get("weaknesses", []))[:120],
                str(e.get("reason", e.get("reasoning", "")))[:160]))
        lines.append("")
        return "\n".join(lines)

    def _build_rag_section(self, rag_results: List[Dict]) -> str:
        lines = ["=== RAG FACTS (reference only, not candidate facts) ==="]
        for i, chunk in enumerate(rag_results[:3]):
            content = str(chunk.get("content", ""))[:350]
            lines.append(f"[Fact {i+1}] {content}")
        lines.append("")
        return "\n".join(lines)
