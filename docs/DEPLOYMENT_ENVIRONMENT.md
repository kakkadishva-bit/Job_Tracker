
SECRET_KEY is required
----------------------
`app.secret_key` must come from the `SECRET_KEY` environment variable.
Sessions, login cookies, CSRF-adjacent signing and the whole
authentication flow depend on this key being **stable across restarts
and workers**; a random per-process key logged users out on nearly every
request when the app runs under multiple gunicorn workers.

Set it once and never change it casually (changing it invalidates every
existing session cookie):

    SECRET_KEY=<a long random string, at least 16 chars>

Render: Environment → add `SECRET_KEY` (generate with
`python -c "import secrets; print(secrets.token_hex(32))"`).

Gunicorn note: the repo default `Dockerfile` CMD uses 4 workers; that is
fine now that the secret is shared, because every worker — and every
restart — signs cookies with the same key.

Database persistence (DATABASE_URL)
-----------------------------------
The app reads `DATABASE_URL` and falls back to `sqlite:///jobagent.db`
(local dev, resolves under `instance/`).

Additive-only schema upgrades: `db.create_all()` creates missing tables,
and `ensure_schema_upgrades()` (models/user_model.py) adds columns that
older databases lack (`user_preferences.timezone`, `notification_slots`,
`notify_*`, `notifications.read_at`, `interview_history.weak_areas`,
`interview_history.strong_areas`, `interview_history.overall_score`).
Existing rows are never altered or deleted.

On Render's free tier the local SQLite file is **ephemeral**: the disk is
wiped on every deploy, so registered users vanish. Choose one:

1. Attach a Render **persistent disk** mounted at the instance path, or
2. Set `DATABASE_URL` to a managed database (Render Postgres), e.g.

    DATABASE_URL=postgresql://<user>:<password>@<host>/<db>

Render: Environment → add `DATABASE_URL`; Dashboard → attach a disk if
staying on SQLite. This is configuration, not code — no code-only fix
exists for ephemeral disks.