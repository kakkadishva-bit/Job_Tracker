# -*- coding: utf-8 -*-
"""TEMP: focused Groq interview smoke test via the real endpoints. (delete after use)"""
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
load_dotenv()

from app import app

c = app.test_client()
RESUME = ("JANE DOE - ML Engineer, 3 years. Built a RAG chatbot with FAISS "
          "IndexFlatIP over 384-dim MiniLM embeddings, 512-token chunks, top-5 "
          "cross-encoder rerank; Recall@5 0.61 to 0.84. FastAPI service, "
          "multi-stage Docker, Redis p95 900ms to 120ms. SKILLS: Python, "
          "Machine Learning, RAG, FAISS, FastAPI, Docker, SQL")
JD = "Senior ML Engineer. Required: Python, Machine Learning, RAG, FastAPI, Docker."

r = c.post("/api/interview-prep/start", json={
    "role": "Senior Machine Learning Engineer",
    "interview_mode": "quick",
    "job_context": {"title": "Senior ML Engineer", "description": JD, "analyzed": True},
    "required_skills": ["Python", "Machine Learning", "RAG", "FastAPI", "Docker"],
    "resume_context": {"text": RESUME},
})
assert r.status_code == 200, r.get_data(as_text=True)[:400]
d = r.get_json()
sid = d["session_id"]
questions = [d["question"]["question"]]
q_meta = [{"llm": d.get("llm_generated_question"),
           "src": (d.get("question") or {}).get("source", ""),
           "fb": d.get("question_fallback_reason")}]
print("[SMOKE] START provider=%s model=%s | Q1 llm=%s src=%r fallback=%r rag=%s"
      % (d.get("llm", {}).get("runtime"), d.get("llm", {}).get("model"),
         d.get("llm_generated_question"),
         (d.get("question") or {}).get("source", ""),
         d.get("question_fallback_reason"), d.get("rag_used")))
print("[SMOKE] Q1: %s" % questions[0])

answers = [
    "I built a RAG chatbot with FAISS IndexFlatIP over 384-dim MiniLM embeddings, "
    "512-token chunks with 64-token overlap, top-5 retrieval and a cross-encoder "
    "reranker; Recall@5 improved from 0.61 to 0.84.",
    "I containerized the service with a multi-stage Dockerfile, ran uvicorn with 4 "
    "workers behind nginx, pinned the base image digest and set resource limits; "
    "image size went from 1.4GB to 380MB.",
    "I don't know.",
    "FastAPI is good. I used it. It handles requests and returns JSON.",
    "Overfitting means the model memorizes training data. I use L2 regularization "
    "with lambda tuned by cross-validation, early stopping on a validation split, "
    "and monitor the train/val gap; val F1 went from 0.72 to 0.89 on my last model.",
]
evals, fu = [], []
for i, ans in enumerate(answers, 1):
    t0 = time.time()
    r = c.post("/api/interview-prep/answer", json={"session_id": sid, "answer": ans})
    assert r.status_code == 200, (i, r.status_code, r.get_data(as_text=True)[:300])
    d = r.get_json()
    ev = d.get("evaluation") or {}
    nq = d.get("next_question") or {}
    evals.append(ev)
    fu.append(bool(d.get("follow_up")))
    if nq.get("question"):
        questions.append(nq["question"])
        q_meta.append({"llm": nq.get("llm_generated"), "src": nq.get("source", ""),
                       "fb": d.get("question_fallback_reason")})
    print("\n[SMOKE] turn=%d (%.1fs) answer=%r" % (i, time.time() - t0, ans[:55]))
    print("  provider=%s model=%s question_llm=%s evaluation_llm=%s"
          % (d.get("llm", {}).get("runtime"), d.get("llm", {}).get("model"),
             bool(nq.get("llm_generated")) if nq else None,
             ev.get("evaluated_by") == "llm"))
    print("  eval score=%s strengths=%s" % (ev.get("overall_score"),
                                            str(ev.get("strengths"))[:90]))
    print("  weaknesses=%s" % str(ev.get("weaknesses"))[:90])
    print("  follow_up=%s rag_used=%s" % (d.get("follow_up"), d.get("rag_used")))
    if nq:
        print("  next question (%s): %s" % (nq.get("source"), str(nq.get("question"))[:105]))

def norm(q):
    return re.sub(r"\W+", " ", str(q).lower()).strip()

print("\n===== SMOKE VERIFICATION =====")
print("turns evaluated                 :", len(evals))
print("1) start -> Groq question       :", q_meta[0]["llm"] is True, "| src:", q_meta[0]["src"],
      "| fallback:", q_meta[0]["fb"])
print("2) answers -> Groq evaluation   :",
      all(e.get("evaluated_by") == "llm" for e in evals),
      "| by:", [e.get("evaluated_by") for e in evals])
scores = [e.get("overall_score") for e in evals]
print("   answer-specific feedback ok  :",
      all((e.get("strengths") or e.get("weaknesses")) for e in evals))
print("3) context used (resume+JD+RAG+history+prev answer+prev eval):")
print("   rag_used flags               :", None, "| follow-ups:", fu)
print("   next questions reference earlier context:")
for i in range(1, len(questions)):
    print("     Q%d: %s" % (i + 1, questions[i][:110]))
print("4) 5 different answers -> different evals: scores =", scores,
      "| all different:", len(set(scores)) == len(scores))
print("   -> different next questions :",
      len(set(norm(q) for q in questions)) == len(questions), "| asked:", len(questions))
print("5) no static fallback when Groq succeeds:",
      all(m["llm"] is True and not m["fb"] for m in q_meta),
      "| sources:", [m["src"] for m in q_meta])
r = c.post("/api/interview-prep/end", json={"session_id": sid})
print("END:", r.status_code, "| overall:",
      (r.get_json() or {}).get("summary", {}).get("overall_score"))
