# Job Tracker — Deployment Issues Audit (Phase 1)

**Deployment:** https://job-tracker-amxp.onrender.com/
**Audited:** local working tree (GitHub `origin/master` `6633cfe` + local Dockerfile permission fix).
**Method:** static inspection of `app.py` (~3,470 lines), all routes, `static/js/app.js`, `static/js/auth.js`, `templates/*.html`, `models/*.py`, `services/interview/*`, `services/llm/*`, `utils/auth.py`, Dockerfile, requirements.txt, existing tests. Repo-wide regex searches for all requested terms.

**Rule honored:** no fix code was changed during this audit.

---

## 1. Executive summary

| # | Symptom | Primary root cause(s) | Main fix locations |
|---|---|---|---|
| 1 | Name shows "JobAgent" | Brand strings hardcoded in templates/JS/backend responses | templates/*.html, static/js/*.js, app.py strings, README |
| 2 | Chat "Failed to send: Unexpected token '<'" | RC1+RC2: invalid session → 302 to login HTML → `r.json()` on HTML | app.py (secret key, JSON 401), app.js `apiCall` |
| 3 | Privacy "Failed to accept… Unexpected token '<'" | Same as #2; accept route also not idempotent (re-inserts welcome msg) | app.py:3304–3325, app.js:726–734 |
| 4 | Scores wrong, "Average Score: N/A" | End route hand-builds summary **omitting** `average_score`/dimension scores; `generate_report()` never called | app.py:2938–2955, state.py:298–335, app.js:583–596 |
| 5 | Answers need 4–5 retries; repeated questions | In-memory `interview_sessions` + **4 gunicorn workers** → 400 "Invalid or expired session" → retries; weak dedup | app.py:79, 2752, 2805; Dockerfile CMD |
| 6 | Role Guide "Search failed: Failed" | Unhandled exception → Flask **HTML 500** (no error handlers exist) → `apiCall` fallback `{error:'Failed'}` | app.py:2280–2337, app.js:43–49 |
| 7 | Must re-enter credentials | (a) `SECRET_KEY` random per process (4 workers = 4 keys); (b) SQLite on Render **ephemeral disk** wiped each deploy | app.py:84, 98–108; env config |
| 8 | Main app reachable without login | `/` and `spa_fallback` unprotected; most `/api/*` routes unprotected | app.py:2256–2262, §5 route list |

### Cross-cutting root causes

- **RC1 — Per-process random `SECRET_KEY`** (`app.py:84`): `os.environ.get('SECRET_KEY', os.urandom(24).hex())`. Dockerfile CMD runs **4 gunicorn workers**; each worker generates a *different* key → a cookie signed by worker A fails validation on worker B ≈75% of requests → random logouts and 302-to-login on API calls. Restart also invalidates all sessions when `SECRET_KEY` is unset on Render.
- **RC2 — API 401s return HTML; frontend parses HTML as JSON.** `login_manager.login_view = 'login_page'` (app.py:115) with **no `unauthorized_handler`** → Flask-Login 302-redirects unauthenticated API calls to the login page; `fetch` follows and receives **200 + HTML**; `apiCall` (app.js:43–49) calls `r.json()` (line 48) → `Unexpected token '<'`. On the `!r.ok` branch it falls back to `{error:'Failed'}` → toasts "Search failed: **Failed**", "Failed to send: **Failed**".
- **RC3 — Ephemeral SQLite.** `DATABASE_URL` defaults to `sqlite:///jobagent.db` → Flask-SQLAlchemy 3.x resolves it under `instance/` → `/app/instance/jobagent.db` on Render's **ephemeral filesystem**, wiped on every deploy → registered users vanish. `db.create_all()` (app.py:124–128) is idempotent and does **not** destroy data — the filesystem does.
- **RC4 — Interview state is in-memory only** (`app.py:79` `interview_sessions: Dict`). Multi-worker + restarts → "Invalid or expired session" 400s, retried answers, duplicated turns. `InterviewHistory` model exists but is unused by the active interview routes.
- **RC5 — No JSON error handlers.** No `@app.errorhandler` anywhere in `app.py` → any unhandled exception renders Werkzeug's HTML 500 page, converted by `apiCall` into the useless message "Failed".

---

## 2. Issue-by-issue root causes

### Issue 1 — Product name still "JobAgent" (Phase 2)
Visible occurrences found (brand → **Job Tracker**):
- `templates/index.html:6` — `<title>JobAgent - Smart Career Assistant</title>`
- `templates/index.html:424` — `<strong>JobAgent Community</strong>`
- `templates/login.html:6`, `signup.html:6`, `forgot_password.html:6`, `reset_password.html:6` — `<title>… - JobAgent</title>`
- `static/js/app.js:729` — toast `Welcome to the JobAgent Community!`
- `app.py:2161` — signup response `Welcome to JobAgent.`
- `app.py:3231 / 3237 / 3266 / 3319` — chat policy title, "feedback about the JobAgent platform", banned message, join message
- `README.md:1` — public docs heading

Internal-only (**do not rename**): `app.py:2` module docstring, `static/js/auth.js:1` and `static/js/app.js:1` comments, `utils/logger.py` logger name, `sqlite:///jobagent.db` path/URLs, docker-compose/n8n infra names, doc generators (`generate_tech_pdf.py`, `convert_docs_to_pdf.py`), `docs/*` content, DB table names, Python identifiers.
Phase 2 must still run a final sweep of `templates/index.html` body (navbar brand, footer, headings) — the audit's `<title>` search only captured page titles.

### Issue 2 — Community chat send fails (Phase 6)
- Backend **exists and is correctly shaped**: `/api/chat/send` POST `@login_required` (`app.py:3355–3390`) — access check, empty/1000-char validation, profanity flag, persists `ChatMessage`, returns JSON.
- Frontend `sendChatMessage` calls `/api/chat/send` through `apiCall` (app.js ≈818–828) → on failure toasts `Failed to send: '+e.message`.
- Root cause = **RC1 + RC2** (invalid session → 302 login HTML → JSON parse error), **not** a missing route.
- Cosmetic defect: `from models.chat_model import ChatMessage, ChatUserStatus` duplicated at app.py:34 **and** 36.
- DB layer is fine: `chat_messages`, `chat_user_status` tables in `models/chat_model.py`; polling via `/api/chat/messages` (app.js:863–867 every ~5s).

### Issue 3 — Privacy acceptance fails (Phase 5)
- Route exists and returns JSON: `/api/chat/accept-policy` POST `@login_required` (app.py:3304–3325).
- Failure chain = RC1+RC2 (unauthenticated → 302 → login HTML → `Unexpected token '<'`).
- **Additional defect (must fix):** route is not idempotent — it inserts a `🎉 … has joined the JobAgent community chat!` `ChatMessage` on **every** call (3316–3323) even when the policy was already accepted. Must early-return `{'success': True, 'accepted': True}` when `status.has_accepted_policy` is already True.
- Frontend (`app.js:726–734`): on error it re-enables the button and shows the raw message — must use the safe API helper and only hide the policy screen on success. `renderChatPolicy`/login-required branch exists (app.js:705–722).

### Issue 4 — Interview scoring wrong / "N/A" (Phase 14)
- `/api/interview-prep/end` (app.py:2938–2955) **hand-builds** the summary and omits `average_score`, per-dimension `scores`, and `recommendations` that the UI expects.
- `InterviewState.generate_report()` (state.py:298–335) already computes `average_score`, `scores`, `strong_areas`, `recommendations` — but the end route never calls it (only `finalize()` at 2936).
- `app.js:583–596` renders `'N/A'` whenever `summary.average_score == null` → "Average Score: N/A" while `overall_score` still renders (e.g. 16 when most answers were scored ~10 by the heuristic `_empty_answer_result`, evaluator.py:352–356, e.g. after LLM fallback or empty submissions).
- Weighted dimension scoring already exists (`answer_evaluator.py:273+`: correctness .25, depth .20, clarity/practical/problem-solving, relevance .10) — Phase 14 must surface it, not reinvent it.
- Fixes: end route returns `state.generate_report()` merged with existing fields; UI shows "Not enough evaluated answers yet" when `answer_scores` is empty; never average unevaluated answers.

### Issue 5 — Answers need retries; duplicated turns (Phases 7–8)
- Frontend `sendInterviewAnswer` (app.js:522–560) is already well-built: in-flight guard `interviewProcessing` (523, 528, 555), disables input while pending, restores the answer on failure (553), thinking bubble lifecycle (534/538). Enter handler (576–581) and button (index.html:257) call the same guarded function — no duplicate listeners found.
- The retries users experience are **backend 400s**: `interview_sessions` is in-memory (app.py:79) and the Dockerfile runs **4 gunicorn workers** → the answer POST lands on a worker that doesn't hold the session → `{"error": "Invalid or expired session"}` 400 (2805–2806) → user retries → eventually the correct worker serves it.
- Duplicate turns/questions arise when a request **succeeds server-side but its response is lost client-side** (retry re-sends the answer; app.py:2847 `state.record_answer`, 2870 `record_question` increment the turn again; 2849–2850 also re-append the last question into `conversation`).
- Structural fix (Phase 16): persist sessions to DB (`interview_sessions`, `interview_messages` tables with ownership checks) + a frontend idempotency key per submission; keep `interviewProcessing` guard and the answer-preservation/retry behavior.

### Issue 6 — Role Guide "Search failed: Failed" (Phase 17)
- `performSearch` (app.js:54–69) calls `/api/expand-roles` **then** `/api/search`; both exist and return JSON (app.py:2280–2337, 2341+); neither is `@login_required`.
- `apiCall`'s `!r.ok` branch (app.js:47) falls back to `{error:'Failed'}` when the error body isn't JSON → toast "Search failed: Failed" ⇒ the server returned a **non-JSON error body**, i.e. Werkzeug's HTML error page from an **unhandled exception** (RC5 — there is no `@app.errorhandler` in the codebase).
- Likely exception sources in the chain: `_generate_role_guide_with_llm` (app.py:937–978, mostly guarded), `resolve_location(...)` (services/location/resolver.py:97+, external IP→currency lookup), `get_related_roles`, salary annotation. Any single throw → HTML 500 → the whole guide fails, violating "must not fail because one optional data source is unavailable".
- `get_role_guide` (app.py:985–1021) already degrades correctly (exact → alias → containment → LLM → honest "no guide" card). The defect is above it (error handling), not in the data.
- Fix: JSON error handlers for `/api/*`, per-source try/except with deterministic fallback in `/api/search`, safe `apiFetch`. **No fabricated salary/market data** — `annotate_salary_for_location` (resolver.py:97–101) only reformats stored values; keep it that way and show "unavailable" when absent.

### Issue 7 — Login/session persistence broken (Phase 4)
1. **RC1** — `app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())` (app.py:84). With 4 gunicorn workers, each process has its own random key → the signed session cookie validates on ~1 of 4 requests → user appears logged out between loads/API calls. If `SECRET_KEY` is unset on Render, every restart rotates the key too.
2. **RC3** — SQLite at `instance/jobagent.db` (Flask-SQLAlchemy resolves the relative `sqlite:///` URI against the instance folder) on Render's ephemeral disk → **all users deleted on every deploy/restart**.
3. `remember=True` on signup (app.py:2158) and optional on login (2183) already exist; `PERMANENT_SESSION_LIFETIME` and `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE` are **not configured anywhere** — must be set explicitly.
4. Passwords are hashed (werkzeug, models/user_model.py:9/39–43) with 5-attempt lockout (50–58) — **keep this system; do not duplicate it**.
5. `db.create_all()` in try/except-pass (app.py:124–128) is idempotent and never deletes data, but silently swallows DB errors — must log loudly. Make the DB path explicit/stable; document that Render's free tier has no persistent disk (mount a disk or set `DATABASE_URL` to a managed DB; code already supports Postgres). **Never delete existing users during startup.**

### Issue 8 — Main app reachable without login (Phase 3)
- `/` (app.py:2256–2258) and `spa_fallback` (2261+) render the full app with **no auth check**.
- `@login_required` covers only: `/api/auth/logout`, `/api/auth/me`, `/api/applications*`, `/api/notifications*`, `/api/chat/*`. **Unprotected:** `/api/search`, `/api/expand-roles`, `/api/analyze-resume`, `/api/skill-gap`, `/api/jobs/search`, `/api/market/skill-demand`, **all `/api/interview-prep/*`**, plus `/api/auth/check` (by design).
- Interview routes also have **no ownership check** (anyone holding a `session_id` can answer/end) — IDOR (Phases 16/22).
- Fix: server-side gate — unauthenticated HTML requests redirect to `/login`; `/api/*` requests get JSON 401 via a custom `unauthorized_handler` (keyed on `request.path.startswith('/api')`); authenticated users visiting `/login` go straight into the app; remaining APIs get `@login_required`; interview endpoints verify `session.user_id == current_user.id`.

---

## 3. Repo-wide search inventory (summary)

- **"JobAgent"**: ~100+ matches. User-facing: `app.py` 2161, 3231–3319; `templates/*` titles + chat header; `static/js/app.js:729`. Internal (leave): module docstrings, `utils/logger.py` logger name, `jobagent.db` path/URLs, docker-compose/n8n infra names, `models/*.py` docstrings, `job-platform/*` (separate project, out of scope), `docs/*` and PDF generators.
- **"AI Job Agent"**: `docs/DOCUMENTATION.html:6` only (docs scope).
- **"JobAgent Community"**: app.py:3231, 3266, 3319; static/js/app.js:729; templates/index.html:424.
- **"N/A"**: user-visible only at static/js/app.js:594–595 (report rendering); app.py:2776 is a diag log; context_builder.py:86/101 are internal LLM-prompt placeholders (acceptable).
- **"interview" / "session" / "login" / "signup" / "chat" / "privacy" / "accept" / "role guide"**: covered with file:line references in §2.

## 4. Key architecture facts for the fixes

- **Auth stack**: Flask-Login + `User` (hashed passwords via werkzeug, 5-attempt lockout, `UserSession` DB tracking in `utils/auth.py:83–150, 168–233`); `user_loader` app.py:119–121; `login_view='login_page'` (115); signup/login already return proper JSON (2138–2190).
- **Frontend helper**: `apiCall` (app.js:43–49) lacks status/content-type handling; `API_BASE_URL` meta-tag override exists (app.js:4–18); same-origin in the current deployment.
- **Interview**: `/api/interview-prep/start|answer|end` (app.py ≈2700–2962); `InterviewState` (state.py) tracks questions/topics/skills/claims/difficulty/turns; `QuestionGenerator` is LLM-first with deterministic fallback and `_semantic_dup` word-Jaccard dedup (question_generator.py:193–220, threshold 0.82 — too weak for paraphrases); `AnswerEvaluator` = LLM + heuristic fallback + weighted dimensions (evaluator.py:273+); RAG retrieval wired into the answer route (app.py:2826–2843); provider selection via `get_llm_provider()` → Groq-only today (app.py:53–65), while `services/llm/local_llm_provider.py` already implements an OpenAI-compatible local runtime (Ollama/llama.cpp/LM Studio/Jan) — the Phase 13 abstraction largely exists and must be preserved, not rebuilt.
- **RAG**: `services/rag/*` with graceful degradation when sentence-transformers is absent, embedding cache `.cache/rag`, corpora `data/interview_knowledge/*.md`. sentence-transformers is **not** in requirements.txt; RAG currently degrades to zero-vector retrieval — keep degradation unless Phase 12 deliberately adds the dependency (note: the Dockerfile is wheels-only; sentence-transformers ships cp311 wheels).
- **Deployment**: Dockerfile (3.11-slim, `/opt/venv`, wheels-only, non-root `appuser`, gunicorn **4 workers** — worker count interacts with RC1/RC4 and may stay once sessions are DB-backed), `/opt/venv` + PATH permission fix applied locally (uncommitted).

## 5. What must NOT change

- Groq integration (`get_llm_provider`, `services/llm/grok_provider.py`) and interview logic contracts.
- Deterministic resume + skill intelligence (`services/resume/*`) — the existing 57/57 tests must keep passing.
- Existing tests; password hashing system; DB table names; internal naming (`jobagent.db`, logger name, imports, Python identifiers).
- Dockerfile model: wheels-only, non-root, no apt-get/gcc.
- No paid APIs; no fabricated salary/market/job/interview data; no user-data deletion.

## 6. Implementation order and gates (per Phase 23)

1. ✅ Audit (this document)
2. Auth gate + JSON 401 `unauthorized_handler` + `SECRET_KEY` required at boot + cookie flags → auth/protected-route tests
3. DB path/persistence (explicit stable path or documented `DATABASE_URL`; idempotent startup with loud logging) → signup + restart-simulation tests
4. Privacy acceptance idempotency + frontend safe parse → accept / already-accepted / unauth tests
5. Community chat safe parse + multi-send + error paths → chat tests
6. Interview DB persistence + ownership checks → session lifecycle/ownership tests
7. Interview answer flow (one submission = one request; no next question before processing; retry-safe idempotency) → retry/duplicate tests
8. Scoring: end route → `generate_report()`, dimension breakdown, "Not enough evaluated answers yet" → score/zero-eval tests
9. Question dedup hardening (normalized tokens + embedding-assisted similarity; follow-ups exempt) → paraphrase-dedup tests
10. Resume/JD adaptive verification (claims/JD-tested lists populate) → tests
11. RAG enablement check + embedding cache; preserve graceful degradation → RAG-unavailable tests
12. Provider abstraction sweep (Groq + local providers; LLM only for questions/evaluation/follow-ups) → LLM-unavailable tests
13. Role Guide JSON error handlers + per-source fallbacks → valid/invalid/fallback tests
14. Brand rename → "Job Tracker" (visible strings only)
15. Full `python -m pytest -q`; `npm run build` (farsan-showcase) — report only what actually ran
16. Final verification; Render env checklist (`SECRET_KEY`, `DATABASE_URL` decision, disk)

After each logical phase: run relevant tests, fix failures, stop on major regressions.

## 7. Risks / open decisions

- **RC1 fix requires `SECRET_KEY` in the Render environment.** Recommended: fail fast at boot with a clear error when unset (secure default), plus `SESSION_COOKIE_SECURE=True`, `HTTPONLY=True`, `SAMESITE='Lax'`, `PERMANENT_SESSION_LIFETIME=30 days`.
- **RC3 has no code-only fix on Render's free tier**: ephemeral disk wipes persist until a disk is mounted or a managed `DATABASE_URL` is set — both are configuration, not code. The code fix is an explicit, stable path + idempotent startup + a clearly documented limitation.
- Worker count (4) can remain once sessions are DB-backed; reducing it is not required.
- The interview DB migration must be purely additive (`db.create_all()` creates the new tables; nothing existing is dropped or altered).