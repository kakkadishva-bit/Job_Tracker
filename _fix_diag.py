# -*- coding: utf-8 -*-
"""Add TEMP [INTERVIEW-DIAG] logging to the interview endpoints. (TEMP)"""
import io

def rd(p): return io.open(p, encoding="utf-8").read()
def wr(p, t): io.open(p, "w", encoding="utf-8", newline="").write(t)

p = "app.py"
t = rd(p)

# 1) temporary diag helper (single place to remove later)
marker = "    return _llm_provider_singleton\n"
a = t.index(marker) + len(marker)
HELPER = '''

def _interview_diag(msg: str) -> None:
    """TEMP INTERVIEW-DIAG: print Groq usage facts for the interview endpoints.

    REMOVE after verification. provider=groq, question_llm/evaluation_llm flags
    and the real provider error (HTTP status / exception) on failure - never a
    silent fallback."""
    print("[INTERVIEW-DIAG] " + msg, flush=True)

'''
t = t[:a] + HELPER + t[a:]

# 2) /start diag (before its return)
a = t.index('    return jsonify({\n        "session_id": session_id,\n        "role": role,')
DIAG_START = ('''    _interview_diag(
        "provider=%s model=%s turn=1 question_llm=%s evaluation_llm=%s q_fallback=%r "
        "provider_error=%r"
        % (llm_info.get("runtime"), llm_info.get("model"),
           bool(first_question.get("llm_generated")), "n/a (no answer yet)",
           first_question.get("fallback_reason"),
           (llm_info.get("last_error") or "") or "none"))
''')
t = t[:a] + DIAG_START + t[a:]

# 3) /answer diag (before its return)
a = t.index('    return jsonify({\n        "session_id": session_id,\n        "evaluation": evaluation,')
DIAG_ANSWER = ('''    _provider_error = (getattr(provider, "last_error", "") or "")
    _interview_diag(
        "provider=%s model=%s turn=%s question_llm=%s evaluation_llm=%s follow_up=%s "
        "rag_hits=%s q_fallback=%r eval_fallback=%r provider_error=%r"
        % (llm_info.get("runtime"), llm_info.get("model"), state.turn_count,
           bool((next_question or {}).get("llm_generated")),
           (evaluation or {}).get("evaluated_by") == "llm",
           bool(follow_up), len(rag_results),
           (next_question or {}).get("fallback_reason"),
           (evaluation or {}).get("fallback_reason"),
           _provider_error or "none"))
    if not ((next_question or {}).get("llm_generated")
            and (evaluation or {}).get("evaluated_by") == "llm"):
        _interview_diag(
            "GROQ NOT USED THIS TURN -> eval_fallback=%r question_fallback=%r "
            "provider_error=%r (fallback served deliberately, reason logged)"
            % ((evaluation or {}).get("fallback_reason"),
               (next_question or {}).get("fallback_reason"),
               _provider_error or "no provider configured"))
''')
t = t[:a] + DIAG_ANSWER + t[a:]
wr(p, t)
print("app.py: [INTERVIEW-DIAG] logging added to /start and /answer")
