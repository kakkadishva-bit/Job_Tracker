"""Phase timing diagnostic for the adaptive interview stack."""
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
os.environ.setdefault("SECRET_KEY", "diag")
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("LLM_TIMEOUT", "1")

t0 = time.time()
import app as app_module  # noqa: E402
print("import app                 : %6.2fs" % (time.time() - t0))

t0 = time.time()
llm = app_module.get_llm_provider()
print("get_llm_provider           : %6.2fs  %s model=%s base_url=%s" % (
    time.time() - t0, type(llm).__name__, getattr(llm, "model", "?"),
    getattr(llm, "base_url", "?")))

t0 = time.time()
out = llm.generate_json('Return {"ok": true}')
print("llm.generate_json          : %6.2fs  -> %r" % (time.time() - t0, out))

try:
    from services.rag.rag_pipeline import get_rag
    t0 = time.time()
    rag = get_rag()
    print("get_rag                    : %6.2fs  -> %s" % (time.time() - t0, type(rag).__name__))
    if rag:
        t0 = time.time()
        res = rag.retrieve("python fastapi docker machine learning", top_k=3)
        print("rag.retrieve (1st)         : %6.2fs  -> %d hits" % (time.time() - t0, len(res or [])))
        t0 = time.time()
        rag.retrieve("python fastapi docker machine learning", top_k=3)
        print("rag.retrieve (2nd)         : %6.2fs" % (time.time() - t0))
except Exception as e:
    print("get_rag failed: %s" % e)

RESUME = ("Alex Rivera\nSoftware Engineer with 5 years experience building Python backends.\n"
          "SKILLS: Python, FastAPI, Docker, SQL, AWS, Machine Learning, RAG.\n"
          "EXPERIENCE\nSenior Backend Engineer, BlueCorp (2021 - Present)\n"
          "- Built a RAG chatbot in Python with FastAPI and vector search.\n")
JD = ("Backend Engineer (Python)\nWe need Python with strong FastAPI, Docker and SQL skills.\n"
      "Required: Python, FastAPI, Docker, SQL, REST API.\n")

client = app_module.app.test_client()
payload = {
    "role": "Python Developer",
    "company": "Acme",
    "resume_context": {"text": RESUME},
    "job_context": {"title": "Backend Engineer", "description": JD, "analyzed": True},
    "required_skills": ["Python", "FastAPI"],
    "preferred_skills": ["AWS"],
}

t0 = time.time()
r = client.post("/api/interview-prep/start", json=payload)
d = r.get_json()
print("POST /start                : %6.2fs  status=%s" % (time.time() - t0, r.status_code))
sid = d["session_id"]

t0 = time.time()
r = client.post("/api/interview-prep/answer", json={
    "session_id": sid,
    "answer": ("I built a RAG chatbot with Python and FastAPI using vector embeddings, deployed in "
               "Docker on AWS with a CI/CD pipeline. It cut support response time by 60%.")})
d2 = r.get_json()
print("POST /answer               : %6.2fs  status=%s" % (time.time() - t0, r.status_code))
print("eval_by=%s llm_eval=%s llm_q=%s" % (
    (d2.get("evaluation") or {}).get("evaluated_by"),
    d2.get("llm_generated_eval"), d2.get("llm_generated_question")))
