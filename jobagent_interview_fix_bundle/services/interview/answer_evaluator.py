"""Grounded answer evaluation with local LLM and deterministic fallback."""
import re
from typing import Any, Dict

class AnswerEvaluator:
    def __init__(self, llm_provider=None): self.llm_provider = llm_provider

    def evaluate(self, question: str, answer: str, context: str = "") -> Dict[str, Any]:
        answer = (answer or "").strip()
        if not answer: return self._fallback(question, answer)
        if self.llm_provider:
            try:
                result = self.llm_provider.generate_json(
                    f"Question: {question}\nCandidate answer: {answer}\nReference/context: {context[:6000]}\n"
                    "Evaluate only what can be supported by the question/context. Do not invent facts. "
                    "Score each 0-100: correctness,relevance,depth,clarity,practical_understanding,problem_solving. "
                    "Return JSON with those scores, overall_score, strengths[], weaknesses[], missing_topics[], follow_up_needed, reasoning.",
                    system_prompt="You are a strict interview evaluator. Accuracy and evidence matter more than verbosity.", max_tokens=500)
                if isinstance(result, dict) and self._valid(result): return result
            except Exception: pass
        return self._fallback(question, answer)

    def _valid(self, r):
        return all(k in r for k in ["overall_score","correctness","relevance","depth","clarity","practical_understanding","problem_solving"])

    def _fallback(self, q, a):
        words = len(a.split())
        technical = len(re.findall(r"\b(api|database|model|python|docker|rag|sql|algorithm|testing|deployment|accuracy|precision|recall|architecture|cache|vector|embedding|fastapi|aws)\b", a.lower()))
        completeness = min(100, 25 + min(words, 50) + technical * 4)
        clarity = max(35, min(100, 90 - len(re.findall(r"\b(um|uh|maybe|i think|not sure)\b", a.lower())) * 12))
        overall = round(0.30*completeness + 0.15*clarity + 0.20*min(100, technical*12+30) + 0.20*min(100, words*2) + 0.15*completeness)
        return {"overall_score":overall,"correctness":min(100,30+technical*10),"relevance":completeness,"depth":min(100,20+technical*10+min(words,30)),"clarity":clarity,"practical_understanding":min(100,25+technical*8),"problem_solving":min(100,30+technical*7),"strengths":["Addresses the question" if words >= 15 else "Concise response"],"weaknesses":["Add a concrete example" if words < 30 else "Add more specific evidence where useful"],"missing_topics":[],"follow_up_needed": overall < 70 or words < 15,"recommended_follow_up_type":"clarification" if words < 15 else "deeper_technical","reasoning":"Deterministic fallback evaluation used because local LLM evaluation was unavailable."}
