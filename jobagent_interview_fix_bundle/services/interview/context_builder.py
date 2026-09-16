"""Compact, grounded context builder for the interview LLM."""
from typing import Any, Dict, List


class InterviewContextBuilder:
    MAX_RECENT_TURNS = 8

    def __init__(self, rag_pipeline=None):
        self.rag_pipeline = rag_pipeline

    def build_context(self, resume_context: Dict[str, Any], job_context: Dict[str, Any],
                      conversation: List[Dict[str, Any]], state: Dict[str, Any],
                      current_query: str = "") -> Dict[str, Any]:
        parts = [self._resume(resume_context), self._job(job_context), self._state(state),
                 self._conversation(conversation)]
        rag_results = []
        if current_query and self.rag_pipeline:
            try:
                rag_results = self.rag_pipeline.retrieve(current_query, top_k=4, similarity_threshold=0.30)
            except Exception:
                rag_results = []
        if rag_results:
            parts.append(self._rag(rag_results))
        return {"context": "\n\n".join(parts), "rag_used": bool(rag_results), "rag_chunks": len(rag_results), "rag_results": rag_results}

    def _resume(self, r):
        if not r: return "=== RESUME ===\nNo resume supplied."
        lines = ["=== RESUME (USE ONLY THESE FACTS) ==="]
        if r.get("raw_text"): lines.append(r["raw_text"][:5000])
        if r.get("text"): lines.append(r["text"][:5000])
        skills = r.get("skill_intelligence", {}).get("skills", [])
        if skills: lines.append("Detected skills: " + ", ".join(x.get("skill", "") for x in skills[:30]))
        return "\n".join(lines)

    def _job(self, j):
        if not j: return "=== TARGET JOB ===\nNo job description supplied."
        return "=== TARGET JOB (USE ONLY THESE REQUIREMENTS) ===\n" + str(j)[:6000]

    def _state(self, s):
        return "=== STATE ===\n" + "\n".join([
            f"Role: {s.get('target_role','')}", f"Level: {s.get('experience_level','')}",
            f"Difficulty: {s.get('difficulty','MEDIUM')}", f"Turn: {s.get('turn_count',0)}",
            f"Required skills not tested: {', '.join(s.get('required_skills_not_tested',[])[:15])}",
        ])

    def _conversation(self, c):
        recent = c[-self.MAX_RECENT_TURNS:]
        if not recent: return "=== CONVERSATION ===\nNone."
        return "=== RECENT CONVERSATION ===\n" + "\n".join(f"{m.get('role','').upper()}: {m.get('content','')[:1200]}" for m in recent)

    def _rag(self, results):
        lines = ["=== RAG SOURCES (GROUNDING ONLY) ==="]
        for i, r in enumerate(results[:4], 1):
            meta = r.get("metadata", {})
            lines.append(f"[{i}] {meta.get('document_id','unknown')} score={r.get('score',0):.2f}: {r.get('content','')[:1200]}")
        return "\n".join(lines)
