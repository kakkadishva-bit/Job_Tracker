"""Adaptive question generation: local LLM first, deterministic fallback second."""
import json, re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

BASIC_BY_SKILL = {
    "python": "Explain one Python feature you have actually used in a project and why you used it.",
    "machine learning": "Choose one ML project from your background. How did you evaluate the model and what did you learn?",
    "rag": "Explain the RAG system you built: document ingestion, chunking, retrieval, and generation.",
    "fastapi": "Describe how you used FastAPI in a real project, including validation and error handling.",
    "docker": "Explain how you containerized one of your applications and what problem Docker solved.",
    "sql": "Describe a SQL query or database problem you worked on and how you solved it.",
    "aws": "Describe what you deployed on AWS and why you selected the services you used.",
    "kubernetes": "Explain a Kubernetes concept you have actually used and where it fit in your project.",
}

class QuestionGenerator:
    def __init__(self, llm_provider=None): self.llm_provider = llm_provider

    def _llm_json(self, prompt: str) -> Optional[Dict[str, Any]]:
        if not self.llm_provider: return None
        try:
            return self.llm_provider.generate_json(prompt, system_prompt=(
                "You are a rigorous technical interviewer. Ask exactly one interview question. "
                "Use ONLY facts in the supplied resume and ONLY requirements in the supplied JD. "
                "Do not invent candidate experience, company facts, or requirements. "
                "If the resume has no evidence, ask a neutral knowledge/experience question. "
                "Return JSON: {question,type,skill,source,reason}."
            ), max_tokens=300)
        except Exception:
            return None

    def first_question(self, state, resume_context, job_context, rag_context=""):
        prompt = f"""Create the first realistic interview question. Role: {state.target_role}. Level: {state.experience_level}. Resume: {str(resume_context)[:4500]}. JD: {str(job_context)[:4500]}."""
        q = self._llm_json(prompt)
        return self._clean(q, "resume", "") if q else self._fallback_first(state, resume_context, job_context)

    def next_question(self, state, resume_context, job_context, conversation, evaluation, rag_context=""):
        # Follow-up is always grounded in the previous answer.
        if state.should_follow_up(evaluation):
            state.mark_follow_up()
            prompt = f"""Ask ONE targeted follow-up to the candidate's previous answer. Previous question: {state.current_question or {}}. Candidate answer: {conversation[-1].get('content','') if conversation else ''}. Evaluation: {evaluation}. Context: {rag_context[:5000]}. Do not change topic unless the answer is impossible to clarify."""
            q = self._llm_json(prompt)
            if q: return self._clean(q, "follow_up", state.current_skill or "")
            return self._fallback_followup(state, evaluation)

        # Prefer an explicitly required JD skill not yet tested.
        for skill in state.required_skills:
            if skill.lower() not in {s.lower() for s in state.required_skills_tested}:
                q = self._llm_json(self._skill_prompt(skill, state, resume_context, job_context, rag_context))
                return self._clean(q, "technical", skill, "required_jd") if q else self._fallback_skill(skill, "required_jd")

        # Then resume evidence that has not been tested.
        skills = resume_context.get("skill_intelligence", {}).get("skills", []) if isinstance(resume_context, dict) else []
        for item in skills[:20]:
            skill = item.get("skill", "")
            if skill and skill.lower() not in {s.lower() for s in state.resume_claims_tested}:
                q = self._llm_json(self._skill_prompt(skill, state, resume_context, job_context, rag_context))
                return self._clean(q, "resume", skill, "resume_claim") if q else self._fallback_skill(skill, "resume_claim")

        prompt = f"Ask the next interview question for {state.target_role} at {state.difficulty} difficulty. Context: {rag_context[:5000]}. Conversation: {conversation[-6:]}. Avoid all previous questions."
        q = self._llm_json(prompt)
        if q: return self._clean(q, "technical", state.current_skill or "general")
        return self._fallback_general(state)

    def _skill_prompt(self, skill, state, resume, job, rag):
        return f"Ask one {state.difficulty} interview question about {skill}. Resume evidence: {str(resume)[:3500]}. JD: {str(job)[:3500]}. RAG: {rag[:3500]}"

    def _clean(self, q, typ, skill="", source=""):
        if not q or not isinstance(q, dict): return None
        text = str(q.get("question", "")).strip()
        if not text or len(text) < 10: return None
        return {"question": text, "type": q.get("type") or typ, "skill": q.get("skill") or skill,
                "source": q.get("source") or source or "llm", "reason": q.get("reason", "")}

    def _fallback_first(self, state, resume, job):
        projects = resume.get("projects", []) if isinstance(resume, dict) else []
        if projects:
            p = projects[0]
            return {"question": f"Please walk me through your project '{p.get('name','your project')}', including the problem, your contribution, and the technical decisions you made.", "type":"project", "skill":"", "source":"resume_claim"}
        return {"question": f"Please introduce yourself and explain why your background is a good fit for the {state.target_role} role.", "type":"introduction", "skill":"", "source":"role"}

    def _fallback_followup(self, state, evaluation):
        skill = state.current_skill or "that topic"
        if evaluation.get("correctness", 100) < 50:
            text = f"Let's clarify that. What is the key idea behind {skill}, and can you give a simple example?"
        else:
            text = f"Good. Now go one level deeper: what trade-off or failure case would you consider when working with {skill}?"
        return {"question": text, "type":"follow_up", "skill":skill, "source":"adaptive_fallback"}

    def _fallback_skill(self, skill, source):
        key = skill.lower()
        text = next((v for k,v in BASIC_BY_SKILL.items() if k in key), f"Tell me about your experience with {skill} and describe one concrete example of using it.")
        return {"question":text, "type":"technical", "skill":skill, "source":source}

    def _fallback_general(self, state):
        return {"question":f"For the {state.target_role} role, describe a difficult technical problem you solved and how you approached it.", "type":"problem_solving", "skill":"", "source":"fallback"}

    @staticmethod
    def is_duplicate(question: str, previous: List[Dict[str, Any]], threshold=0.82):
        q = re.sub(r"\W+", " ", question.lower()).strip()
        return any(SequenceMatcher(None, q, re.sub(r"\W+", " ", str(x.get('question','')).lower()).strip()).ratio() >= threshold for x in previous)
