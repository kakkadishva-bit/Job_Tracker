"""Reliable interview session state."""
from datetime import datetime
from typing import Any, Dict, List, Optional

INTERVIEW_MODES = {
    "quick": {"min_questions": 5, "max_questions": 10},
    "standard": {"min_questions": 10, "max_questions": 20},
    "deep": {"min_questions": 20, "max_questions": 35},
    "custom": {"min_questions": 1, "max_questions": 50},
}
DIFFICULTY_LEVELS = ["EASY", "MEDIUM", "HARD"]


class InterviewState:
    """State machine for one interview. No LLM memory is required."""
    def __init__(self, session_id: str, user_id: Any = "", target_role: str = "",
                 experience_level: str = "unknown", interview_mode: str = "standard",
                 required_skills: Optional[List[str]] = None,
                 preferred_skills: Optional[List[str]] = None, job_id: str = "", **kwargs):
        # Backward compatibility with the broken app call InterviewState(id, config).
        if isinstance(user_id, dict):
            cfg = user_id
            user_id = cfg.get("user_id", "")
            target_role = cfg.get("target_role", target_role)
            experience_level = cfg.get("experience_level", experience_level)
            interview_mode = cfg.get("interview_mode", interview_mode)
            job_id = cfg.get("job_id", job_id)
            required_skills = cfg.get("required_skills", required_skills)
            preferred_skills = cfg.get("preferred_skills", preferred_skills)
        self.session_id = session_id
        self.user_id = user_id
        self.target_role = target_role
        self.experience_level = experience_level
        self.interview_mode = interview_mode if interview_mode in INTERVIEW_MODES else "standard"
        self.job_id = job_id or ""
        self.started_at = datetime.utcnow().isoformat()
        self.ended_at: Optional[str] = None
        self.questions_asked: List[Dict[str, Any]] = []
        self.answers: List[Dict[str, Any]] = []
        self.topics_covered: List[str] = []
        self.skills_covered: List[str] = []
        self.required_skills = list(required_skills or [])
        self.preferred_skills = list(preferred_skills or [])
        self.required_skills_tested: List[str] = []
        self.preferred_skills_tested: List[str] = []
        self.resume_claims_tested: List[str] = []
        self.answer_scores: List[float] = []
        self.follow_up_count = 0
        self.consecutive_weak_answers = 0
        self.current_topic: Optional[str] = None
        self.current_skill: Optional[str] = None
        self.current_question: Optional[Dict[str, Any]] = None
        self.difficulty = "MEDIUM"
        self.turn_count = 0
        self.status = "active"
        self.resume_used = False
        self.jd_used = False
        self.rag_used = False
        self.evaluations: List[Dict[str, Any]] = []
        self.strong_areas: List[str] = []
        self.weak_areas: List[str] = []

    @property
    def overall_score(self) -> int:
        if not self.answer_scores:
            return 0
        return round(sum(self.answer_scores) / len(self.answer_scores))

    @property
    def skills_not_tested(self) -> List[str]:
        return [s for s in self.required_skills if s.lower() not in {x.lower() for x in self.required_skills_tested}]

    def mark_skill_tested(self, skill: str):
        if skill and skill.lower() not in {s.lower() for s in self.skills_covered}:
            self.skills_covered.append(skill)

    def mark_required_skill_tested(self, skill: str):
        if skill and skill.lower() not in {s.lower() for s in self.required_skills_tested}:
            self.required_skills_tested.append(skill)
            self.mark_skill_tested(skill)

    def mark_preferred_skill_tested(self, skill: str):
        if skill and skill.lower() not in {s.lower() for s in self.preferred_skills_tested}:
            self.preferred_skills_tested.append(skill)
            self.mark_skill_tested(skill)

    def record_question(self, question: str, question_type: str = "technical", skill: str = "", source: str = ""):
        item = {"question": question, "type": question_type, "skill": skill, "source": source,
                "difficulty": self.difficulty, "timestamp": datetime.utcnow().isoformat()}
        self.questions_asked.append(item)
        self.current_question = item
        self.current_topic = question_type
        self.current_skill = skill or None
        if skill:
            self.mark_skill_tested(skill)
        return item

    def record_answer(self, answer: str, evaluation: Dict[str, Any]):
        score = float(evaluation.get("overall_score", 0) or 0)
        self.answers.append({"answer": answer, "evaluation": evaluation, "timestamp": datetime.utcnow().isoformat()})
        self.evaluations.append(evaluation)
        self.answer_scores.append(score)
        self.turn_count += 1
        if score < 55:
            self.consecutive_weak_answers += 1
        else:
            self.consecutive_weak_answers = 0
        if self.current_question and self.current_question.get("skill"):
            skill = self.current_question["skill"]
            self.mark_skill_tested(skill)
            if self.current_question.get("source") == "required_jd":
                self.mark_required_skill_tested(skill)
            elif self.current_question.get("source") == "preferred_jd":
                self.mark_preferred_skill_tested(skill)
            elif self.current_question.get("source") == "resume_claim":
                if skill not in self.resume_claims_tested:
                    self.resume_claims_tested.append(skill)
        if score < 45 and self.difficulty != "EASY":
            self.difficulty = DIFFICULTY_LEVELS[max(0, DIFFICULTY_LEVELS.index(self.difficulty) - 1)]
        elif score >= 80 and self.difficulty != "HARD":
            self.difficulty = DIFFICULTY_LEVELS[min(2, DIFFICULTY_LEVELS.index(self.difficulty) + 1)]

    def should_follow_up(self, evaluation: Dict[str, Any]) -> bool:
        return bool(evaluation.get("follow_up_needed")) and self.follow_up_count < 2

    def mark_follow_up(self):
        self.follow_up_count += 1

    def should_continue(self) -> bool:
        limits = INTERVIEW_MODES[self.interview_mode]
        count = len(self.questions_asked)
        return self.status == "active" and count < limits["max_questions"]

    def finalize(self):
        self.status = "completed"
        self.ended_at = datetime.utcnow().isoformat()
        self.strong_areas = []
        self.weak_areas = []
        for ev in self.evaluations:
            self.strong_areas.extend(ev.get("strengths", [])[:2])
            self.weak_areas.extend(ev.get("weaknesses", [])[:2])
        self.strong_areas = list(dict.fromkeys(self.strong_areas))[:8]
        self.weak_areas = list(dict.fromkeys(self.weak_areas))[:8]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id, "user_id": self.user_id, "target_role": self.target_role,
            "experience_level": self.experience_level, "interview_mode": self.interview_mode,
            "job_id": self.job_id, "started_at": self.started_at, "ended_at": self.ended_at,
            "questions_asked": len(self.questions_asked), "turn_count": self.turn_count,
            "difficulty": self.difficulty, "current_topic": self.current_topic,
            "current_skill": self.current_skill, "status": self.status,
            "skills_covered": list(self.skills_covered), "required_skills_tested": list(self.required_skills_tested),
            "required_skills_not_tested": self.skills_not_tested,
            "resume_claims_tested": list(self.resume_claims_tested),
            "answer_scores": list(self.answer_scores), "follow_up_count": self.follow_up_count,
            "overall_score": self.overall_score, "resume_used": self.resume_used,
            "jd_used": self.jd_used, "rag_used": self.rag_used,
        }
