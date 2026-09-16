"""
services/interview/state.py
Manages interview session state for adaptive question flow.
"""
import logging
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

DIFFICULTY_LEVELS = ["EASY", "MEDIUM", "HARD", "EXPERT"]

INTERVIEW_MODES = {
    "quick": {"min_questions": 5, "max_questions": 10},
    "standard": {"min_questions": 15, "max_questions": 25},
    "deep": {"min_questions": 30, "max_questions": 50},
    "custom": {"min_questions": 1, "max_questions": 50},
}


class InterviewState:
    """Tracks all interview state and controls question flow decisions."""

    def __init__(self, session_id: str, user_id: str = "", target_role: str = "",
                 experience_level: str = "unknown", interview_mode: str = "standard",
                 required_skills: List[str] = None, preferred_skills: List[str] = None,
                 job_id: str = None, config: Dict[str, Any] = None):
        # Back-compat: legacy app.py call was InterviewState(session_id, config_dict).
        if isinstance(user_id, dict) and not target_role and config is None:
            config = user_id
            user_id = ""
        cfg = config or {}
        if required_skills is None:
            required_skills = list(cfg.get("required_skills") or [])
        if preferred_skills is None:
            preferred_skills = list(cfg.get("preferred_skills") or [])
        self.session_id = session_id
        self.user_id = user_id or cfg.get("user_id", "")
        self.target_role = target_role or cfg.get("target_role", "")
        self.experience_level = (experience_level if experience_level != "unknown"
                                 else cfg.get("experience_level", "unknown"))
        self.interview_mode = (interview_mode if interview_mode != "standard"
                               else cfg.get("interview_mode", "standard"))
        self.company = cfg.get("company", "")
        self.job_id = job_id or cfg.get("job_id", "") or ""

        self.started_at = datetime.utcnow().isoformat()
        self.ended_at: Optional[str] = None

        self.questions_asked: List[Dict[str, Any]] = []
        self.topics_covered: List[str] = []
        self.skills_covered: List[str] = []
        self.skills_not_tested: List[str] = []

        self.required_skills_tested: List[str] = []
        self.required_skills_not_tested: List[str] = list(required_skills or [])
        self.preferred_skills_tested: List[str] = []
        self.preferred_skills_not_tested: List[str] = list(preferred_skills or [])

        self.resume_claims_tested: List[str] = []
        self.resume_claims_not_tested: List[str] = []

        self.answer_scores: List[float] = []
        self.follow_up_count = 0
        self.follow_up_chain = 0  # consecutive follow-ups on the current skill
        self.last_answer = ""  # most recent candidate answer (verbatim)
        self.consecutive_weak_answers = 0
        self.previous_evaluations: List[Dict[str, Any]] = []
        self.previous_questions: List[str] = []
        self.skills_remaining: List[str] = list(required_skills or [])

        self.current_topic: Optional[str] = None
        self.current_skill: Optional[str] = None
        self.difficulty = "MEDIUM"
        self.turn_count = 0
        self.status = "active"

        # Flags used by the API layer / final report.
        self.resume_used = False
        self.jd_used = False
        self.rag_used = False
        self.weak_areas: List[str] = []
        self.strong_areas: List[str] = []

    def mark_skill_tested(self, skill: str):
        if skill and skill not in self.skills_covered:
            self.skills_covered.append(skill)
        self._remove_matching(self.skills_remaining, skill)

    def mark_required_skill_tested(self, skill: str):
        if skill and skill not in self.required_skills_tested:
            self.required_skills_tested.append(skill)
        self._remove_matching(self.required_skills_not_tested, skill)

    def mark_preferred_skill_tested(self, skill: str):
        if skill and skill not in self.preferred_skills_tested:
            self.preferred_skills_tested.append(skill)
        self._remove_matching(self.preferred_skills_not_tested, skill)

    @staticmethod
    def _canon(skill) -> str:
        """Deterministic canonical key for skill comparison (case/space tolerant)."""
        return re.sub(r"[^a-z0-9+#.]", "", str(skill or "").lower())

    @classmethod
    def _remove_matching(cls, lst: List[str], skill: str) -> bool:
        """Remove the first case/format-insensitive match of skill from lst."""
        key = cls._canon(skill)
        if not key:
            return False
        for i, existing in enumerate(list(lst)):
            if cls._canon(existing) == key:
                lst.pop(i)
                return True
        return False

    def is_skill_tested(self, skill: str) -> bool:
        key = self._canon(skill)
        return any(self._canon(s) == key for s in self.skills_covered)

    def next_untested_required_skill(self) -> Optional[str]:
        """Deterministic: the next JD required skill not yet covered."""
        for s in self.required_skills_not_tested:
            if not self.is_skill_tested(s):
                return s
        return None

    def add_answer_score(self, score: int):
        self.answer_scores.append(score)
        if score < 60:
            self.consecutive_weak_answers += 1
        else:
            self.consecutive_weak_answers = 0
        if len(self.answer_scores) >= 3:
            recent_avg = sum(self.answer_scores[-3:]) / 3
            if recent_avg < 40 and self.consecutive_weak_answers >= 2:
                self._adjust_difficulty("down")
            elif recent_avg > 75 and self.consecutive_weak_answers == 0:
                self._adjust_difficulty("up")

    def _adjust_difficulty(self, direction: str):
        idx = DIFFICULTY_LEVELS.index(self.difficulty)
        if direction == "up" and idx < len(DIFFICULTY_LEVELS) - 1:
            self.difficulty = DIFFICULTY_LEVELS[idx + 1]
        elif direction == "down" and idx > 0:
            self.difficulty = DIFFICULTY_LEVELS[idx - 1]

    @property
    def overall_score(self) -> int:
        return self._compute_overall_score()

    def _compute_overall_score(self) -> int:
        if not self.answer_scores:
            return 0
        avg = sum(self.answer_scores) / len(self.answer_scores)
        if len(self.answer_scores) >= 2:
            recent_avg = sum(self.answer_scores[-2:]) / 2
            return int(avg * 0.6 + recent_avg * 0.4)
        return int(avg)
    def record_answer(self, answer, evaluation: Optional[Dict[str, Any]] = None) -> None:
        """Record the candidate's answer text plus its evaluation.

        Back-compat: the legacy single-argument form record_answer(evaluation)
        is still accepted (the answer text then defaults to '')."""
        if isinstance(answer, dict) and evaluation is None:
            evaluation = answer
            answer = ""
        self.last_answer = str(answer or "")
        if not isinstance(evaluation, dict):
            return
        total = evaluation.get("overall_score")
        if total is None:
            total = evaluation.get("score", 0)
        if total is None or not isinstance(total, (int, float)):
            weights = {
                "correctness": 0.25, "relevance": 0.10, "depth": 0.20,
                "clarity": 0.15, "practical_understanding": 0.15, "problem_solving": 0.15,
            }
            try:
                total = sum(float(evaluation.get(k, 0)) * w for k, w in weights.items())
            except Exception:
                total = 0
        try:
            total = int(max(0, min(100, total or 0)))
        except Exception:
            total = 0
        self.add_answer_score(total)
        snap = {
            "score": total,
            "overall_score": total,
            "strengths": list(evaluation.get("strengths") or []),
            "weaknesses": list(evaluation.get("weaknesses") or []),
            "reason": str(evaluation.get("reason", evaluation.get("reasoning", "")))[:300],
            "skill": self.current_skill or "",
            "question": (self.current_question.get("question", "") if self.current_question else "")[:300],
            "answer_excerpt": self.last_answer[:300],            "topic": self.current_topic or "",
        }
        self.previous_evaluations.append(snap)

        for item in evaluation.get("strengths") or []:
            if item and item not in self.strong_areas:
                self.strong_areas.append(str(item))
        for item in evaluation.get("weaknesses") or []:
            if item and item not in self.weak_areas:
                self.weak_areas.append(str(item))
        # Track skill-level strength/weakness for adaptivity.
        if self.current_skill:
            if total >= 70 and self.current_skill not in self.strong_areas:
                pass  # skill-level signal kept via scores; avoid polluting area lists
            if total < 55 and self.current_skill not in self.weak_areas:
                self.weak_areas.append(self.current_skill)

    def record_question(self, question: str, qtype: str = "technical", skill: str = "",
                        source: str = "", topic: str = "", difficulty: str = "",
                        follow_up: bool = False) -> None:
        """Record an asked question, update coverage tracking."""
        if not question:
            return
        self.questions_asked.append({
            "question": question, "type": qtype or "technical", "skill": skill or "",
            "topic": topic or "", "difficulty": difficulty or self.difficulty,
            "source": str(source or ""), "follow_up": bool(follow_up),
        })
        if skill and skill != self.current_skill:
            self.follow_up_chain = 0  # new skill: the follow-up budget resets
        self.turn_count += 1
        if question and question not in self.previous_questions:
            self.previous_questions.append(question)
        if topic:
            self.current_topic = topic
            if topic not in self.topics_covered:
                self.topics_covered.append(topic)
        if difficulty and difficulty in DIFFICULTY_LEVELS:
            self.difficulty = difficulty
        if skill:
            self.current_skill = skill
            self.mark_skill_tested(skill)
            # Resume-claim tracking: any resume skill asked about counts as tested.
            if skill not in self.resume_claims_tested:
                self.resume_claims_tested.append(skill)
            self.mark_required_skill_tested(skill)
            self.mark_preferred_skill_tested(skill)

    def should_continue(self) -> bool:
        """Whether the interview should keep accepting answers."""
        if self.status != "active":
            return False
        mode = INTERVIEW_MODES.get(self.interview_mode, INTERVIEW_MODES["standard"])
        max_q = mode.get("max_questions", 25)
        return len(self.questions_asked) < max_q

    @property
    def current_question(self) -> Optional[Dict[str, Any]]:
        """The question currently awaiting an answer (the last one asked)."""
        return self.questions_asked[-1] if self.questions_asked else None

    def should_follow_up(self, last_evaluation: Dict[str, Any] = None) -> bool:
        """True when the last answer deserves ONE probing follow-up before the
        interview moves on: weak/mixed score, follow-up budget not exhausted,
        and question quota not reached. Mirrors a real interviewer probing a
        shaky answer instead of silently switching topics."""
        if self.status != "active":
            return False
        mode = INTERVIEW_MODES.get(self.interview_mode, INTERVIEW_MODES["standard"])
        if len(self.questions_asked) >= mode.get("max_questions", 25):
            return False
        if self.follow_up_chain >= 2:
            return False
        score = None
        if isinstance(last_evaluation, dict):
            score = last_evaluation.get("overall_score")
            if not isinstance(score, (int, float)):
                score = last_evaluation.get("score")
        if not isinstance(score, (int, float)) and self.previous_evaluations:
            score = self.previous_evaluations[-1].get("score")
        if not isinstance(score, (int, float)):
            return False
        return score < 60

    def mark_follow_up(self) -> None:
        """Record that the question just asked is a follow-up probe."""
        self.follow_up_count += 1
        self.follow_up_chain += 1
        if self.questions_asked:
            self.questions_asked[-1]["follow_up"] = True

    def finalize(self) -> None:
        """End the interview and lock in the final report fields."""
        if self.status != "active":
            return
        self.status = "completed"
        self.ended_at = datetime.utcnow().isoformat()
        # Skills that were never probed count as improvement areas.
        for skill in self.required_skills_not_tested:
            if skill and skill not in self.weak_areas:
                self.weak_areas.append(skill)
    def generate_report(self) -> Dict[str, Any]:
        """Final interview report with scores, strengths, weaknesses, recommendations."""
        scores = list(self.answer_scores)
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        recs: List[str] = []
        for w in self.weak_areas:
            recs.append(f"Practice {w}: prepare STAR examples, trade-offs, and a hands-on demo.")
        if not recs:
            recs.append("Keep practicing timed answers with concrete metrics and trade-offs.")
        if self.required_skills_not_tested:
            recs.append("Also review untested required skills: " + ", ".join(self.required_skills_not_tested[:5]) + ".")
        strengths = list(self.strong_areas)
        if not strengths and avg >= 60:
            strengths = ["Consistent answers"]
        return {
            "session_id": self.session_id,
            "target_role": self.target_role,
            "overall_score": self.overall_score,
            "average_score": avg,
            "scores": scores,
            "questions_asked": len(self.questions_asked),
            "turn_count": self.turn_count,
            "difficulty": self.difficulty,
            "skills_covered": list(self.skills_covered),
            "required_skills_tested": list(self.required_skills_tested),
            "required_skills_not_tested": list(self.required_skills_not_tested),
            "weak_areas": list(self.weak_areas),
            "weaknesses": list(self.weak_areas),
            "strong_areas": strengths,
            "strengths": strengths,
            "recommendations": recs,
            "preparation_recommendations": recs,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "resume_used": self.resume_used,
            "jd_used": self.jd_used,
            "rag_used": self.rag_used,
        }

    def is_complete(self, follow_up_pending: bool = False) -> bool:
        mode = INTERVIEW_MODES.get(self.interview_mode, INTERVIEW_MODES["standard"])
        min_q, max_q = mode["min_questions"], mode["max_questions"]
        asked_count = len(self.questions_asked)
        if asked_count < min_q:
            return False
        if follow_up_pending:
            return False
        return asked_count >= max_q

    def is_first_turn(self) -> bool:
        return self.turn_count == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id, "user_id": self.user_id,
            "target_role": self.target_role, "experience_level": self.experience_level,
            "interview_mode": self.interview_mode, "job_id": self.job_id,
            "started_at": self.started_at, "ended_at": self.ended_at,
            "questions_asked": len(self.questions_asked), "turn_count": self.turn_count,
            "difficulty": self.difficulty, "current_topic": self.current_topic,
            "current_skill": self.current_skill, "status": self.status,
            "topics_covered": list(self.topics_covered), "skills_covered": list(self.skills_covered),
            "skills_remaining": list(self.skills_remaining),
            "skills_not_tested": list(self.skills_not_tested),
            "required_skills_tested": list(self.required_skills_tested),
            "required_skills_not_tested": list(self.required_skills_not_tested),
            "preferred_skills_tested": list(self.preferred_skills_tested),
            "preferred_skills_not_tested": list(self.preferred_skills_not_tested),
            "resume_claims_tested": list(self.resume_claims_tested),
            "strong_areas": list(self.strong_areas), "weak_areas": list(self.weak_areas),
            "previous_questions": list(self.previous_questions)[-10:],
            "previous_evaluations": list(self.previous_evaluations)[-4:],
            "answer_scores": list(self.answer_scores), "follow_up_count": self.follow_up_count,
            "overall_score": self._compute_overall_score(),
            "resume_used": self.resume_used, "jd_used": self.jd_used, "rag_used": self.rag_used,
        }