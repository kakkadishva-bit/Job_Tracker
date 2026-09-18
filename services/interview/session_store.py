"""
services/interview/session_store.py
Database-backed persistence for interview sessions.

Why this exists
---------------
Interview state used to live in a module-level dict (``interview_sessions``).
With Gunicorn running several workers, a session created by worker A was
invisible to workers B/C/D, so a follow-up request was answered with
"Invalid or expired session" (HTTP 400) most of the time. That is what forced
users to retry an answer 4-5 times, and the retries that did land were processed
twice - producing repeated questions.

This store keeps the authoritative session in the database, so any worker can
serve any turn of the same interview.

Storage layout (existing tables - no schema change)
---------------------------------------------------
``interview_sessions``
  * ``anon_session_id`` - the public UUID handed to the browser (lookup key)
  * ``user_id``         - owner, enforced on every load (IDOR protection)
  * ``state_json``      - ``{"state": <InterviewState.serialize()>, "extras": {...}}``
  * counters/status/score columns duplicated from state for cheap querying

``interview_messages``
  * one row per interviewer question and per candidate answer, with the
    evaluation JSON attached to the candidate row.

Every method degrades safely: if the database is unavailable the caller gets
``None``/``False`` and the API layer falls back to its in-process cache instead
of failing the request.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from models.user_model import db, InterviewSession, InterviewMessage
from services.interview.state import InterviewState

logger = logging.getLogger(__name__)

#: Context blobs that must survive alongside the state (JSON-safe values only).
EXTRAS_FIELDS = (
    "resume_context",
    "job_context",
    "required_skills",
    "preferred_skills",
    "conversation",
)


def _json_safe(value: Any) -> Any:
    """Best-effort conversion to something json.dumps() accepts."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return str(value)


class InterviewSessionStore:
    """Persist and reload interview sessions through the database."""

    # -- helpers ------------------------------------------------------
    @staticmethod
    def _state_to_json(state: InterviewState, extras: Dict[str, Any]) -> str:
        payload = {
            "state": _json_safe(state.serialize()),
            "extras": {key: _json_safe(extras.get(key)) for key in EXTRAS_FIELDS},
        }
        return json.dumps(payload)

    @staticmethod
    def _coerce_job_id(value: Any) -> Optional[int]:
        """``job_id`` is an Integer column; callers may send "", None or "12"."""
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _apply_columns(cls, row: InterviewSession, state: InterviewState) -> None:
        """Mirror frequently-queried state fields onto real columns."""
        row.target_role = (state.target_role or "")[:200] or "Interview"
        row.company = str(state.company)[:200] if state.company else None
        row.experience_level = str(state.experience_level or "mid")[:20]
        row.interview_mode = str(state.interview_mode or "standard")[:20]
        row.status = str(state.status or "active")[:20]
        row.question_count = len(state.questions_asked)
        row.turn_count = state.turn_count
        row.overall_score = float(state.overall_score)
        row.current_topic = str(state.current_topic)[:100] if state.current_topic else None
        row.current_skill = str(state.current_skill)[:200] if state.current_skill else None
        row.difficulty = str(state.difficulty or "medium")[:20]

    # -- public API ---------------------------------------------------
    @classmethod
    def create(cls, state: InterviewState, extras: Dict[str, Any]) -> Optional[int]:
        """Insert a new session row. Returns the row id, or None on failure."""
        try:
            row = InterviewSession()
            row.anon_session_id = str(state.session_id)[:64]
            try:
                row.user_id = int(state.user_id) if state.user_id not in (None, "") else None
            except (TypeError, ValueError):
                row.user_id = None
            row.job_id = cls._coerce_job_id(state.job_id)
            row.resume_version_id = (str(extras.get("resume_version_id") or "")[:64] or None)
            row.job_description = _json_safe(extras.get("job_description") or None)
            cls._apply_columns(row, state)
            row.ended_at = None
            row.state_json = cls._state_to_json(state, extras)
            db.session.add(row)
            db.session.commit()
            return row.id
        except Exception as exc:  # pragma: no cover - depends on DB availability
            db.session.rollback()
            logger.warning("Interview session create failed: %s", exc)
            return None

    @classmethod
    def load(cls, session_id: str, user_id: Any) -> Optional[Tuple[InterviewState, Dict[str, Any], int]]:
        """Load a session owned by ``user_id``.

        Returns ``(state, extras, row_id)`` or ``None`` when the session does not
        exist, is not owned by this user, or the database is unavailable. The
        ownership test lives here so no route can forget it.
        """
        if not session_id:
            return None
        try:
            row = InterviewSession.query.filter_by(
                anon_session_id=str(session_id)[:64]).first()
            if row is None:
                return None
            expected_user_id = getattr(user_id, "id", user_id)
            try:
                expected_user_id = int(expected_user_id) if expected_user_id not in (None, "") else None
            except (TypeError, ValueError):
                expected_user_id = None
            if row.user_id != expected_user_id:
                return None  # IDOR guard - do not disclose existence
            payload = json.loads(row.state_json) if row.state_json else {}
            state = InterviewState.from_dict(payload.get("state") or {})
            extras = payload.get("extras") or {}
            if not state.session_id:
                state.session_id = str(session_id)
            return state, extras, row.id
        except Exception as exc:  # pragma: no cover - depends on DB availability
            db.session.rollback()
            logger.warning("Interview session load failed: %s", exc)
            return None

    @classmethod
    def save(cls, state: InterviewState, extras: Dict[str, Any],
             row_id: Optional[int] = None) -> bool:
        """Persist the current state. Idempotent: updates the existing row."""
        try:
            row = None
            if row_id is not None:
                row = db.session.get(InterviewSession, row_id)
            if row is None:
                row = InterviewSession.query.filter_by(
                    anon_session_id=str(state.session_id)[:64]).first()
            if row is None:
                return cls.create(state, extras) is not None
            cls._apply_columns(row, state)
            if state.ended_at:
                try:
                    row.ended_at = datetime.fromisoformat(str(state.ended_at).replace("Z", "+00:00")).replace(tzinfo=None)
                except (TypeError, ValueError):
                    row.ended_at = datetime.utcnow()
            row.state_json = cls._state_to_json(state, extras)
            db.session.commit()
            return True
        except Exception as exc:  # pragma: no cover - depends on DB availability
            db.session.rollback()
            logger.warning("Interview session save failed: %s", exc)
            return False

    @classmethod
    def lookup_owner(cls, session_id: str) -> Optional[int]:
        """Owner user id for a session, or None when no such session exists.

        Used to tell "no such session" (400, legacy behaviour) apart from
        "session exists but belongs to another user" (404, IDOR guard).
        """
        if not session_id:
            return None
        try:
            row = InterviewSession.query.filter_by(
                anon_session_id=str(session_id)[:64]).first()
            return row.user_id if row is not None else None
        except Exception as exc:  # pragma: no cover - depends on DB availability
            db.session.rollback()
            logger.warning("Interview session owner lookup failed: %s", exc)
            return None

    @classmethod
    def add_message(cls, row_id: Optional[int], role: str, content: str,
                    question_type: str = "", question_id: str = "",
                    evaluation: Optional[Dict[str, Any]] = None) -> bool:
        """Append one conversation message (interviewer question or answer)."""
        if row_id is None or not content:
            return False
        try:
            row = InterviewMessage()
            row.session_id = row_id
            row.role = (role or "interviewer")[:20]
            row.content = str(content)
            row.question_type = (str(question_type or "")[:50] or None)
            row.question_id = (str(question_id or "")[:64] or None)
            row.evaluation_json = (json.dumps(_json_safe(evaluation))
                                   if evaluation is not None else None)
            db.session.add(row)
            db.session.commit()
            return True
        except Exception as exc:  # pragma: no cover - depends on DB availability
            db.session.rollback()
            logger.warning("Interview message persist failed: %s", exc)
            return False

    @classmethod
    def messages(cls, session_id: str, user_id: Any) -> list:
        """Stored conversation for a session owned by ``user_id`` (oldest first)."""
        try:
            row = InterviewSession.query.filter_by(
                anon_session_id=str(session_id)[:64]).first()
            if row is None or row.user_id != getattr(user_id, "id", None):
                return []
            rows = (InterviewMessage.query.filter_by(session_id=row.id)
                    .order_by(InterviewMessage.id.asc()).all())
            return [{
                "role": m.role,
                "content": m.content,
                "question_type": m.question_type,
                "question_id": m.question_id,
                "evaluation": (json.loads(m.evaluation_json) if m.evaluation_json else None),
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
            } for m in rows]
        except Exception as exc:  # pragma: no cover - depends on DB availability
            db.session.rollback()
            logger.warning("Interview message read failed: %s", exc)
            return []

    @classmethod
    def count_answers(cls, session_id: str, user_id: Any) -> int:
        """Number of candidate answers stored for this session (duplicate check)."""
        return sum(1 for m in cls.messages(session_id, user_id)
                   if m.get("role") == "candidate")

    @classmethod
    def count_messages(cls, session_id: str, user_id: Any, role: str = "") -> int:
        """Stored message count, optionally filtered by role."""
        msgs = cls.messages(session_id, user_id)
        if role:
            msgs = [m for m in msgs if m.get("role") == role]
        return len(msgs)