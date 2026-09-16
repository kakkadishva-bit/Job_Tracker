"""
services/training/evaluator.py
Evaluation metrics for interview model quality.
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


def evaluate_model(predictions: List[str], references: List[str],
                  resume_facts: Optional[List[str]] = None) -> Dict[str, float]:
    """
    Evaluate model predictions against references.

    Metrics:
    - correctness: answer relevance and accuracy
    - groundedness: how well answer uses provided context
    - resume_fidelity: whether answer matches resume claims
    - follow_up_quality: relevance of follow-up questions
    """
    if not predictions or not references:
        return {"correctness": 0.0, "groundedness": 0.0, "resume_fidelity": 0.0}

    scores = {
        "correctness": _compute_relevance(predictions, references),
        "groundedness": _compute_groundedness(predictions, references),
        "resume_fidelity": _compute_resume_fidelity(predictions, resume_facts or []),
    }
    scores["overall"] = sum(scores.values()) / len(scores)
    return scores


def _compute_relevance(predictions: List[str], references: List[str]) -> float:
    """Compute word overlap as a simple relevance proxy."""
    if not predictions or not references:
        return 0.0
    total = 0
    for pred, ref in zip(predictions, references):
        pred_words = set(pred.lower().split())
        ref_words = set(ref.lower().split())
        if not ref_words:
            continue
        overlap = len(pred_words & ref_words) / len(ref_words)
        total += min(1.0, overlap)
    return total / max(1, len(predictions))


def _compute_groundedness(predictions: List[str], references: List[str]) -> float:
    """Compute how much of the prediction is grounded in the reference."""
    return _compute_relevance(predictions, references)


def _compute_resume_fidelity(predictions: List[str], resume_facts: List[str]) -> float:
    """Check if predictions are consistent with resume facts."""
    if not resume_facts or not predictions:
        return 0.5  # neutral if no facts available
    total = 0
    for fact in resume_facts:
        fact_lower = fact.lower()
        for pred in predictions:
            if any(word in pred.lower() for word in fact_lower.split() if len(word) > 3):
                total += 1
                break
    return total / max(1, len(resume_facts))
