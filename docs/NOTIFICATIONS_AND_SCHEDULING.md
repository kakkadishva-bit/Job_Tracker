# Notification Scheduling (08:00 / 12:00 / 17:00)

The slot-based notification engine (`services/notifications/engine.py`)
generates notifications for three daily slots in each user's timezone
(default **Asia/Kolkata**):

- **08:00** — overnight/morning digest
- **12:00** — midday digest
- **17:00** — evening digest

Generation is idempotent: every check writes a `dedupe_key` unique per
user, so repeated or concurrent runs never duplicate anything. If there
is no real data for a check, it produces nothing — filler notifications
are never fabricated. The user's timezone, slot hours and per-category
opt-outs live in `UserPreference` (see "Database" below).

Two runners are available (both are idempotent; running both at once is
safe):

## Option A — in-process background thread (default for web services)

`services/notifications/scheduler.py` is started automatically when the
app boots (both `python app.py` and gunicorn/WSGI import paths), runs a
pass every `NOTIFY_SCHEDULER_INTERVAL_MINUTES` (default **10**), and
covers any user whose slot is currently due.

Environment flags:

| Variable                              | Default | Meaning                                        |
|---------------------------------------|---------|------------------------------------------------|
| `NOTIFY_SCHEDULER_ENABLED`            | `1`     | Set to `0` to stop the background thread.      |
| `NOTIFY_SCHEDULER_START_ON_IMPORT`    | `1`     | Set to `0` if a cron job is used instead.      |
| `NOTIFY_SCHEDULER_INTERVAL_MINUTES`   | `10`    | Minutes between scheduler passes (>= 1).       |

## Option B — Render Cron Job (required on the free tier)

Render's free tier spins the web service down, so the background thread
cannot be trusted there. Instead create a **Render Cron Job** that runs
the bundled `schedule_notifications.py` script (one safe, idempotent
pass) and set `NOTIFY_SCHEDULER_START_ON_IMPORT=0` on the web service:

| Command                            | Schedule (cron) | Covers (Asia/Kolkata) |
|------------------------------------|-----------------|-----------------------|
| `python schedule_notifications.py` | `30 2 * * *`   | 08:00 IST             |
| `python schedule_notifications.py` | `30 6 * * *`   | 12:00 IST             |
| `python schedule_notifications.py` | `30 11 * * *`  | 17:00 IST             |

The script needs the same environment as the web service
(`SECRET_KEY`, `DATABASE_URL`, job-search API keys). No extra
libraries are required — it imports `app` and the engine only.

## Notification categories (all real data, never fabricated)

1. **Job searching** (`new_job_match`) — fresh postings from the live
   search service matching the user's saved preferred roles.
2. **New skills** (`new_skill`) — skills extracted from those real
   postings (evidence-based extractor) that the profile lacks.
3. **In-demand skills** (`indemand_skill`) — top skills by real mention
   counts from live postings (sample size shown in the message).
4. **Resume analysis** (`resume_analysis`) — stale-resume or missing-
   resume reminders derived from the user's own profile state.
5. **Interview prep** (`interview_reminder`, `interview_prep`) —
   scheduled-interview alerts plus daily prep reminders that reference
   the user's own weak areas from their last practice session.
6. **Job tracker** (`tracker_stale`) — follow-ups for applications that
   have sat 7+ days in one status and weekly nudges for saved jobs that
   were never applied to (matched by the user's own company+role rows).

## API surface (all `/api/notifications*` routes require login)

| Method | Route                                       | Purpose                        |
|--------|---------------------------------------------|--------------------------------|
| GET    | `/api/notifications`                        | Run due generation, return `{unread_count, notifications}` (newest 30, with `is_read`, `created_at`, `type`). |
| POST   | `/api/notifications/<id>/read`              | Mark one as read (owner only → 404 otherwise). |
| POST   | `/api/notifications/read-all`               | Mark all unread as read (returns `marked_count`; rows are kept, never deleted). |

