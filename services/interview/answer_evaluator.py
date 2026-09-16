"""
services/interview/answer_evaluator.py
Evaluates candidate answers using structured scoring rubric.
"""
import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

STRONG_SIGNALS = [
    "specifically", "example", "because", "trade-off", "tradeoffs",
    "however", "challenge", "optimized", "performance", "architecture",
    "implement", "deployed", "production", "solved", "reduced"
]
WEAK_SIGNALS = [
    "um", "uh", "like", "you know", "i think", "maybe", "sort of",
        "i'm not sure", "i guess", "basically"
]


class AnswerEvaluator:
    """Evaluates candidate answers and returns structured scores."""

    def __init__(self, llm_provider=None):
        self.llm_provider = llm_provider
        # Exact reason the LLM (Groq) path was not used for the last
        # evaluation ("" when it worked). Surfaced as fallback_reason so a
        # heuristic score is never mistaken for a Groq evaluation.
        self.last_llm_error = ""
    def evaluate(self, question: str, answer: str, context: str = "",
                 prev_evaluation: Dict[str, Any] = None) -> Dict[str, Any]:
        """Evaluate a candidate answer and return structured feedback.

        Groq is tried first (this specific answer vs this specific question,
        with resume/JD/RAG context and the previous evaluation for continuity).
        The deterministic scorer is only a fallback and is ALWAYS tagged with
        the exact reason the LLM path was not used."""
        self.last_llm_error = ""
        if not answer or not answer.strip():
            return self._mark_fallback(
                self._empty_answer_result(),
                "empty_answer: nothing was submitted to evaluate")
        if self.llm_provider:
            llm_result = self._evaluate_with_llm(question, answer, context, prev_evaluation)
            if llm_result:
                return llm_result
        else:
            self.last_llm_error = ("no_llm_provider: AnswerEvaluator was created "
                                   "without an LLM provider")
        return self._mark_fallback(self._evaluate_heuristic(question, answer, context))

    def _provider_error(self) -> str:
        """Last error reported by the LLM provider (Groq), for diagnostics."""
        return (getattr(self.llm_provider, "last_error", "") or "no reason reported")

    @staticmethod
    def _prev_eval_str(prev_evaluation) -> str:
        if not isinstance(prev_evaluation, dict):
            return "none (this is the first answer)"
        return ("score=%s, weaknesses=%s" % (
            prev_evaluation.get("overall_score", prev_evaluation.get("score", "?")),
            str(prev_evaluation.get("weaknesses", ""))[:180]))

    def _mark_fallback(self, evaluation: Dict[str, Any],
                       reason: str = "") -> Dict[str, Any]:
        """Tag a heuristic evaluation with why Groq was not used."""
        if isinstance(evaluation, dict):
            evaluation.setdefault("llm_generated", False)
            evaluation.setdefault("evaluated_by", "heuristic")
            evaluation.setdefault(
                "fallback_reason",
                reason or self.last_llm_error
                or (getattr(self.llm_provider, "last_error", "") if self.llm_provider else "")
                or "llm_not_configured_or_unavailable")
        return evaluation

    def _evaluate_with_llm(self, question: str, answer: str, context: str = "",
                           prev_evaluation: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """Asks Groq to actually judge this specific answer against this
        specific question (with resume/JD/RAG context and the previous
        evaluation for continuity). Returns None on any failure so the caller
        falls back to the deterministic scorer - a flaky LLM call should never
        break the interview. Every failure records the real reason in
        self.last_llm_error instead of failing silently."""
        try:
            result = self.llm_provider.generate_json(
                f"Question asked: {question}\n"
                f"Candidate's answer: {answer}\n"
                f"Previous evaluation of this candidate (for continuity): {self._prev_eval_str(prev_evaluation)}\n"
                f"Context (resume/job description excerpt, may be empty): {context[:2000]}\n\n"
                "Evaluate ONLY what this specific answer actually says - do not invent facts "
                "the candidate didn't state. Score each dimension 0-100: correctness, relevance, "
                "depth, clarity, practical_understanding, problem_solving. Then give overall_score "
                "(0-100), strengths (list of short phrases specific to THIS answer), weaknesses "
                "(list of short phrases specific to THIS answer, not generic filler), missing_topics "
                "(list, can be empty), follow_up_needed (true/false), recommended_follow_up_type "
                "(one of: clarification, deeper_technical, topic_transition), and reasoning (one sentence).",
                system_prompt=(
                    "You are a precise, evidence-based technical interview evaluator. "
                    "Your feedback must be specific to the actual content of this answer, "
                    "never generic boilerplate. Be fair but rigorous."
                ),
                max_tokens=600,
            )
        except Exception as exc:
            self.last_llm_error = ("llm_call_failed: %s: %s (provider reason: %s)"
                                   % (type(exc).__name__, exc, self._provider_error()))
            logger.warning("LLM answer evaluation failed, using heuristic fallback: %s",
                           self.last_llm_error)
            return None

        if not isinstance(result, dict):
            self.last_llm_error = ("llm_call_failed: Groq returned a non-dict reply "
                                   "(provider reason: %s)" % self._provider_error())
            logger.warning("LLM evaluation returned non-dict, using heuristic fallback")
            return None
        required_keys = {"overall_score", "correctness", "relevance", "depth",
                          "clarity", "practical_understanding", "problem_solving"}
        if not required_keys.issubset(result.keys()):
            self.last_llm_error = ("invalid_json: Groq reply was missing the required "
                                   "scoring keys (provider reason: %s)" % self._provider_error())
            logger.warning("LLM evaluation missing required keys, using heuristic fallback: %s",
                           self.last_llm_error)
            return None

        result.setdefault("strengths", [])
        result.setdefault("weaknesses", [])
        result.setdefault("missing_topics", [])
        result.setdefault("follow_up_needed", result.get("overall_score", 100) < 70)
        result.setdefault("recommended_follow_up_type", "deeper_technical")
        result.setdefault("reasoning", "LLM-evaluated response.")
        result["evaluated_by"] = "llm"
        result["llm_generated"] = True
        result.pop("fallback_reason", None)
        return result

    def _evaluate_heuristic(self, question: str, answer: str, context: str = "") -> Dict[str, Any]:
        """Deterministic fallback scorer - used when no LLM is configured,
        or when the LLM call fails. Word-count/keyword based, so it's not
        as sharp as the LLM path, but it always works offline."""
        scores = self._compute_scores(question, answer, context)
        strengths = self._extract_strengths(answer, scores)
        weaknesses = self._extract_weaknesses(answer, scores)
        missing = self._extract_missing_topics(question, answer)
        overall = self._compute_overall_score(scores)

        return {
            "overall_score": overall,
            "correctness": scores["correctness"],
            "relevance": scores["relevance"],
            "depth": scores["depth"],
            "clarity": scores["clarity"],
            "practical_understanding": scores["practical_understanding"],
            "problem_solving": scores["problem_solving"],
            "strengths": strengths,
            "weaknesses": weaknesses,
            "missing_topics": missing,
            "follow_up_needed": scores["follow_up_needed"],
            "recommended_follow_up_type": scores["follow_up_type"],
            "reasoning": scores["reasoning"],
            "evaluated_by": "heuristic",
        }

    def _compute_scores(self, question: str, answer: str, context: str) -> Dict[str, Any]:
        answer_stripped = answer.strip()
        word_count = len(answer_stripped.split())
        char_count = len(answer_stripped)

        strong_signals = sum(1 for s in STRONG_SIGNALS if s.lower() in answer.lower())
        weak_signals = sum(1 for w in WEAK_SIGNALS if re.search(r"\b" + re.escape(w) + r"\b", answer.lower()))
        has_technical_terms = self._count_technical_indicators(answer)
        has_examples = bool(re.search(r"(for example|such as|e\.g|for instance|like)\b", answer.lower())) and word_count > 20
        has_tradeoffs = bool(re.search(r"\b(trade.?off|versus|vs|however|whereas|compared to|on the other hand)\b", answer.lower()))
        has_structure = bool(re.search(r"\b(first|second|third|also|additionally|furthermore|finally)\b", answer.lower()))

        # Relevance: based on answer length - floor at 0, no artificial minimum
        if word_count < 3:
            relevance = 5
        elif word_count < 10:
            relevance = 20
        elif word_count < 20:
            relevance = 40
        elif word_count < 40:
            relevance = 55
        elif word_count < 80:
            relevance = 70
        else:
            relevance = min(90, 70 + (word_count - 80) // 10)

        # Depth: technical terms, examples, tradeoffs, structure
        depth = 0
        depth += min(50, has_technical_terms * 10)  # up to 50 from technical content
        depth += strong_signals * 8                  # each strong signal: "because", "therefore" etc.
        depth += 15 if has_examples else 0
        depth += 12 if has_tradeoffs else 0
        depth += 8 if has_structure else 0
        depth = min(100, depth)

        # Clarity: penalise vague filler, reward structure
        clarity = 70  # baseline
        clarity -= weak_signals * 10
        if has_structure:
            clarity += 15
        if word_count < 5:
            clarity = min(clarity, 30)
        clarity = max(0, min(100, clarity))

        # Correctness: technical content + examples + not vague
        correctness = 0
        correctness += min(50, has_technical_terms * 12)
        correctness += strong_signals * 8
        correctness += 12 if has_examples else 0
        if word_count < 4 or (weak_signals > 1 and has_technical_terms == 0):
            correctness = min(correctness, 25)
        correctness = min(100, correctness)

        # Practical understanding
        practical = 0
        practical += min(40, has_technical_terms * 10)
        has_implementation = bool(re.search(r"\b(implement|build|develop|deploy|use|used|apply|applied|built|deployed)\b", answer.lower()))
        if has_implementation:
            practical += 20
        if has_examples:
            practical += 15
        practical = min(100, practical)

        # Problem solving
        problem_solving = 0
        problem_solving += strong_signals * 8
        has_problem = bool(re.search(r"\b(challenge|problem|issue|difficult|hard|solved|solution|solve|approach|handle|handled)\b", answer.lower()))
        if has_problem:
            problem_solving += 20
        if has_tradeoffs:
            problem_solving += 15
        problem_solving = min(100, problem_solving)

        follow_up_needed = clarity < 70 or depth < 50 or correctness < 50 or word_count < 15
        if follow_up_needed:
            follow_up_type = "deeper_technical" if depth < 40 or correctness < 40 else "clarification"
        else:
            follow_up_type = "topic_transition"

        return {
            "correctness": min(100, correctness),
            "relevance": min(100, relevance),
            "depth": min(100, depth),
            "clarity": min(100, clarity),
            "practical_understanding": min(100, practical),
            "problem_solving": min(100, problem_solving),
            "follow_up_needed": follow_up_needed,
            "follow_up_type": follow_up_type,
            "reasoning": self._build_reasoning(correctness, depth, clarity, word_count, strong_signals, weak_signals),
        }

    def _count_technical_indicators(self, text: str) -> int:
        technical_keywords = [
            "api", "database", "docker", "kubernetes", "fastapi", "flask",
            "machine learning", "deep learning", "neural", "tensor",
            "transformer", "rag", "llm", "vector", "embed", "sql",
            "python", "javascript", "react", "aws", "cloud", "microservice",
            "container", "deployment", "ci/cd", "pipeline", "model", "training",
            "overfitting", "regularization", "gradient", "loss", "accuracy",
            "precision", "recall", "f1", "confusion", "bias", "variance",
        ]
        text_lower = text.lower()
        count = 0
        for kw in technical_keywords:
            if kw in text_lower:
                count += 1
        return count

    def _compute_overall_score(self, scores: Dict[str, Any]) -> int:
        weights = {
            "correctness": 0.25, "relevance": 0.10, "depth": 0.20,
            "clarity": 0.15, "practical_understanding": 0.15, "problem_solving": 0.15,
        }
        # Each score is 0-100 and weights sum to 1.0, so the weighted sum
        # already lands on a 0-100 scale — round to a clean integer.
        total = sum(scores[k] * weights[k] for k in weights)
        return int(round(total))

    def _extract_strengths(self, answer: str, scores: Dict[str, Any]) -> List[str]:
        strengths = []
        if scores["correctness"] > 60:
            strengths.append("High technical correctness")
        if scores["depth"] > 50:
            strengths.append("Good depth of explanation")
        if scores["practical_understanding"] > 50:
            strengths.append("Demonstrates practical understanding")
        if scores["problem_solving"] > 50:
            strengths.append("Addresses problems/solutions")
        if len(answer.split()) > 40:
            strengths.append("Detailed response")
        if sum(1 for s in STRONG_SIGNALS if s.lower() in answer.lower()) > 2:
            strengths.append("Uses technical depth language")
        return strengths

    def _extract_weaknesses(self, answer: str, scores: Dict[str, Any]) -> List[str]:
        weaknesses = []
        if scores["correctness"] < 50:
            weaknesses.append("Limited technical detail")
        if scores["depth"] < 40:
            weaknesses.append("Shallow explanation")
        if scores["clarity"] < 60:
            weaknesses.append("Lacks structure/clarity")
        if scores["practical_understanding"] < 40:
            weaknesses.append("Missing concrete examples")
        if len(answer.split()) < 15:
            weaknesses.append("Brief response")
        if sum(1 for w in WEAK_SIGNALS if re.search(r"\b" + re.escape(w) + r"\b", answer.lower())) > 1:
            weaknesses.append("Uses filler language")
        return weaknesses

    def _extract_missing_topics(self, question: str, answer: str) -> List[str]:
        missing = []
        q_lower = question.lower()
        a_lower = answer.lower()
        if ("trade" not in a_lower and "versus" not in a_lower and "vs" not in a_lower
                and any(kw in q_lower for kw in ["difference", "trade-off", "versus"])):
            missing.append("Trade-offs not discussed")
        if not re.search(r"\b(for example|such as|e\.g)\b", a_lower) and len(answer.split()) > 30:
            missing.append("Concrete examples missing")
        if any(kw in q_lower for kw in ["implement", "build", "use", "deploy"]):
            if not re.search(r"\b(implement|build|deployed|used)\b", a_lower):
                missing.append("Implementation details missing")
        return missing[:3]

    def _build_reasoning(self, correctness: int, depth: int, clarity: int,
                         word_count: int, strong_signals: int, weak_signals: int) -> str:
        parts = []
        if word_count < 5:
            parts.append("very brief response")
        elif word_count < 15:
            parts.append("short response")
        else:
            parts.append("detailed response")
        if strong_signals > 1:
            parts.append(f"{strong_signals} technical depth signals")
        if weak_signals > 0:
            parts.append(f"{weak_signals} filler signals")
        if correctness > 60:
            parts.append("high correctness")
        elif correctness < 40:
            parts.append("low correctness")
        if depth > 50:
            parts.append("good depth")
        elif depth < 30:
            parts.append("shallow depth")
        return "; ".join(parts)

    def _empty_answer_result(self) -> Dict[str, Any]:
        return {
            "overall_score": 10,
            "correctness": 10, "relevance": 10, "depth": 10,
            "clarity": 10, "practical_understanding": 10, "problem_solving": 10,
            "strengths": [], "weaknesses": ["No answer provided"],
            "missing_topics": [],
            "follow_up_needed": True, "recommended_follow_up_type": "clarification",
            "reasoning": "Empty answer provided",
        }