"""Live 10-turn adaptive interview E2E check (server-side, via Flask test client)."""
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

RESUME = """JANE DOE
Machine Learning Engineer
jane@example.com | github.com/janedoe

SUMMARY
ML engineer with 3 years experience building retrieval systems.

EXPERIENCE
ML Engineer, Acme Corp (2022-2025)
- Built RAG chatbot using FAISS for document retrieval, serving 10k queries/day
- Deployed FastAPI microservice for model inference on Docker
- Trained and evaluated machine learning models for intent classification

PROJECTS
Resume Intelligence Bot
- Developed a Python pipeline extracting skills from resumes using spaCy NER
- Implemented FAISS vector index for semantic search over job descriptions

SKILLS
Python, Machine Learning, RAG, FAISS, FastAPI, spaCy, Docker, SQL
"""

JD = """Senior Machine Learning Engineer

Requirements:
- Python (5+ years)
- Machine Learning and model evaluation
- RAG (Retrieval-Augmented Generation) pipelines
- FastAPI backend services
- Docker containerization and deployment
"""

ANSWERS = [
    "In my RAG chatbot at Acme I used FAISS with IndexFlatIP over 384-dim MiniLM embeddings. "
    "I chunked documents at 512 tokens with 64-token overlap, stored embeddings with document IDs, "
    "and retrieved top-k=5 then reranked with a cross-encoder. Recall@5 improved from 0.61 to 0.84.",
    "I used FAISS because it was fast.",
    "Overfitting is when the model gets 100% accuracy on training data and it is good for production "
    "because the model has memorized everything so it will always be right.",
    "To reduce overfitting in production I combine several techniques. First L2 regularization with "
    "lambda tuned by cross-validation. Second early stopping on a validation split. Third data "
    "augmentation for the minority class. I also monitor train/val loss divergence and drift; when "
    "the gap exceeds 5% I retrain. On the Acme intent model this took val F1 from 0.72 to 0.89 while "
    "cutting inference latency by choosing a distilled student model.",
    "FastAPI is good. I used it. It handles requests and returns JSON.",
    "For the FastAPI inference service I used Pydantic models for validation, dependency injection "
    "for the model loader, uvicorn with 4 workers, and a /health endpoint. I added request timeouts "
    "and a Redis cache for repeated queries which cut p95 latency from 900ms to 120ms.",
    "Docker is a virtual machine that lets you run a different operating system. I do not use it much, "
    "I just run python app.py on my laptop and it works the same.",
    "I containerize with a multi-stage Dockerfile: builder stage installs dependencies into a venv, "
    "runtime stage copies only the venv, runs as a non-root user, and sets no build tools. Image size "
    "went from 1.4GB to 380MB. I pin base image digests and scan with Trivy in CI.",
    "For production RAG I would change four things: move from IndexFlatIP to IVF-PQ for scale beyond a "
    "million vectors, add hybrid BM25 + dense retrieval to fix rare-term misses, cache embeddings and "
    "answers, and add retrieval evaluation in CI measuring Recall@k and groundedness. I would also "
    "version the index alongside the embedding model so a model swap cannot silently break retrieval.",
    "I think chunk size is 512 maybe? I just used the default.",
]


def main():
    from app import app
    client = app.test_client()
    payload = {
        "role": "Senior Machine Learning Engineer",
        "company": "Acme",
        "experience_level": "senior",
        "interview_mode": "technical",
        "job_context": {"title": "Senior Machine Learning Engineer",
                        "description": JD, "analyzed": True},
        "required_skills": ["Python", "Machine Learning", "RAG", "FastAPI", "Docker"],
        "resume_context": {"text": RESUME},
    }
    r = client.post("/api/interview-prep/start", json=payload)
    if r.status_code != 200:
        print("START FAILED", r.status_code, r.get_data(as_text=True)[:500])
        return 1
    data = r.get_json()
    sid = data["session_id"]
    print("=" * 100)
    print("LLM runtime : %s / %s   available=%s" % (
        data.get("llm_runtime"), data.get("llm_model"), data.get("llm_available")))
    print("resume_used=%s  jd_used=%s  rag_used=%s" % (
        data.get("resume_used"), data.get("jd_used"), data.get("rag_used")))
    print("question_fallback_reason=%r" % (data.get("question_fallback_reason"),))
    _rag = data.get("rag") or {}
    print("rag: available=%s backend=%s chunks=%s embeddings=%s error=%r" % (
        _rag.get("available"), _rag.get("backend"), _rag.get("chunk_count"),
        _rag.get("embeddings_available"),
        _rag.get("last_error") or _rag.get("embedding_error")))
    _lc = data.get("llm_config") or {}
    print("llm_config: grok=%s groq=%s runtime=%s notes=%s" % (
        _lc.get("grok_configured"), _lc.get("groq_configured"),
        _lc.get("selected_runtime"), _lc.get("notes")))
    print("=" * 100)

    questions = [data["question"]["question"]]
    print("\n[TURN 1] Q: %s" % questions[0])
    print("   source=%s skill=%s topic=%s diff=%s llm=%s" % (
        data["question"].get("source"), data["question"].get("skill"),
        data["question"].get("topic"), data["question"].get("difficulty"),
        data["question"].get("llm_generated")))

    scores, evals, lq, le = [], [], [], []
    for i, ans in enumerate(ANSWERS, start=1):
        r = client.post("/api/interview-prep/answer",
                        json={"session_id": sid, "answer": ans})
        if r.status_code != 200:
            print("TURN %d FAILED %s %s" % (i, r.status_code, r.get_data(as_text=True)[:300]))
            break
        d = r.get_json()
        ev = d.get("evaluation") or {}
        nq = d.get("next_question") or {}
        scores.append(ev.get("overall_score"))
        evals.append(ev)
        le.append(d.get("llm_generated_eval"))
        lq.append(d.get("llm_generated_question"))
        print("\n[ANSWER %d] %s" % (i, ans[:110] + ("..." if len(ans) > 110 else "")))
        print("   EVAL score=%s by=%s fallback_reason=%r" % (ev.get("overall_score"), ev.get("evaluated_by"), d.get("eval_fallback_reason")))
        print("   RAG last_hits=%s last_error=%r" % ((d.get("rag") or {}).get("last_hits"), (d.get("rag") or {}).get("last_error")))
        print("        strengths=%s" % ev.get("strengths"))
        print("        weaknesses=%s" % ev.get("weaknesses"))
        print("        missing=%s" % ev.get("missing_topics"))
        print("        reason=%s" % str(ev.get("reason") or ev.get("reasoning"))[:180])
        if nq:
            questions.append(nq.get("question"))
            print("   NEXT Q(turn %s): %s" % (d.get("turn"), nq.get("question")))
            print("        source=%s skill=%s diff=%s follow_up=%s llm=%s fallback_reason=%r" % (
                nq.get("source"), nq.get("skill"), nq.get("difficulty"),
                nq.get("follow_up"), nq.get("llm_generated"), d.get("question_fallback_reason")))
        else:
            print("   (interview completed: %s)" % d.get("status"))

    print("\n" + "=" * 100)
    print("UNIQUE QUESTIONS: %d / %d" % (len(set(questions)), len(questions)))
    print("UNIQUE EVAL TEXTS: %d / %d" % (
        len(set(json.dumps(e.get("strengths")) + json.dumps(e.get("weaknesses")) for e in evals)),
        len(evals)))
    print("SCORES: %s" % scores)
    print("LLM-generated questions: %s" % lq)
    print("LLM-evaluated answers : %s" % le)
    print("=" * 100)

    r = client.post("/api/interview-prep/end", json={"session_id": sid})
    s = (r.get_json() or {}).get("summary", {})
    print("SUMMARY score=%s questions_asked=%s turns=%s difficulty=%s llm_evals=%s" % (
        s.get("overall_score"), s.get("questions_asked"), s.get("turn_count"),
        s.get("difficulty"), s.get("evaluated_by_llm")))
    print("skills_tested=%s" % s.get("required_skills_tested"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
