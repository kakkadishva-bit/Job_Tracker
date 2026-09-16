"""
services/training/dataset.py
Dataset preparation for interview fine-tuning.
"""
import json
import logging
import os
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class InterviewExample:
    """A single interview training example."""
    question: str
    answer: str
    context: str = ""
    score: float = 0.0
    skill: str = ""
    difficulty: str = "MEDIUM"
    follow_up: str = ""


class InterviewDataset:
    """Dataset of interview Q&A examples for fine-tuning."""

    def __init__(self):
        self.examples: List[InterviewExample] = []

    def add_example(self, question: str, answer: str, context: str = "",
                    score: float = 0.0, skill: str = "", difficulty: str = "MEDIUM"):
        self.examples.append(InterviewExample(
            question=question,
            answer=answer,
            context=context,
            score=score,
            skill=skill,
            difficulty=difficulty,
        ))

    def split(self, train_ratio: float = 0.8) -> Tuple["InterviewDataset", "InterviewDataset"]:
        """Split into train and validation sets."""
        n = len(self.examples)
        split_idx = int(n * train_ratio)
        train_ds = InterviewDataset()
        train_ds.examples = self.examples[:split_idx]
        val_ds = InterviewDataset()
        val_ds.examples = self.examples[split_idx:]
        return train_ds, val_ds

    def __len__(self):
        return len(self.examples)

    def __getitem__(self, idx):
        return self.examples[idx]

    def to_jsonl(self, path: str):
        """Export to JSONL format for training."""
        with open(path, "w", encoding="utf-8") as f:
            for ex in self.examples:
                f.write(json.dumps({
                    "instruction": ex.question,
                    "input": ex.context,
                    "output": ex.answer,
                    "score": ex.score,
                    "skill": ex.skill,
                    "difficulty": ex.difficulty,
                }, ensure_ascii=False) + "\n")

    @classmethod
    def from_jsonl(cls, path: str) -> "InterviewDataset":
        """Load from JSONL format."""
        ds = cls()
        if not os.path.exists(path):
            logger.warning("Dataset file not found: %s", path)
            return ds
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line.strip())
                    ds.add_example(
                        question=data.get("question", data.get("instruction", "")),
                        answer=data.get("answer", data.get("output", "")),
                        context=data.get("context", data.get("input", "")),
                        score=data.get("score", 0.0),
                        skill=data.get("skill", ""),
                        difficulty=data.get("difficulty", "MEDIUM"),
                    )
                except json.JSONDecodeError:
                    continue
        return ds


def prepare_training_data(sessions_dir: str, output_dir: str) -> InterviewDataset:
    """
    Prepare training data from recorded interview sessions.

    Args:
        sessions_dir: Directory containing interview session JSON files.
        output_dir: Directory to save processed training data.

    Returns:
        InterviewDataset with all examples.
    """
    os.makedirs(output_dir, exist_ok=True)
    dataset = InterviewDataset()

    if not os.path.isdir(sessions_dir):
        logger.warning("Sessions directory not found: %s", sessions_dir)
        return dataset

    for filename in os.listdir(sessions_dir):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(sessions_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                session = json.load(f)

            conversation = session.get("conversation", [])
            for i in range(0, len(conversation) - 1, 2):
                if conversation[i].get("role") == "interviewer" and conversation[i + 1].get("role") == "candidate":
                    q = conversation[i].get("content", "")
                    a = conversation[i + 1].get("content", "")
                    evaluation = conversation[i + 1].get("evaluation", {})
                    score = evaluation.get("overall_score", 50)
                    skill = conversation[i].get("skill", "")
                    difficulty = session.get("difficulty", "MEDIUM")
                    dataset.add_example(q, a, score=score, skill=skill, difficulty=difficulty)
        except Exception as e:
            logger.warning("Failed to process session %s: %s", filename, e)

    output_path = os.path.join(output_dir, "training_data.jsonl")
    dataset.to_jsonl(output_path)
    logger.info("Prepared %d training examples from %s", len(dataset), sessions_dir)
    return dataset
