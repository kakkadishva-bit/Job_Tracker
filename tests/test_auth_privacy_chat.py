"""Phase 2 regression tests: authentication, session persistence, privacy-policy
acceptance, community chat and resource ownership (IDOR).

These tests exercise the real endpoints through the Flask test client. No
production security setting is relaxed — ``FLASK_DEBUG=1`` is set only so the
plain-HTTP test client can carry a session cookie that production marks
``Secure`` (HTTPS-only).
"""
import os
import uuid

os.environ["FLASK_DEBUG"] = "1"
os.environ.setdefault("SECRET_KEY", "job-tracker-test-secret")

import pytest


# ─── Helpers ──────────────────────────────────────────────────────────────

def _new_client():
    import app as app_module
    return app_module.app.test_client()


def _creds(tag="user"):
    suffix = uuid.uuid4().hex[:12]
    # Usernames allow only letters, digits and underscores.
    safe_tag = tag.replace("-", "_")
    return {
        "email": "{0}-{1}@example.com".format(tag, suffix),
        "username": "{0}_{1}".format(safe_tag, suffix),
        "password": "TestPass123!",
        "confirm_password": "TestPass123!",
    }


def _signup(client, tag="user"):
    """Create an account through the real signup endpoint (also signs in)."""
    creds = _creds(tag)
    resp = client.post("/api/auth/signup", json=creds)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:400]
    return creds


def _authed_client(tag="user", accept_policy=False):
    client = _new_client()
    _signup(client, tag)
    if accept_policy:
        resp = client.post("/api/chat/accept-policy", json={})
        assert resp.status_code == 200, resp.get_data(as_text=True)[:400]
    return client


def _json(resp):
    """Assert the response really is JSON (never HTML) and return the payload."""
    ctype = resp.headers.get("Content-Type", "")
    assert "application/json" in ctype, "expected JSON, got {0!r}".format(ctype)
    return resp.get_json()


def _user_id(client):
    payload = client.get("/api/auth/me").get_json() or {}
    return (payload.get("user") or payload).get("id")


@pytest.fixture()
def anon_client():
    return _new_client()


# ─── AUTH: signup / login / logout ────────────────────────────────────────

def test_signup_creates_account_and_returns_json(anon_client):
    creds = _creds("signup")
    resp = anon_client.post("/api/auth/signup", json=creds)
    assert resp.status_code == 200
    payload = _json(resp)
    assert payload["success"] is True
    assert payload["user"]["email"] == creds["email"]
    # Password material must never be echoed back
    assert "password" not in payload["user"]
    assert "password_hash" not in payload["user"]


def test_signup_rejects_unmatched_passwords(anon_client):
    creds = _creds("mismatch")
    creds["confirm_password"] = "DifferentPass123!"
    resp = anon_client.post("/api/auth/signup", json=creds)
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_signup_rejects_weak_password(anon_client):
    creds = _creds("weak")
    creds["password"] = creds["confirm_password"] = "abc"
    resp = anon_client.post("/api/auth/signup", json=creds)
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_signup_rejects_duplicate_email(anon_client):
    creds = _creds("dupe")
    assert anon_client.post("/api/auth/signup", json=creds).status_code == 200
    again = _creds("other")
    again["email"] = creds["email"]
    resp = anon_client.post("/api/auth/signup", json=again)
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_login_succeeds_with_correct_credentials():
    client = _new_client()
    creds = _signup(client, "login")
    fresh = _new_client()
    resp = fresh.post("/api/auth/login", json={
        "email": creds["email"], "password": creds["password"], "remember": True})
    assert resp.status_code == 200
    assert _json(resp)["success"] is True


def test_login_rejects_wrong_password(anon_client):
    creds = _creds("badpw")
    assert anon_client.post("/api/auth/signup", json=creds).status_code == 200
    fresh = _new_client()
    resp = fresh.post("/api/auth/login", json={
        "email": creds["email"], "password": "WrongPass123!"})
    assert resp.status_code == 401
    assert _json(resp)["success"] is False


def test_login_requires_both_fields(anon_client):
    resp = anon_client.post("/api/auth/login", json={"email": "", "password": ""})
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_logout_clears_session(anon_client):
    _signup(anon_client, "logout")
    assert anon_client.get("/api/auth/check").get_json()["authenticated"] is True
    assert anon_client.post("/api/auth/logout").status_code == 200
    assert anon_client.get("/api/auth/check").get_json()["authenticated"] is False
    resp = anon_client.get("/api/auth/me")
    assert resp.status_code == 401
    assert _json(resp)["success"] is False
    assert resp.status_code == 401
    assert _json(resp)["success"] is False


# ─── Login must be the first page + protected routes ──────────────────────

@pytest.mark.parametrize("path", [
    "/", "/dashboard", "/search", "/interview", "/community",
    "/role-guide", "/career-insights", "/resume", "/jobs",
])
def test_unauthenticated_page_redirects_to_login(anon_client, path):
    resp = anon_client.get(path)
    assert resp.status_code == 302
    assert "/login" in resp.headers.get("Location", "")


@pytest.mark.parametrize("path", ["/login", "/signup", "/forgot-password"])
def test_login_pages_reachable_when_anonymous(anon_client, path):
    assert anon_client.get(path).status_code == 200


@pytest.mark.parametrize("path", ["/login", "/signup"])
def test_authenticated_user_is_redirected_into_app(path):
    client = _authed_client("authedpage")
    resp = client.get(path)
    assert resp.status_code == 302
    assert "/login" not in resp.headers.get("Location", "")


def test_authenticated_user_can_load_app_shell():
    client = _authed_client("shell")
    assert client.get("/").status_code == 200
    assert client.get("/dashboard").status_code == 200


# ─── API 401 must be JSON, never an HTML redirect ─────────────────────────

@pytest.mark.parametrize("method,path", [
    ("get", "/api/auth/me"),
    ("get", "/api/chat/messages"),
    ("get", "/api/chat/policy"),
    ("post", "/api/chat/send"),
    ("post", "/api/chat/accept-policy"),
    ("post", "/api/interview-prep/start"),
    ("post", "/api/interview-prep/answer"),
    ("post", "/api/interview-prep/end"),
])
def test_unauthenticated_api_returns_json_401(anon_client, method, path):
    resp = getattr(anon_client, method)(path, json={})
    assert resp.status_code == 401, path
    payload = _json(resp)          # asserts application/json, not text/html
    assert payload["success"] is False
    assert not resp.get_data(as_text=True).lstrip().startswith("<")


def test_public_endpoints_do_not_require_auth(anon_client):
    assert anon_client.get("/health").status_code == 200
    assert anon_client.get("/api/auth/check").get_json()["authenticated"] is False


# ─── API error handling: always JSON on /api/* ────────────────────────────

def test_unknown_api_route_returns_json_404():
    client = _authed_client("notfound")
    resp = client.get("/api/definitely-not-a-route")
    assert resp.status_code == 404
    assert _json(resp)["success"] is False


def test_unknown_api_route_is_json_even_when_anonymous(anon_client):
    """Even the 401 gate must answer with JSON, never an HTML page."""
    resp = anon_client.get("/api/definitely-not-a-route")
    assert resp.status_code == 401
    assert _json(resp)["success"] is False


def test_wrong_method_on_api_returns_json():
    client = _authed_client("badmethod")
    resp = client.post("/api/chat/policy", json={})   # GET-only endpoint
    assert resp.status_code in (404, 405), resp.status_code
    assert _json(resp)["success"] is False


def test_malformed_json_body_does_not_return_html():
    client = _authed_client("malformed", accept_policy=True)
    resp = client.post("/api/chat/send", data="{not json",
                       content_type="application/json")
    assert resp.status_code in (400, 500), resp.status_code
    assert not resp.headers.get("Content-Type", "").startswith("text/html")
    assert _json(resp)["success"] is False
# ─── Session persistence ──────────────────────────────────────────────────

def test_session_persists_across_requests():
    client = _authed_client("session")
    for _ in range(5):
        assert client.get("/api/auth/check").get_json()["authenticated"] is True
    assert _user_id(client) is not None


def test_session_cookie_is_valid_for_a_different_client_instance():
    """A cookie signed by one worker must validate on another worker.

    Regression guard for the per-process random SECRET_KEY that logged users
    out on most requests under Gunicorn's multiple workers.
    """
    import app as app_module

    client = _authed_client("sharedkey")
    cookie = client.get_cookie("session")
    assert cookie is not None and cookie.value

    other_worker = _new_client()
    other_worker.set_cookie("session", cookie.value)
    assert other_worker.get("/api/auth/check").get_json()["authenticated"] is True

    # The signing key comes from the environment, not from randomness.
    assert app_module.app.secret_key == os.environ["SECRET_KEY"]
    assert len(str(app_module.app.secret_key)) >= 16


def test_session_survives_navigation_across_many_endpoints():
    client = _authed_client("navigate", accept_policy=True)
    assert client.get("/dashboard").status_code == 200
    assert client.get("/api/chat/policy").status_code == 200
    assert client.get("/community").status_code == 200
    assert client.get("/api/auth/check").get_json()["authenticated"] is True


# ─── Privacy policy acceptance ────────────────────────────────────────────

def test_policy_not_accepted_initially():
    client = _authed_client("policy-new")
    payload = client.get("/api/chat/policy").get_json()
    assert payload["has_accepted"] is False
    assert payload["policy"]


def test_accept_policy_returns_json_success():
    client = _authed_client("policy-ok")
    resp = client.post("/api/chat/accept-policy", json={})
    assert resp.status_code == 200
    payload = _json(resp)
    assert payload["success"] is True
    assert payload["accepted"] is True
    assert client.get("/api/chat/policy").get_json()["has_accepted"] is True


def test_accept_policy_is_idempotent_and_does_not_duplicate_join_message():
    client = _authed_client("policy-idem")

    assert _json(client.post("/api/chat/accept-policy", json={}))["accepted"] is True
    first = client.get("/api/chat/messages").get_json()["messages"]
    system_first = [m for m in first if m["message_type"] == "system"]

    for _ in range(4):
        resp = client.post("/api/chat/accept-policy", json={})
        assert resp.status_code == 200
        body = _json(resp)
        assert body["success"] is True and body["accepted"] is True

    after = client.get("/api/chat/messages").get_json()["messages"]
    system_after = [m for m in after if m["message_type"] == "system"]
    assert len(system_after) == len(system_first), \
        "repeated acceptance must not insert duplicate join messages"


def test_accept_policy_requires_authentication(anon_client):
    resp = anon_client.post("/api/chat/accept-policy", json={})
    assert resp.status_code == 401
    assert _json(resp)["success"] is False


def test_accept_policy_only_affects_the_calling_user():
    user_a = _authed_client("policy-a", accept_policy=True)
    user_b = _authed_client("policy-b")
    assert user_a.get("/api/chat/policy").get_json()["has_accepted"] is True
    assert user_b.get("/api/chat/policy").get_json()["has_accepted"] is False


# ─── Community chat ───────────────────────────────────────────────────────

def test_chat_send_requires_policy_acceptance():
    client = _authed_client("chat-nopolicy")
    resp = client.post("/api/chat/send", json={"message": "hello"})
    assert resp.status_code == 403
    assert _json(resp)["success"] is False


def test_chat_allows_many_messages_and_persists_them():
    client = _authed_client("chat-many", accept_policy=True)

    sent = []
    for i in range(6):
        text = "sequential message number {0} {1}".format(i, uuid.uuid4().hex[:6])
        resp = client.post("/api/chat/send", json={"message": text})
        assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
        payload = _json(resp)
        assert payload["success"] is True
        assert payload["message_obj"]["message"] == text
        sent.append(text)

    payload = client.get("/api/chat/messages?limit=200").get_json()
    assert payload["success"] is True
    bodies = [m["message"] for m in payload["messages"]]
    for text in sent:
        assert text in bodies, "message not persisted: {0}".format(text)
    ids = [m["id"] for m in payload["messages"] if m["message"] in sent]
    assert ids == sorted(ids), "messages must be chronological"


def test_chat_rejects_empty_message():
    client = _authed_client("chat-empty", accept_policy=True)
    resp = client.post("/api/chat/send", json={"message": "   "})
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_chat_rejects_overlong_message():
    client = _authed_client("chat-long", accept_policy=True)
    resp = client.post("/api/chat/send", json={"message": "x" * 1001})
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_chat_accepts_boundary_length_message():
    client = _authed_client("chat-boundary", accept_policy=True)
    resp = client.post("/api/chat/send", json={"message": "y" * 1000})
    assert resp.status_code == 200
    assert _json(resp)["success"] is True


def test_chat_messages_require_authentication(anon_client):
    assert anon_client.get("/api/chat/messages").status_code == 401
    assert anon_client.post("/api/chat/send", json={"message": "hi"}).status_code == 401


def test_chat_does_not_trust_client_supplied_user_id():
    """A spoofed user_id in the body must be ignored (no message forgery)."""
    owner = _authed_client("chat-owner", accept_policy=True)
    attacker = _authed_client("chat-attacker", accept_policy=True)
    owner_id = _user_id(owner)
    attacker_id = _user_id(attacker)
    assert owner_id != attacker_id

    text = "spoof attempt {0}".format(uuid.uuid4().hex[:8])
    resp = attacker.post("/api/chat/send", json={"message": text, "user_id": owner_id})
    assert resp.status_code == 200
    stored = _json(resp)["message_obj"]
    assert stored["user_id"] == attacker_id, "client-supplied user_id must be ignored"


# ─── Resource ownership / IDOR ────────────────────────────────────────────

def _start_interview(client):
    payload = {
        "role": "Python Developer",
        "company": "Acme",
        "experience_level": "mid",
        "interview_mode": "standard",
        "resume_context": {"text": "SKILLS: Python, FastAPI, Docker, SQL."},
        "job_context": {"title": "Backend Engineer"},
        "required_skills": ["Python"],
        "preferred_skills": [],
    }
    resp = client.post("/api/interview-prep/start", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    return _json(resp)["session_id"]


def test_interview_session_cannot_be_used_by_another_user():
    owner = _authed_client("interview-owner")
    attacker = _authed_client("interview-attacker")
    session_id = _start_interview(owner)

    resp = attacker.post("/api/interview-prep/answer",
                         json={"session_id": session_id, "answer": "I would use Python."})
    assert resp.status_code == 404, resp.get_data(as_text=True)[:300]
    assert _json(resp)["success"] is False

    resp = attacker.post("/api/interview-prep/end", json={"session_id": session_id})
    assert resp.status_code == 404
    assert _json(resp)["success"] is False

    # The real owner is unaffected.
    assert owner.post("/api/interview-prep/end",
                      json={"session_id": session_id}).status_code == 200


def test_interview_start_ignores_client_supplied_user_id():
    """Ownership is taken from the session, never from the request body."""
    import app as app_module

    owner = _authed_client("interview-idor")
    victim = _authed_client("interview-victim")
    victim_id = _user_id(victim)

    payload = {
        "role": "Python Developer",
        "user_id": victim_id,               # spoofed
        "resume_context": {"text": "SKILLS: Python."},
        "job_context": {"title": "Backend Engineer"},
    }
    resp = owner.post("/api/interview-prep/start", json=payload)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    session_id = _json(resp)["session_id"]

    record = app_module.interview_sessions[session_id]
    assert record["user_id"] != victim_id, "client-supplied user_id must be ignored"
    assert record["user_id"] == _user_id(owner)

    # The real starter still owns the session.
    assert owner.post("/api/interview-prep/end",
                      json={"session_id": session_id}).status_code == 200