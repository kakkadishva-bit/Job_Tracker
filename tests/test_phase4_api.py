"""
Phase-4 API tests: notification endpoints (read/unread, mark-all,
ownership), Role Guide endpoints and Job Tracker endpoints.

All requests go through the real Flask test client with a real signed-in
session created via POST /api/auth/signup (see tests/conftest.py).
"""
import json
import uuid

import pytest


# ── Helpers ──────────────────────────────────────────────────────────────

def _new_client():
    import app as app_module
    return app_module.app.test_client()


def _authed_client(tag="api4"):
    client = _new_client()
    suffix = uuid.uuid4().hex[:12]
    creds = {
        "email": "%s-%s@example.com" % (tag, suffix),
        "username": "%s_%s" % (tag, suffix),
        "password": "TestPass123!",
        "confirm_password": "TestPass123!",
    }
    resp = client.post("/api/auth/signup", json=creds)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:300]
    return client


def _json(resp):
    ctype = resp.headers.get("Content-Type", "")
    assert "application/json" in ctype, "expected JSON, got %r" % ctype
    return resp.get_json()


def _user_id(client):
    payload = client.get("/api/auth/me").get_json() or {}
    return (payload.get("user") or payload).get("id")


def _seed_notifications(user_id, count=3):
    """Insert real Notification rows directly for the given user."""
    import app as app_module
    from models.user_model import db, Notification
    with app_module.app.app_context():
        for i in range(count):
            db.session.add(Notification(
                user_id=user_id,
                type=["new_job_match", "resume_analysis", "tracker_stale"][i % 3],
                title="Seeded notification %d" % i,
                message="Seeded body %d" % i,
                dedupe_key="seed:%s:%d" % (user_id, i),
            ))
        db.session.commit()


# ─── Notification API ────────────────────────────────────────────────────

def test_notifications_requires_authentication():
    client = _new_client()
    resp = client.get("/api/notifications")
    assert resp.status_code == 401
    assert _json(resp)["success"] is False


def test_notifications_endpoint_returns_list_and_unread_count():
    client = _authed_client("notiflist")
    _seed_notifications(_user_id(client), 3)

    resp = client.get("/api/notifications")
    assert resp.status_code == 200
    body = _json(resp)

    assert "unread_count" in body
    assert isinstance(body.get("notifications"), list)
    assert body["unread_count"] >= 3
    titles = [n["title"] for n in body["notifications"]]
    assert any(t.startswith("Seeded notification") for t in titles)
    # Each row carries everything the UI needs.
    sample = body["notifications"][0]
    for key in ("id", "type", "title", "message", "is_read", "created_at"):
        assert key in sample


def test_mark_single_notification_read():
    client = _authed_client("notifread")
    _seed_notifications(_user_id(client), 1)

    body = _json(client.get("/api/notifications"))
    target = [n for n in body["notifications"] if not n["is_read"]][0]

    resp = client.post("/api/notifications/%d/read" % target["id"])
    assert resp.status_code == 200
    assert _json(resp)["status"] == "ok"

    after = _json(client.get("/api/notifications"))
    entry = [n for n in after["notifications"] if n["id"] == target["id"]][0]
    assert entry["is_read"] is True


def test_mark_all_notifications_read():
    client = _authed_client("notifall")
    _seed_notifications(_user_id(client), 3)
    assert _json(client.get("/api/notifications"))["unread_count"] >= 3

    resp = client.post("/api/notifications/read-all")
    assert resp.status_code == 200
    body = _json(resp)
    assert body["status"] == "ok"
    assert body["marked_count"] >= 3

    after = _json(client.get("/api/notifications"))
    assert after["unread_count"] == 0
    assert all(n["is_read"] for n in after["notifications"])


def test_notifications_are_private_per_user():
    """One user can never read or mutate another user's notifications."""
    owner = _authed_client("notifowner")
    attacker = _authed_client("notifattacker")
    _seed_notifications(_user_id(owner), 2)

    owner_body = _json(owner.get("/api/notifications"))
    target = owner_body["notifications"][0]

    # The attacker's list must not contain the owner's rows.
    attacker_body = _json(attacker.get("/api/notifications"))
    attacker_ids = {n["id"] for n in attacker_body["notifications"]}
    assert target["id"] not in attacker_ids

    # The attacker cannot mark the owner's notification as read (404).
    resp = attacker.post("/api/notifications/%d/read" % target["id"])
    assert resp.status_code == 404
    assert _json(resp)["success"] is False

    # ...and the owner's row is untouched.
    still = _json(owner.get("/api/notifications"))
    entry = [n for n in still["notifications"] if n["id"] == target["id"]][0]
    assert entry["is_read"] is False


# ─── Role Guide ──────────────────────────────────────────────────────────

def test_role_guide_search_succeeds_for_known_role():
    """The exact flow the frontend performs: expand-roles then search."""
    client = _authed_client("role")

    expand = client.post("/api/expand-roles",
                         json={"role": "Frontend Developer"})
    assert expand.status_code == 200
    related = _json(expand)["related_roles"]
    assert related and "Frontend Developer" in related

    resp = client.post("/api/search",
                       json={"query": "Frontend Developer", "roles": related})
    assert resp.status_code == 200
    body = _json(resp)

    for key in ("query", "roles", "primary_guide", "related_guides",
                "location_info", "platform_urls"):
        assert key in body, "missing key %s" % key

    guide = body["primary_guide"]
    assert guide["role_title"] == "Frontend Developer"
    assert guide["guide_available"] is True
    assert guide["overview"]
    assert guide["responsibilities"]
    assert guide["required_skills"]
    assert isinstance(body["related_guides"], list)


def test_role_guide_unknown_role_returns_honest_payload():
    """An unknown role must still return JSON with a clearly-marked guide,
    never an HTML error page (the old "Search failed: Failed" path)."""
    client = _authed_client("roleunk")
    resp = client.post("/api/search", json={"query": "Zorb Flange Polisher"})
    assert resp.status_code == 200
    assert "application/json" in resp.headers.get("Content-Type", "")

    guide = _json(resp)["primary_guide"]
    assert guide["role_title"]
    assert guide["guide_available"] is True
    assert guide["overview"]


def test_role_guide_search_requires_query():
    client = _authed_client("rolebad")
    resp = client.post("/api/search", json={"query": "   "})
    assert resp.status_code == 400
    assert "error" in _json(resp)


def test_role_guide_endpoints_require_authentication():
    anon = _new_client()
    for path, body in (("/api/search", {"query": "Python Developer"}),
                       ("/api/expand-roles", {"role": "Python Developer"})):
        resp = anon.post(path, json=body)
        assert resp.status_code == 401, path
        assert _json(resp)["success"] is False


def test_role_guide_search_is_json_on_bad_body():
    client = _authed_client("rolejson")
    resp = client.post("/api/search", data="{not json",
                       content_type="application/json")
    assert resp.status_code in (400, 500)
    assert not resp.headers.get("Content-Type", "").startswith("text/html")
    assert _json(resp)["success"] is False
# ─── Job Tracker ─────────────────────────────────────────────────────────

def _save_job(client, title="Backend Engineer", company="Acme"):
    return client.post("/api/dashboard/save-job",
                       json={"guide": {"role_title": title, "company": company}})


def test_save_job_persists_and_lists_for_owner():
    client = _authed_client("jobsave")
    resp = _save_job(client, "Backend Engineer")
    assert resp.status_code == 200
    assert _json(resp)["status"] == "ok"

    listed = _json(client.get("/api/jobs/saved"))
    assert listed["success"] is True
    titles = [j["role_title"] for j in listed["jobs"]]
    assert "Backend Engineer" in titles


def test_save_job_is_idempotent_per_title():
    client = _authed_client("jobdupe")
    _save_job(client, "Backend Engineer")
    _save_job(client, "Backend Engineer")

    listed = _json(client.get("/api/jobs/saved"))
    matching = [j for j in listed["jobs"] if j["role_title"] == "Backend Engineer"]
    assert len(matching) == 1, "saving the same role twice must not duplicate"


def test_saved_jobs_are_private_per_user():
    owner = _authed_client("jobowner")
    other = _authed_client("jobother")
    _save_job(owner, "Owner Only Role")

    owner_titles = [j["role_title"]
                    for j in _json(owner.get("/api/jobs/saved"))["jobs"]]
    other_titles = [j["role_title"]
                    for j in _json(other.get("/api/jobs/saved"))["jobs"]]
    assert "Owner Only Role" in owner_titles
    assert "Owner Only Role" not in other_titles


def test_remove_saved_job():
    client = _authed_client("jobremove")
    _save_job(client, "Temp Role")
    resp = client.post("/api/dashboard/remove-job",
                       json={"role_title": "Temp Role"})
    assert resp.status_code == 200
    titles = [j["role_title"] for j in _json(client.get("/api/jobs/saved"))["jobs"]]
    assert "Temp Role" not in titles


def test_update_saved_job_status():
    client = _authed_client("jobstatus")
    _save_job(client, "Status Role")
    job_id = _json(client.get("/api/jobs/saved"))["jobs"][0]["id"]

    resp = client.post("/api/jobs/saved/status",
                       json={"id": job_id, "status": "applied"})
    assert resp.status_code == 200
    assert _json(resp)["status"] == "applied"


def test_update_saved_job_status_rejects_other_users_job():
    owner = _authed_client("statusowner")
    attacker = _authed_client("statusattacker")
    _save_job(owner, "Guarded Role")
    job_id = _json(owner.get("/api/jobs/saved"))["jobs"][0]["id"]

    resp = attacker.post("/api/jobs/saved/status",
                         json={"id": job_id, "status": "offer"})
    assert resp.status_code == 404
    assert _json(resp)["success"] is False


def test_update_saved_job_status_validates_value():
    client = _authed_client("statusbad")
    _save_job(client, "Validation Role")
    job_id = _json(client.get("/api/jobs/saved"))["jobs"][0]["id"]

    resp = client.post("/api/jobs/saved/status",
                       json={"id": job_id, "status": "not-a-status"})
    assert resp.status_code == 400
    assert _json(resp)["success"] is False


def test_application_tracker_ownership_and_status_update():
    owner = _authed_client("appowner")
    attacker = _authed_client("appattacker")

    created = owner.post("/api/applications",
                         json={"company": "Acme", "role": "Backend Engineer"})
    assert created.status_code == 200
    app_id = _json(created)["id"]

    board = _json(owner.get("/api/applications"))["board"]
    assert any(a["id"] == app_id for a in board["applied"])

    updated = owner.patch("/api/applications/%d" % app_id,
                          json={"status": "interview"})
    assert updated.status_code == 200
    assert _json(updated)["current_status"] == "interview"

    stolen = attacker.patch("/api/applications/%d" % app_id,
                            json={"status": "rejected"})
    assert stolen.status_code == 404

    attacker_board = _json(attacker.get("/api/applications"))["board"]
    assert all(a["id"] != app_id
               for group in attacker_board.values() for a in group)


def test_tracker_delete_is_scoped_to_owner():
    owner = _authed_client("delowner")
    attacker = _authed_client("delattacker")
    created = owner.post("/api/applications",
                         json={"company": "Acme", "role": "Backend Engineer"})
    app_id = _json(created)["id"]

    assert attacker.delete("/api/applications/%d" % app_id).status_code == 404
    assert owner.delete("/api/applications/%d" % app_id).status_code == 200


def test_saved_jobs_and_tracker_require_authentication():
    anon = _new_client()
    for path in ("/api/jobs/saved", "/api/applications"):
        resp = anon.get(path)
        assert resp.status_code == 401, path
        assert _json(resp)["success"] is False


# ─── Auth surface used by this phase ─────────────────────────────────────

def test_health_endpoint_is_public():
    anon = _new_client()
    resp = anon.get("/health")
    assert resp.status_code == 200
    assert _json(resp)["status"] == "ok"


def test_login_and_signup_pages_are_public():
    anon = _new_client()
    for path in ("/login", "/signup", "/forgot-password"):
        assert anon.get(path).status_code == 200, path


def test_authenticated_user_is_redirected_away_from_login():
    client = _authed_client("redirect")
    for path in ("/login", "/signup"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/login" not in resp.headers.get("Location", "")


def test_logout_invalidates_session():
    client = _authed_client("logout2")
    assert client.get("/api/auth/check").get_json()["authenticated"] is True

    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/check").get_json()["authenticated"] is False

    # Protected APIs and pages now send the user back to Login.
    api = client.get("/api/notifications")
    assert api.status_code == 401
    page = client.get("/dashboard")
    assert page.status_code == 302
    assert "/login" in page.headers.get("Location", "")