# JobAgent

An AI-powered career assistant that helps job seekers prepare for interviews, analyze resumes, discover career paths, and match with job opportunities. The application features an adaptive AI interview system powered by Groq, RAG-based knowledge retrieval, resume ATS analysis, and role-guided career navigation.

## Features

- **AI Interview System** — Adaptive technical interviews powered by Groq LLM (question generation + answer evaluation)
- **Resume Analysis** — ATS scoring, strengths/missing-items detection, skill extraction
- **Role Guides** — Curated career paths with responsibilities, skills, salary ranges, and growth outlooks
- **Job Matching** — Skill-gap analysis and job board integrations
- **Career Insights** — Market demand analysis and career recommendations
- **RAG Knowledge Base** — Vector search over technical concepts for grounded interview answers
- **Multi-platform Support** — Job scraping from Naukri, RemoteOK, Wellfound (via Firecrawl)
- **User Accounts** — Authentication, saved jobs, interview progress tracking

## Local Setup

### Prerequisites

- Python 3.8+ (developed on Python 3.9)
- pip package manager

### 1. Clone & Install

```bash
git clone https://github.com/yourname/job-agent.git
cd job-agent
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | Yes | Strong random secret for Flask sessions |
| `GROQ_API_KEY` | Yes (interview) | Get from [console.groq.com](https://console.groq.com/) — powers interview Q&A |
| `FRONTEND_URL` | No | CORS allowlist origin (e.g. `https://app.vercel.app`). Leave empty for dev |
| `DATABASE_URL` | No | Defaults to `sqlite:///jobagent.db` |
| `FIRECRAWL_API_KEY` | No | Required only for Wellfound scraping |
| `PORT` | No | Server port (default 5000) |
| `HOST` | No | Server host (default 0.0.0.0) |

### 3. Run Locally

```bash
python app.py
```

Then open `http://localhost:5000` in your browser.

### Frontend Build

This project uses **server-rendered Flask templates + static JS/CSS** — there is no separate frontend build step. The frontend assets are served directly from the Flask app (`static/` and `templates/` directories). No `npm install` or `npm run build` is needed.

## Deployment Architecture (Temporary)

```
┌─────────────────────────────────────────────────┐
│  Hosting Platform (e.g. Render / Fly.io / etc.) │
│                                                 │
│  ┌──────────────┐       ┌───────────────────┐ │
│  │ Frontend     │  HTTP  │ Backend (Flask)   │ │
│  │ (same origin │◄─────►│  python app.py    │ │
│  │  as backend) │  API   │  PORT from env    │ │
│  └──────────────┘       │  Groq LLM         │ │
│                          │  SQLite/RDS DB    │ │
│                          └───────────────────┘ │
└─────────────────────────────────────────────────┘
```

### Deployment Steps

1. **Backend (Flask)** — Deploy `app.py` to any Python-capable host:
   - Set `PORT` and `HOST` environment variables (platform provides `PORT` automatically on most hosts)
   - Set all required env vars from `.env.example` as **hosted environment variables** (never commit `.env`)
   - Start command: `python app.py`
   - The app binds to `0.0.0.0:$PORT` automatically

2. **Frontend** — Same-origin serving (Flask templates + static JS/CSS). If you choose to host the frontend separately:
   - Set `FRONTEND_URL=https://your-frontend-origin.com` in the backend's environment to enable CORS
   - The JS frontend reads `API_BASE_URL` from a `<meta name="api-base-url">` tag or `window.__API_BASE_URL__` variable. Add this meta tag to `templates/index.html`:
     ```html
     <meta name="api-base-url" content="https://your-backend.example.com">
     ```

### Security Notes

- **Never commit `.env` or API keys.** Set all secrets through your hosting platform's environment variables.
- **CORS is restricted** — set `FRONTEND_URL` to your exact frontend origin. If unset, all origins are allowed (dev convenience only).
- **SQLite** is used by default for simplicity. For production with multiple workers, switch to PostgreSQL (`DATABASE_URL=postgresql://…`).
- The `instance/jobagent.db` file and `uploads/` directory are excluded from version control via `.gitignore`.

## Testing

```bash
pytest tests/ -v
```

## Environment Variables (Complete Reference)

| Variable | Required | Default |
|---|---|---|
| `SECRET_KEY` | Yes | (random) |
| `GROQ_API_KEY` | Yes (interview) | — |
| `FRONTEND_URL` | No | (all origins) |
| `DATABASE_URL` | No | `sqlite:///jobagent.db` |
| `FIRECRAWL_API_KEY` | No | — |
| `PORT` | No | `5000` |
| `HOST` | No | `0.0.0.0` |
| `FLASK_DEBUG` | No | `1` (dev) |
| `LLM_MODEL` | No | (auto-discover) |

## License

This project is for educational purposes.
