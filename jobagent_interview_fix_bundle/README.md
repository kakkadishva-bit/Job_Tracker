# JobAgent Interview Fix

This bundle fixes the current interview implementation found in `job-track.zip`.

Critical defects found:
- `InterviewState(session_id, config)` was incompatible with the class constructor.
- `InterviewState` had no `record_answer`, `record_question`, `should_continue`, `finalize`, or `overall_score` API used by `app.py`.
- `QuestionGenerator` had no `get_next_question`, while `app.py` called it.
- `get_first_question()` returned a string while the frontend expected `data.question.question`, causing the blank AI bubble.
- `InterviewContextBuilder` called `retrieve_context()`, but `RAGPipeline` exposes `retrieve()`.
- `QuestionGenerator` was instantiated with `llm_provider=None`, so no local LLM was ever used.
- The frontend cleared the input but had no reliable session recovery/history.

Use the replacement Python modules plus the supplied app/frontend route patch. Do not claim 100% accuracy; the system is designed for grounded, testable answers with LLM/RAG and deterministic fallback.
