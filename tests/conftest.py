"""Shared pytest fixtures for the Job Tracker test suite.

Why this file exists
--------------------
The API is now protected: unauthenticated ``/api/*`` requests receive a JSON
401 instead of an HTML login redirect (see
``docs/AUTHENTICATION_AND_PERSISTENCE.md``). Test modules that exercise
protected endpoints therefore need a signed-in session.

This conftest signs a disposable test user into any module that provides a
``client`` fixture (for example ``tests/test_interview_flow.py``), using the
real ``POST /api/auth/signup`` endpoint so the genuine authentication path is
exercised. No existing test module or assertion is modified, and no production
security setting is relaxed.
"""
import os
import uuid

# Must be set before ``app`` is imported. The Flask test client speaks plain
# HTTP, while production marks the session cookie ``Secure`` (HTTPS-only), so
# the test environment runs in debug configuration exactly like local dev.
os.environ["FLASK_DEBUG"] = "1"
os.environ.setdefault("SECRET_KEY", "job-tracker-test-secret")
# Make LLM health checks fail fast during tests (no local runtime dependency).
os.environ.setdefault("LLM_BASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("LLM_TIMEOUT", "1")

import pytest


def signup_test_user(client, tag="test"):
    """Create and sign in a disposable user through the real signup endpoint.

    Returns the credentials used, so the same account can be logged into again.
    """
    suffix = uuid.uuid4().hex[:12]
    credentials = {
        "email": "%s-%s@example.com" % (tag, suffix),
        "username": "%s_%s" % (tag, suffix),
        "password": "TestPass123!",
        "confirm_password": "TestPass123!",
    }
    resp = client.post("/api/auth/signup", json=credentials)
    assert resp.status_code == 200, resp.get_data(as_text=True)[:400]
    payload = resp.get_json()
    assert payload and payload.get("success"), payload
    return credentials


@pytest.fixture(scope="module", autouse=True)
def _sign_in_module_client(request):
    """Sign a test user into a module-provided ``client`` fixture, if any.

    Modules that do not expose a ``client`` fixture are left untouched.
    """
    if "client" not in getattr(request, "fixturenames", []):
        return None
    try:
        client = request.getfixturevalue("client")
    except Exception:  # pragma: no cover - the test module will report its own error
        return None
    if getattr(client, "_job_tracker_signed_in", False):
        return client
    signup_test_user(client, tag="module")
    client._job_tracker_signed_in = True
    return client
