"""Interview system end-to-end tests (adaptive flow via the Flask test client)."""
import os

os.environ.setdefault("SECRET_KEY", "interview-test-secret")
# Make LLM health checks fail fast during tests (no dependency on a local runtime).
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("LLM_TIMEOUT", "1")

import pytest


@pytest.fixture(scope="module")
def client():
    import app as app_module
    return app_module.app.test_client()


RESUME = """Alex Rivera
Software Engineer with 5 years experience building Python backends.
SKILLS: Python, FastAPI, Docker, SQL, AWS, Machine Learning, RAG.
EXPERIENCE
Senior Backend Engineer, BlueCorp (2021 - Present)
- Built a RAG chatbot in Python with FastAPI and vector search.
- Containerized microservices with Docker and deployed on AWS with CI/CD.
- Optimized SQL queries, cutting report generation time by 70%.
EDUCATION
B.S. Computer Science, University of Michigan, 2018
"""

JD = """Backend Engineer (Python)
We are looking for a Python developer with strong FastAPI, Docker and SQL skills.
Experience with AWS, CI/CD and machine learning is a plus.
Required: Python, FastAPI, Docker, SQL, REST API.
"""


def _start_payload():
    return {
        "role": "Python Developer",
        "company": "Acme",
        "experience_level": "mid",
        "interview_mode": "standard",
        "resume_context": {"text": RESUME},
        "job_context": {"title": "Backend Engineer", "description": JD, "analyzed": True},
        "required_skills": ["Python", "FastAPI"],
        "preferred_skills": ["AWS"],
    }


def test_start_returns_nonempty_question(client):
    r = client.post("/api/interview-prep/start", json=_start_payload())
    assert r.status_code == 200, r.get_data(as_text=True)[:500]
    data = r.get_json()
    assert data.get("question"), data
    q = data["question"]
    assert isinstance(q, dict) and q.get("question"), q
    assert q["question"].strip()
    assert data.get("session_id")


def test_answer_evaluates_and_produces_next_adaptive_question(client):
    r = client.post("/api/interview-prep/start", json=_start_payload())
    data = r.get_json()
    sid = data["session_id"]
    seen = {data["question"]["question"].lower()}

    answers = [
        "I built a RAG chatbot with Python and FastAPI using vector embeddings, deployed in "
        "Docker on AWS with a CI/CD pipeline. It cut support response time by 60%.",
        "For SQL I design indexes and optimize slow queries; I reduced a daily report from "
        "4 minutes to 40 seconds using query plans and covering indexes.",
    ]
    for ans in answers:
        r = client.post("/api/interview-prep/answer", json={"session_id": sid, "answer": ans})
        assert r.status_code == 200, r.get_data(as_text=True)[:500]
        d = r.get_json()
        ev = d.get("evaluation") or {}
        assert isinstance(ev.get("overall_score"), (int, float)), d
        assert "correctness" in ev and "depth" in ev and "clarity" in ev
        nq = d.get("next_question")
        assert nq and nq.get("question") and nq["question"].strip(), d
        assert nq["question"].lower() not in seen, "duplicate/empty question" + str(nq)
        seen.add(nq["question"].lower())


def test_end_returns_report_with_recommendations(client):
    r = client.post("/api/interview-prep/start", json=_start_payload())
    data = r.get_json()
    sid = data["session_id"]
    client.post("/api/interview-prep/answer", json={
        "session_id": sid,
        "answer": "I built a RAG chatbot with Python and FastAPI using vector embeddings, "
                  "deployed in Docker on AWS with a CI/CD pipeline. It cut support response time by 60%.",
    })
    r = client.post("/api/interview-prep/end", json={"session_id": sid})
    assert r.status_code == 200, r.get_data(as_text=True)[:500]
    summary = r.get_json().get("summary") or {}
    assert summary.get("overall_score") is not None
    assert summary.get("recommendations") or summary.get("preparation_recommendations")
    assert "strong_areas" in summary and "weak_areas" in summary


def test_missing_answer_rejected(client):
    r = client.post("/api/interview-prep/start", json=_start_payload())
    sid = r.get_json()["session_id"]
    r = client.post("/api/interview-prep/answer", json={"session_id": sid, "answer": "   "})
    assert r.status_code == 400


def test_invalid_session_rejected(client):
    r = client.post("/api/interview-prep/answer", json={"session_id": "nope", "answer": "hi"})
    assert r.status_code == 400