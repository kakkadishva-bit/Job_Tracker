# Job Tracker — Authentication & Persistence Reference

Reference for the Phase 2 authentication / session / database hardening.
Applies to the Flask backend (`app.py`), the auth helpers (`utils/auth.py`) and
the user models (`models/user_model.py`).

---

## 1. Authentication model

- **Login/signup is the first page.** `/` and every SPA deep link
  (`/dashboard`, `/search`, `/interview`, `/community`, `/role-guide`,
  `/career-insights`, ...) is served by the fallback route `spa_fallback` in
  `app.py`, which redirects unauthenticated visitors to `/login`.
- Signed-in users visiting `/login`, `/signup`, `/forgot-password` or
  `/reset-password/<token>` are redirected straight into the application.
- Passwords are hashed with Werkzeug (`generate_password_hash` /
  `check_password_hash` in `models/user_model.py`). **Plaintext passwords are
  never stored**, and the existing hashing system is reused — no second user
  system was introduced.
- `/api/auth/logout` clears both the Flask session and the remember cookie.

## 2. API authentication gate (JSON, never HTML)

`app.py` installs a single `before_request` hook, `_require_api_auth`:

- Every `/api/*` request requires an authenticated user **except** the public
  endpoints in `PUBLIC_API_PATHS`:
  `/api/auth/login`, `/api/auth/signup`, `/api/auth/check`,
  `/api/auth/forgot-password`, `/api/auth/reset-password`.
- `OPTIONS` requests always pass through (CORS preflight).
- Unauthenticated API calls receive **JSON 401**:

  ```json
  { "success": false, "error": "Authentication required" }
  ```

  — **never** an HTML login redirect. `@login_manager.unauthorized_handler`
  enforces the same rule for `@login_required` routes.
- `404`, `405` and unhandled `500` responses on `/api/*` are also JSON, so the
  frontend never receives HTML where it expects JSON. This HTML-instead-of-JSON
  behaviour was the root cause of the `Unexpected token '<'` errors in the
  community chat and the privacy-policy screen.
- `/health` stays public for the Docker/Render health check.

The frontend `apiCall()` helper (`static/js/app.js`) now checks the HTTP status
and the `Content-Type` header before parsing: JSON responses are parsed as JSON,
and HTML/network/server failures produce a readable message instead of a JSON
parse error.

## 3. Session configuration

| Setting | Value | Why |
|---|---|---|
| `SECRET_KEY` | **required env var** | signs the session cookie |
| `SESSION_COOKIE_HTTPONLY` | `True` | JavaScript cannot read the cookie |
| `SESSION_COOKIE_SAMESITE` | `Lax` | mitigates cross-site POST CSRF |
| `SESSION_COOKIE_SECURE` | `True` unless `FLASK_DEBUG=1` | HTTPS-only cookie in production |
| `PERMANENT_SESSION_LIFETIME` | 30 days | session lifetime |
| `REMEMBER_COOKIE_DURATION` | 30 days | "remember me" lifetime |
| `REMEMBER_COOKIE_HTTPONLY` / `SAMESITE` / `SECURE` | `True` / `Lax` / secure | same hardening |

Authenticated state therefore survives page refreshes, navigation between
pages and normal browser reopening for the configured lifetime (30 days when the
user ticked "remember me"). Cross-browser-restart persistence **without**
"remember me" is intentionally not guaranteed — that is the documented Flask
session-cookie behaviour, and it is not a defect.

### Why `SECRET_KEY` is required

The application previously fell back to a **randomly generated key per process**.
Under Gunicorn with multiple workers, every worker had a *different* signing
key, so a session cookie created by worker A failed validation on workers B/C/D.
Users were logged out on roughly three out of four requests, and every restart
invalidated all sessions.

`app.py` now refuses to start when `SECRET_KEY` is missing, with an actionable
error message. Generate a stable value once:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Set it as `SECRET_KEY` in the environment — locally in `.env` (gitignored) and in
Render's environment settings. **It is never hard-coded and never committed.**

---

## 4. Database location & persistence

Resolution order in `app.py`:

1. `DATABASE_URL` — full SQLAlchemy URL (e.g. PostgreSQL). Takes precedence.
2. `DATABASE_PATH` — an explicit SQLite file path.
3. Default: `<project>/instance/jobagent.db` (`INSTANCE_DIR` overrides the
   directory that holds it).

The instance directory is created at startup if it is missing, and startup runs
`db.create_all()` inside `app.app_context()`. `create_all()` only creates
*missing* tables — **it never drops, recreates or deletes existing tables, users
or data**, so initialization is idempotent and safe to run on every boot.

## 5. Render limitation (read this before expecting persistent logins)

Render's filesystem is **ephemeral** on web services unless a persistent disk is
attached. There is **no persistent storage by default**, therefore:

- SQLite data (user accounts, saved jobs, chat history, interview records) is
  **deleted on every deploy and every restart**.
- This is **not** a code bug and **not** a data-deleting startup routine — the
  container filesystem itself is replaced by the platform.

**SQLite on Render is temporary.** To keep data you must do one of:

1. **Attach a persistent disk** and set
   `DATABASE_PATH=/var/data/jobagent.db` (a path on the mounted disk).
2. **Use a managed database** and set `DATABASE_URL` to PostgreSQL
   (Render PostgreSQL, Neon, Supabase, ...). Recommended for multi-worker
   deployments, since SQLite is not designed for concurrent writers.

Until one of these is configured, accounts will disappear after each deploy.
This document deliberately does **not** claim SQLite data is persistent on
Render.

### Local development

Locally, SQLite lives at `instance/jobagent.db` and persists across restarts.
The file is gitignored and must never be committed.

## 6. Privacy policy acceptance (community chat)

- Endpoint: `POST /api/chat/accept-policy` (`@login_required`).
- Request body may be empty; no user identifier is accepted from the client —
  the authenticated user is taken from the session.
- Success response (JSON, HTTP 200):

  ```json
  { "success": true, "accepted": true,
    "message": "Policy accepted. Welcome to the community chat!" }
  ```

- **Idempotent.** Accepting a second (or hundredth) time returns
  `{"success": true, "accepted": true, "message": "Policy already accepted."}`
  **without** inserting another welcome message. Previously each call inserted a
  duplicate "🎉 ... has joined the community chat!" system message.
- Banned users receive **403** with their ban reason.
- Unauthenticated callers receive **JSON 401** (see section 2), so the frontend
  shows the real error instead of `Unexpected token '<'`.
- The frontend (`static/js/app.js` → `acceptChatPolicy`) sends the request
  through `apiCall()`, which parses JSON only when the response actually is
  JSON, then closes the policy screen and opens the chat interface.

## 7. Resource ownership (IDOR protection)

- Interview sessions record the owner at creation time from the **server-side**
  session (`current_user.id`); a client-supplied `user_id` is never trusted.
- `/api/interview-prep/answer` and `/api/interview-prep/end` verify
  `session.user_id == current_user.id` and return **404** for another user's
  session, so session IDs cannot be enumerated or hijacked.
- Chat messages are always stored against `current_user.id`; message ownership
  cannot be spoofed by the request body.
- All user-specific `/api/*` routes sit behind the global gate (section 2), so
  no user-scoped API is publicly reachable.

## 8. Render environment variables

| Variable | Required | Notes |
|---|---|---|
| `SECRET_KEY` | **Yes** | App fails to start without it. `python -c "import secrets; print(secrets.token_hex(32))"` |
| `GROQ_API_KEY` | Yes (interview feature) | Powers interview questions/evaluation. Never exposed to the frontend. |
| `FRONTEND_URL` | No | CORS allowlist origin. Leave unset only for local dev. |
| `DATABASE_URL` | Recommended | Managed database URL. Takes precedence over SQLite. |
| `DATABASE_PATH` | If using a persistent disk | e.g. `/var/data/jobagent.db` |
| `FLASK_DEBUG` | No | Keep `0`/unset in production (keeps cookies HTTPS-only). |
| `FIRECRAWL_API_KEY` | No | Only for Wellfound scraping. |

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Container exits at boot with "SECRET_KEY environment variable is not set" | Missing env var | Set `SECRET_KEY` on the host |
| Logged out every few requests | Multiple workers with different keys | Set a single stable `SECRET_KEY` (done) |
| Accounts vanish after each deploy | Render ephemeral filesystem | Attach a persistent disk + `DATABASE_PATH`, or use `DATABASE_URL` |
| `Unexpected token '<'` in the UI | API returned HTML (redirect/error page) | Should no longer occur; check the endpoint returns JSON |
| `Please sign in to continue.` toast | Expired/absent session | Sign in again; verify `SECRET_KEY` is stable |

## 10. Tests

Authentication, session, privacy, chat and ownership behaviour is covered by
`tests/test_auth_privacy_chat.py`. Because the protected API now requires a
signed-in user, `tests/conftest.py` signs a disposable user into test modules
that expose a `client` fixture (for example `tests/test_interview_flow.py`).
No existing test module or assertion is modified, and no production security
setting is relaxed — only the test environment sets `FLASK_DEBUG=1` so the
plain-HTTP Flask test client can carry a session cookie that production marks
`Secure` (HTTPS-only).