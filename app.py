"""

JobAgent - Smart Career Assistant

Flask backend with role guides, resume analysis, ATS scoring,

skill gap analysis, interview prep, and career insights.

"""



import os

import json

import uuid

import re

import urllib.parse

from datetime import datetime, timedelta

from typing import Dict, List, Any, Optional



from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ - without this, GROQ_API_KEY (and

                # ADZUNA/RAPIDAPI keys) in .env are never actually picked up

                # when running via `python app.py` instead of `flask run`.



from flask import (

    Flask, render_template, request, jsonify,

    session, send_from_directory, redirect, url_for

)

from flask_login import (

    LoginManager, login_user, logout_user,

    login_required, current_user

)



from models.job_model import Job

from models.user_model import (

    db, User, UserProfile, UserPreference, SavedJob, JobApplication,

    InterviewHistory, AuditLog, PasswordResetToken, Notification

)

from models.chat_model import ChatMessage, ChatUserStatus

from config import config as app_config

from models.chat_model import ChatMessage, ChatUserStatus

from config import config as app_config



# ========================================================================
# Role Guide Search API
# ========================================================================
# Live job search, market demand, notifications, location 

from services.jobs.job_search_service import search_jobs as live_job_search

from services.market.demand_analyzer import analyze_skill_demand, compare_resume_to_demand

from services.notifications.engine import generate_notifications_for_user

from services.location.resolver import resolve_location, annotate_salary_for_location



# ========================================================================
# Role Guide Search API
# ========================================================================
# Adaptive Interview System 

from services.interview import InterviewState, QuestionGenerator, InterviewContextBuilder, AnswerEvaluator
from services.interview.session_store import InterviewSessionStore

from services.llm import LocalLLMProvider

from services.rag import get_rag



_llm_provider_singleton = None





def get_llm_provider():

    """Interview LLM provider: Groq (api.groq.com) ONLY.



    Uses the GROQ_API_KEY from .env. Ollama, xAI/Grok, OpenAI and Gemini are

    never selected. Returns None when Groq is not configured; QuestionGenerator

    and AnswerEvaluator then serve deterministic results tagged with the exact

    reason (fallback_reason), and the real Groq error is logged, never hidden.

    """

    global _llm_provider_singleton

    if _llm_provider_singleton is None:

        from services.llm.grok_provider import get_interview_llm

        _llm_provider_singleton = get_interview_llm()

    return _llm_provider_singleton





def _interview_diag(msg: str) -> None:

    """TEMP INTERVIEW-DIAG: print Groq usage facts for the interview endpoints.



    REMOVE after verification. provider=groq, question_llm/evaluation_llm flags

    and the real provider error (HTTP status / exception) on failure - never a

    silent fallback."""

    print("[INTERVIEW-DIAG] " + msg, flush=True)







# In-memory interview session store (session_id -> state dict)

interview_sessions: Dict[str, Dict[str, Any]] = {}



from flask_cors import CORS



app = Flask(__name__, static_folder='static', template_folder='templates')

# The signing key must be stable across restarts and workers (sessions,
# remember-me cookies). Tests provide SECRET_KEY via the environment; in
# production set it in the environment — see docs/DEPLOYMENT_ENVIRONMENT.md.
_SECRET_KEY = os.environ.get('SECRET_KEY', '').strip()
if not _SECRET_KEY:
    if os.environ.get('FLASK_DEBUG', '') == '1' or __name__ == '__main__':
        # Local dev convenience only: warn loudly and use an ephemeral key.
        print('WARNING: SECRET_KEY is not set - using a random dev key. '
              'Login sessions will not survive restarts.')
        _SECRET_KEY = os.urandom(24).hex()
    else:  # pragma: no cover
        raise RuntimeError('SECRET_KEY environment variable is required '
                           'in production (see docs/DEPLOYMENT_ENVIRONMENT.md).')
app.secret_key = _SECRET_KEY

app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SECURE'] = os.environ.get('FLASK_DEBUG', '') != '1'
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_DEBUG', '') != '1'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload



# ========================================================================
# Role Guide Search API
# ========================================================================
# CORS Configuration

# Allow a separately-hosted frontend (e.g. Vercel) to call the API.

# FRONTEND_URL is the only allowed origin in production (never "*").

# Local dev with no FRONTEND_URL keeps full CORS support for convenience.

_frontend_url = os.environ.get('FRONTEND_URL', '').strip()

if _frontend_url:

    CORS(app, origins=[_frontend_url])

else:

    CORS(app, origins="*")  # dev convenience G override with FRONTEND_URL in prod



# ========================================================================
# Role Guide Search API
# ========================================================================
# Database Configuration

DB_PATH = os.environ.get('DATABASE_URL', 'sqlite:///jobagent.db')

if DB_PATH.startswith('sqlite'):

    app.config['SQLALCHEMY_DATABASE_URI'] = DB_PATH

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

else:

    app.config['SQLALCHEMY_DATABASE_URI'] = DB_PATH

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {

    'pool_pre_ping': True,

    'pool_size': 10,

    'max_overflow': 20,

}



db.init_app(app)



# ========================================================================
# Role Guide Search API
# ========================================================================
# Flask-Login Setup

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = 'login_page'

login_manager.login_message = 'Please sign in to access this page.'

login_manager.login_message_category = 'info'



@login_manager.user_loader

def load_user(user_id):

    return User.query.get(int(user_id))


# ========================================================================
# API Authentication Gate
# ========================================================================
# All /api/* routes require authentication EXCEPT the public auth endpoints
# below. Anonymous requests to any other /api/* route get a JSON 401.
_PUBLIC_API_PREFIXES = (
    '/api/auth/signup',
    '/api/auth/login',
    '/api/auth/forgot-password',
    '/api/auth/reset-password',
    '/api/auth/check',
)


@app.before_request
def _auth_gate():
    """Single gate for both pages and APIs.

    - Anonymous /api/* requests (except public auth APIs) get JSON 401.
    - Anonymous app pages (SPA routes) get a 302 redirect to /login.
    - Authenticated users hitting /login or /signup are sent into the app.
    """
    path = request.path

    # ── API routes: JSON responses only ─────────────────────────────
    if path.startswith('/api/'):
        if path.rstrip('/') in _PUBLIC_API_PREFIXES:
            return None
        if current_user.is_authenticated:
            return None
        return jsonify({'success': False,
                        'error': 'Authentication required',
                        'code': 'unauthorized'}), 401

    # ── Static files and health check: always public ────────────────
    if path.startswith('/static/') or path == '/health':
        return None

    # ── Public auth pages ───────────────────────────────────────────
    if path in ('/login', '/signup', '/forgot-password'):
        if current_user.is_authenticated and path in ('/login', '/signup'):
            return redirect('/')
        return None

    if path.startswith('/reset-password/'):
        return None

    # ── Every other page (SPA shell) requires a session ─────────────
    if not current_user.is_authenticated:
        return redirect('/login')
    return None
# ========================================================================
# Role Guide Search API
# ========================================================================
# Create tables on first run

with app.app_context():

    try:

        db.create_all()

    except Exception:

        pass


try:

    from models.user_model import ensure_schema_upgrades

    ensure_schema_upgrades(app)

except Exception:

    pass




# ========================================================================
# JSON Error Handlers
# ========================================================================

@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404
    return e


@app.errorhandler(405)
def handle_405(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Method not allowed'}), 405
    return e


@app.errorhandler(400)
def handle_400(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': str(e)}), 400
    return e


@app.errorhandler(401)
def handle_401(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Authentication required', 'code': 'unauthorized'}), 401
    return e


@app.errorhandler(403)
def handle_403(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    return e


@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return e


from werkzeug.exceptions import Unauthorized


@app.errorhandler(Unauthorized)
def handle_flask_login_unauthorized(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Authentication required', 'code': 'unauthorized'}), 401
    return e


# ========================================================================
# Role Guide Search API
# ========================================================================
# In-memory anonymous session store

user_sessions: Dict[str, Dict[str, Any]] = {}





def get_session_id():

    """Get or create a session ID."""

    if 'sid' not in session:

        session['sid'] = str(uuid.uuid4())

    return session['sid']





def get_user_data():

    sid = get_session_id()

    if sid not in user_sessions:

        user_sessions[sid] = {

            'saved_jobs': [],

            'interview_calls': [],

            'ats_scores': [],

            'resume_versions': [],

            'skill_progress': {},

            'search_history': []

        }

    return user_sessions[sid]





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




ROLE_MAP: Dict[str, List[str]] = {

    "python developer": [

        "Python Developer", "Backend Developer", "Django Developer",

        "Flask Developer", "AI Engineer", "Machine Learning Engineer",

        "Data Engineer", "Automation Engineer", "Software Engineer",

        "Full Stack Developer", "API Developer", "Cloud Engineer",

        "DevOps Engineer", "Data Scientist", "NLP Engineer",

        "Computer Vision Engineer", "ETL Developer",

        "Analytics Engineer", "Research Engineer", "Technical Consultant"

    ],

    "frontend developer": [

        "Frontend Developer", "UI Developer", "React Developer",

        "Angular Developer", "Vue.js Developer", "JavaScript Developer",

        "TypeScript Developer", "Web Developer", "Full Stack Developer",

        "UI/UX Developer", "Mobile Developer", "React Native Developer",

        "Flutter Developer", "Progressive Web App Developer",

        "CSS Developer", "HTML Developer", "SaaS Developer",

        "Frontend Architect", "Design Engineer", "Client-Side Developer"

    ],

    "data scientist": [

        "Data Scientist", "Machine Learning Engineer", "AI Engineer",

        "Data Analyst", "Business Intelligence Analyst", "Statistician",

        "Quantitative Analyst", "Research Scientist", "Data Engineer",

        "NLP Engineer", "Computer Vision Engineer", "MLOps Engineer",

        "Analytics Engineer", "Deep Learning Engineer",

        "Applied Scientist", "Decision Scientist",

        "Predictive Modeler", "Big Data Engineer",

        "BI Developer", "Data Architect"

    ],

    "full stack developer": [

        "Full Stack Developer", "Web Developer", "Software Engineer",

        "Frontend Developer", "Backend Developer", "MERN Stack Developer",

        "MEAN Stack Developer", "DevOps Engineer", "Cloud Developer",

        "API Developer", "Mobile Developer", "UI/UX Developer",

        "Application Developer", "Platform Engineer",

        "Solutions Architect", "Technical Lead",

        "Senior Software Engineer", "Stack Developer",

        "Full Stack Engineer", "Product Engineer"

    ],

    "devops engineer": [

        "DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer",

        "Platform Engineer", "Infrastructure Engineer", "CI/CD Engineer",

        "Release Engineer", "Build Engineer", "Systems Engineer",

        "Network Engineer", "Security Engineer", "AWS Engineer",

        "Azure Engineer", "Kubernetes Engineer", "Docker Engineer",

        "Automation Engineer", "SRE", "Cloud Architect",

        "IT Operations Engineer", "DevSecOps Engineer"

    ],

    "mobile developer": [

        "Mobile Developer", "Android Developer", "iOS Developer",

        "React Native Developer", "Flutter Developer", "Cross-Platform Developer",

        "Mobile App Developer", "Swift Developer", "Kotlin Developer",

        "Xamarin Developer", "Mobile Engineer", "App Developer",

        "Mobile UI Developer", "Mobile Backend Developer",

        "Progressive Web App Developer", "Hybrid App Developer",

        "Mobile Solutions Architect", "Mobile Platform Engineer",

        "Wearable App Developer", "Tablet Developer"

    ],

    "machine learning engineer": [

        "Machine Learning Engineer", "AI Engineer", "Data Scientist",

        "Deep Learning Engineer", "NLP Engineer", "Computer Vision Engineer",

        "MLOps Engineer", "Applied Scientist", "Research Scientist",

        "ML Infrastructure Engineer", "AI Research Engineer",

        "Machine Learning Scientist", "Predictive Modeler",

        "Computational Linguist", "AI Software Engineer",

        "Machine Learning Developer", "Autonomous Systems Engineer",

        "AI Platform Engineer", "Recommendation Systems Engineer",

        "Generative AI Engineer"

    ],

    "blockchain developer": [

        "Blockchain Developer", "Web3 Developer", "Solidity Developer",

        "Smart Contract Developer", "Crypto Developer", "DeFi Developer",

        "NFT Developer", "DApp Developer", "Blockchain Engineer",

        "Distributed Ledger Developer", "Blockchain Architect",

        "Token Engineer", "Protocol Developer",

        "Blockchain Security Engineer", "Consensus Engineer",

        "Blockchain Software Engineer", "Web3 Engineer",

        "Digital Asset Developer", "Blockchain Consultant",

        "Decentralized Systems Engineer"

    ],

    "cloud architect": [

        "Cloud Architect", "Cloud Engineer", "AWS Solutions Architect",

        "Azure Architect", "GCP Architect", "Cloud Consultant",

        "Cloud Security Architect", "Multi-Cloud Architect",

        "Cloud Infrastructure Engineer", "Cloud DevOps Engineer",

        "Cloud Platform Engineer", "Cloud Migration Specialist",

        "Cloud Operations Engineer", "Cloud Native Engineer",

        "Serverless Architect", "Cloud Network Engineer",

        "Cloud Database Administrator", "Cloud Reliability Engineer",

        "Enterprise Cloud Architect", "Cloud Governance Specialist"

    ],

    "product manager": [

        "Product Manager", "Senior Product Manager", "Technical Product Manager",

        "Product Owner", "Program Manager", "Project Manager",

        "Growth Manager", "Product Analyst", "Product Designer",

        "Product Marketing Manager", "Scrum Master", "Agile Coach",

        "Product Strategist", "Innovation Manager",

        "Digital Product Manager", "Platform Product Manager",

        "Data Product Manager", "AI Product Manager",

        "E-commerce Product Manager", "SaaS Product Manager"

    ],

    "data analyst": [

        "Data Analyst", "Business Intelligence Analyst", "Reporting Analyst",

        "Analytics Consultant", "Metrics Analyst", "Research Analyst",

        "Financial Analyst", "Operations Analyst", "Marketing Analyst",

        "Product Analyst", "Healthcare Data Analyst", "Quantitative Analyst",

        "Data Visualization Specialist", "Database Analyst",

        "Statistical Analyst", "Performance Analyst",

        "Clinical Data Analyst", "Supply Chain Analyst",

        "Risk Analyst", "Credit Analyst"

    ],

    "ui/ux designer": [

        "UI/UX Designer", "UX Designer", "UI Designer",

        "Product Designer", "UX Researcher", "Interaction Designer",

        "Visual Designer", "UX Engineer", "Design Systems Designer",

        "Service Designer", "User Researcher", "Information Architect",

        "Content Designer", "UX Writer", "Motion Designer",

        "Accessibility Designer", "Game Designer",

        "Brand Designer", "Creative Designer", "Experience Designer"

    ],

    "ai engineer": [

        "AI Engineer", "Machine Learning Engineer", "Deep Learning Engineer",

        "NLP Engineer", "Computer Vision Engineer", "AI Research Scientist",

        "MLOps Engineer", "AI Platform Engineer", "Generative AI Engineer",

        "AI Software Engineer", "Applied Scientist", "AI Architect",

        "Conversational AI Engineer", "Reinforcement Learning Engineer",

        "AI Ethics Engineer", "Prompt Engineer", "AI Product Manager",

        "Autonomous Systems Engineer", "AI Infrastructure Engineer",

        "Recommendation Systems Engineer"

    ]

}





def _expand_generic(role: str) -> List[str]:

    """Generate related job titles for any given role."""

    base = role.strip().title()

    prefixes = ["Senior", "Junior", "Lead", "Staff", "Principal"]

    suffixes = [

        "Engineer", "Developer", "Specialist", "Analyst",

        "Architect", "Consultant", "Manager", "Lead"

    ]

    titles = [base]

    for s in suffixes:

        titles.append(f"{base} {s}")

    for p in prefixes[:2]:

        titles.append(f"{p} {base}")

    seen = set()

    result = []

    for t in titles:

        if t.lower() not in seen:

            seen.add(t.lower())

            result.append(t)

    return result[:20]





def get_related_roles(role: str) -> List[str]:

    """Related titles only from curated data G never fabricated.



    - canonical/alias query G its ROLE_MAP list (each related title keeps

      its curated name, never the query relabeled);

    - unknown query G [query] alone, so /api/search renders exactly one

      honest "no guide" card instead of N identical generic cards.

    """

    key = (role or "").strip().lower()

    if not key:

        return []

    if key in ROLE_MAP:

        return ROLE_MAP[key]

    if key in ROLE_ALIASES and ROLE_ALIASES[key] in ROLE_MAP:

        return ROLE_MAP[ROLE_ALIASES[key]]

    return [role.strip()]





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




SKILLS_DATABASE = {

    "programming_languages": [

        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go",

        "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB",

        "Dart", "Elixir", "Haskell", "Lua", "Perl"

    ],

    "frontend": [

        "React", "Angular", "Vue.js", "HTML5", "CSS3", "SASS", "LESS",

        "Redux", "Next.js", "Nuxt.js", "Svelte", "jQuery", "Bootstrap",

        "Tailwind CSS", "Material UI", "Ant Design", "Webpack", "Vite",

        "Storybook", "Web Components"

    ],

    "backend": [

        "Node.js", "Express.js", "Django", "Flask", "FastAPI", "Spring Boot",

        "Ruby on Rails", "ASP.NET", "Laravel", "NestJS", "Gin", "Echo",

        "Fiber", "Actix", "Phoenix", "Ktor"

    ],

    "databases": [

        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",

        "SQLite", "Oracle", "SQL Server", "Cassandra", "DynamoDB",

        "Firebase", "Supabase", "Neo4j", "CouchDB", "InfluxDB",

        "TimescaleDB", "ClickHouse", "Snowflake"

    ],

    "cloud": [

        "AWS", "Azure", "GCP", "Heroku", "DigitalOcean", "Vultr",

        "Linode", "Cloudflare", "Vercel", "Netlify", "Firebase"

    ],

    "devops": [

        "Docker", "Kubernetes", "Jenkins", "GitLab CI", "GitHub Actions",

        "Terraform", "Ansible", "Puppet", "Chef", "Prometheus", "Grafana",

        "Nagios", "CircleCI", "Travis CI", "ArgoCD", "Helm", "Istio",

        "Laravel Forge", "Pulumi"

    ],

    "ai_ml": [

        "TensorFlow", "PyTorch", "Scikit-learn", "Keras", "OpenCV",

        "NLTK", "SpaCy", "Hugging Face", "LangChain", "Pandas", "NumPy",

        "Matplotlib", "Seaborn", "XGBoost", "LightGBM", "MLflow",

        "Kubeflow", "Apache Spark", "Databricks", "Jupyter"

    ],

    "mobile": [

        "React Native", "Flutter", "Swift", "Kotlin", "Xamarin",

        "Ionic", "Cordova", "Android SDK", "iOS SDK", "SwiftUI",

        "Jetpack Compose"

    ],

    "tools": [

        "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence",

        "Slack", "Notion", "Figma", "Adobe XD", "Postman", "Swagger",

        "VS Code", "IntelliJ IDEA", "PyCharm", "Vim", "Neovim"

    ],

    "methodologies": [

        "Agile", "Scrum", "Kanban", "TDD", "BDD", "CI/CD",

        "Microservices", "REST API", "GraphQL", "gRPC", "WebSockets",

        "Event-Driven Architecture", "Domain-Driven Design",

        "Serverless", "12-Factor App"

    ],

    "security": [

        "OAuth", "JWT", "SSL/TLS", "OWASP", "Penetration Testing",

        "SIEM", "Firewall Management", "Cryptography", "IAM",

        "Security Auditing", "Vulnerability Assessment"

    ]

}



ALL_SKILLS = set()

for cat in SKILLS_DATABASE.values():

    ALL_SKILLS.update(s.lower() for s in cat)





def _extract_skills_from_text(text: str) -> List[str]:

    """Extract known skills from free-form text."""

    found = set()

    text_lower = text.lower()

    for cat in SKILLS_DATABASE.values():

        for skill in cat:

            pattern = r'\b' + re.escape(skill.lower()) + r'\b'

            if re.search(pattern, text_lower):

                found.add(skill)

    return sorted(found)





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




PLATFORM_SEARCH_URLS = {

    # ========================================================================
# Role Guide Search API
# ========================================================================


    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={role}",

    "indeed": "https://in.indeed.com/jobs?q={role}",

    "glassdoor": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={role}",

    "ziprecruiter": "https://www.ziprecruiter.com/jobs/search?search={role}",

    "monster": "https://www.monster.com/jobs/search?q={role}",

    "simplyhired": "https://www.simplyhired.com/search?q={role}",

    "careerbuilder": "https://www.careerbuilder.com/jobs?keywords={role}",

    "wellfound": "https://wellfound.com/jobs?query={role}",

    "dice": "https://www.dice.com/jobs?q={role}",

    "flexjobs": "https://www.flexjobs.com/search?search={role}",

    # Remote-Focused Platforms

    "remotive": "https://remotive.com/remote-jobs?search={role}",

    "workingnomads": "https://www.workingnomads.com/jobs?search={role}",

    "himalayas": "https://himalayas.app/jobs?search={role}",

    "jobspresso": "https://jobspresso.co/?s={role}",

    "skipthedrive": "https://www.skipthedrive.com/jobs?search={role}",

    "justremote": "https://justremote.co/remote-jobs?search={role}",

    "europeremotely": "https://europeremotely.com/?s={role}",

    "arcdev": "https://arc.dev/remote-jobs?search={role}",

    "virtualvocations": "https://www.virtualvocations.com/jobs?search={role}",

    "wfh": "https://www.wfhquest.com/jobs?search={role}",

    "remoteok": "https://remoteok.com/remote-jobs?search={role}",

    "weworkremotely": "https://weworkremotely.com/remote-jobs/search?term={role}",

    "turing": "https://www.turing.com/jobs?search={role}",

    "remoteco": "https://remote.co/remote-jobs/search?search={role}",

    "hired": "https://hired.com/jobs?search={role}",

    "greenhouse": "https://boards.greenhouse.io/jobs?search={role}",

    "lever": "https://jobs.lever.co/search?query={role}",

    

    "talent": "https://www.talent.com/jobs?k={role}",

    "jooble": "https://jooble.org/SearchResult?ukw={role}",

    "xing": "https://www.xing.com/jobs/search?keywords={role}",

    "theladders": "https://www.theladders.com/job-search?keywords={role}",

    "snagajob": "https://www.snagajob.com/search?q={role}",

    "adzuna": "https://www.adzuna.com/search?q={role}",

    "usajobs": "https://www.usajobs.gov/Search/Results?k={role}",

    "idealist": "https://www.idealist.org/en/jobs?q={role}",

    "builtin": "https://builtin.com/jobs?search={role}",

    "jobrapido": "https://www.jobrapido.com/?q={role}",

    # India-Specific Platforms

    "naukri": "https://www.naukri.com/{role}-jobs",

    "foundit": "https://www.foundit.in/jobs/{role}",

    "internshala": "https://internshala.com/jobs/{role}",

    "freshersworld": "https://www.freshersworld.com/jobs/{role}",

    "shine": "https://www.shine.com/jobs/{role}",

    "timesjobs": "https://www.timesjobs.com/jobs/{role}",

    "apna": "https://apna.co/jobs/{role}",

    "cutshort": "https://cutshort.io/jobs/{role}",

    "hirist": "https://www.hirist.com/jobs/{role}",

    "instahyre": "https://www.instahyre.com/jobs/{role}",

    "iimjobs": "https://www.iimjobs.com/jobs/{role}",

    "placementindia": "https://www.placementindia.com/jobs/{role}",

    

    # Freelancing Platforms

    "upwork": "https://www.upwork.com/nx/search/jobs/?q={role}",

    "fiverr": "https://www.fiverr.com/search/gigs?query={role}",

    "freelancer": "https://www.freelancer.com/jobs/{role}",

    "guru": "https://www.guru.com/jobs/{role}",

    "peopleperhour": "https://www.peopleperhour.com/search?search={role}",

    "toptal": "https://www.toptal.com/freelance-jobs?search={role}",

}



ROLE_GUIDES_DB: Dict[str, Dict[str, Any]] = {

    "frontend developer": {

        "overview": "A Frontend Developer is responsible for building the user-facing side of web applications. They translate design mockups into interactive, responsive interfaces using HTML, CSS, and JavaScript frameworks. Modern frontend developers work with component-based architectures, state management, and performance optimization to deliver seamless user experiences across devices and browsers.",

        "responsibilities": [

            "Develop and maintain responsive web applications using modern frameworks (React, Angular, Vue.js)",

            "Collaborate with UI/UX designers to implement pixel-perfect interfaces",

            "Optimize applications for maximum speed, scalability, and cross-browser compatibility",

            "Write clean, maintainable, and well-documented code",

            "Implement and maintain design systems and component libraries",

            "Conduct code reviews and mentor junior developers",

            "Integrate RESTful APIs and GraphQL endpoints",

            "Write unit and integration tests for frontend code"

        ],

        "required_skills": ["HTML5", "CSS3", "JavaScript", "TypeScript", "React", "Git", "REST API", "Responsive Design"],

        "preferred_skills": ["Next.js", "Vue.js", "Angular", "SASS", "Redux", "Webpack", "Testing (Jest/Cypress)", "Performance Optimization"],

        "salary_estimate": {

            "usd": "$75,000 - $140,000",

            "inr": "G4,00,000 - G18,00,000",

            "eur": "G45,000 - G85,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $50K-$80K",

            "Mid-Level (2-5 years): $80K-$120K",

            "Senior (5-8 years): $120K-$160K",

            "Lead/Staff (8+ years): $150K-$200K+"

        ],

        "career_growth": [

            "Junior Frontend Developer G Mid-Level Frontend Developer",

            "Mid-Level G Senior Frontend Developer",

            "Senior G Frontend Architect or Engineering Manager",

            "Staff Engineer G Principal Engineer",

            "Specialization paths: UI/UX Engineering, Design Systems, Performance Engineering, Full Stack"

        ],

        "interview_topics": [

            "HTML/CSS fundamentals and responsive design",

            "JavaScript closures, prototypes, and async/await",

            "React hooks, context, and state management",

            "CSS Grid, Flexbox, and modern layout techniques",

            "Web performance optimization and Core Web Vitals",

            "Testing strategies (unit, integration, e2e)",

            "Browser rendering pipeline and repaint/reflow"

        ],

        "industry_demand": "High",

        "growth_outlook": "Strong demand continues as every company needs web interfaces. New frameworks and WebAssembly create emerging opportunities."

    },

    "python developer": {

        "overview": "A Python Developer builds and maintains software applications using the Python programming language. They work across various domains including web development (Django/Flask), data processing, automation, API development, and machine learning. Python developers are valued for their ability to write clean, readable code and rapidly prototype solutions.",

        "responsibilities": [

            "Design, develop, and deploy Python-based applications and services",

            "Build and maintain RESTful APIs using Django, Flask, or FastAPI",

            "Write reusable, testable, and efficient code following PEP 8 standards",

            "Integrate databases (PostgreSQL, MySQL, MongoDB) and cache layers (Redis)",

            "Implement automated testing, CI/CD pipelines, and deployment processes",

            "Collaborate with cross-functional teams on feature development",

            "Optimize application performance and database queries",

            "Write technical documentation and participate in code reviews"

        ],

        "required_skills": ["Python", "Django", "Flask", "REST API", "PostgreSQL", "Git", "SQL", "HTML5"],

        "preferred_skills": ["FastAPI", "Docker", "AWS", "Redis", "Celery", "SQLAlchemy", "Celery", "pytest"],

        "salary_estimate": {

            "usd": "$80,000 - $150,000",

            "inr": "G5,00,000 - G25,00,000",

            "eur": "G50,000 - G95,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $55K-$85K",

            "Mid-Level (2-5 years): $85K-$130K",

            "Senior (5-8 years): $130K-$170K",

            "Lead/Staff (8+ years): $160K-$220K+"

        ],

        "career_growth": [

            "Junior Python Developer G Mid-Level Developer",

            "Mid-Level G Senior Python Developer",

            "Senior G Tech Lead / Engineering Manager",

            "Staff Engineer G Principal Engineer / CTO",

            "Specialization paths: Backend Architecture, Data Engineering, ML Engineering, DevOps"

        ],

        "interview_topics": [

            "Python data structures and algorithms",

            "Django ORM and database optimization",

            "RESTful API design principles",

            "Concurrency: threads, multiprocessing, asyncio",

            "Memory management and garbage collection",

            "Testing with pytest and unittest",

            "Design patterns and SOLID principles"

        ],

        "industry_demand": "Very High",

        "growth_outlook": "Excellent G Python dominates in AI/ML, data science, web development, and automation. Demand continues to grow across all sectors."

    },

    "data scientist": {

        "overview": "A Data Scientist extracts meaningful insights from complex datasets using statistical analysis, machine learning, and data visualization. They bridge the gap between business questions and data-driven answers, building predictive models and dashboards that drive strategic decision-making across organizations.",

        "responsibilities": [

            "Analyze large datasets to identify trends, patterns, and actionable insights",

            "Build and deploy machine learning models for prediction and classification",

            "Develop data pipelines and ETL processes for data cleaning and preparation",

            "Create interactive dashboards and data visualizations for stakeholders",

            "Perform statistical testing and hypothesis validation",

            "Collaborate with engineering teams to productionize models",

            "Communicate findings to non-technical stakeholders",

            "Stay current with latest ML techniques and research papers"

        ],

        "required_skills": ["Python", "R", "SQL", "Pandas", "Scikit-learn", "TensorFlow", "Statistics", "Data Visualization"],

        "preferred_skills": ["PyTorch", "Deep Learning", "NLP", "Spark", "Tableau", "A/B Testing", "Feature Engineering", "Cloud (AWS/GCP)"],

        "salary_estimate": {

            "usd": "$95,000 - $165,000",

            "inr": "G8,00,000 - G35,00,000",

            "eur": "G60,000 - G110,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $65K-$100K",

            "Mid-Level (2-5 years): $100K-$145K",

            "Senior (5-8 years): $145K-$190K",

            "Lead/Principal (8+ years): $180K-$280K+"

        ],

        "career_growth": [

            "Junior Data Analyst G Data Scientist",

            "Data Scientist G Senior Data Scientist",

            "Senior G Principal Data Scientist / ML Engineering Manager",

            "Staff G VP of Data / Chief Data Officer",

            "Specialization paths: MLOps, Deep Learning, NLP, Computer Vision, Product Analytics"

        ],

        "interview_topics": [

            "Statistical concepts and probability theory",

            "Machine learning algorithms and when to use them",

            "Feature engineering and data preprocessing",

            "Model evaluation metrics and cross-validation",

            "SQL queries and window functions",

            "Python data manipulation with Pandas",

            "A/B testing and experimental design"

        ],

        "industry_demand": "Very High",

        "growth_outlook": "Exceptional G Every industry needs data-driven decision making. AI/ML specialization commands premium salaries."

    },

    "full stack developer": {

        "overview": "A Full Stack Developer works across the entire web development stack, from building user interfaces to designing server-side logic and database architecture. They are versatile engineers who can independently develop complete features end-to-end, making them highly valued in startups and agile teams.",

        "responsibilities": [

            "Develop end-to-end features across frontend and backend systems",

            "Design and implement RESTful APIs and database schemas",

            "Build responsive, accessible user interfaces with modern frameworks",

            "Set up and maintain CI/CD pipelines and cloud deployments",

            "Optimize applications for performance, security, and scalability",

            "Participate in architectural decisions and technical planning",

            "Write comprehensive tests (unit, integration, e2e)",

            "Mentor junior developers and contribute to engineering culture"

        ],

        "required_skills": ["JavaScript", "TypeScript", "React", "Node.js", "Express.js", "MongoDB", "PostgreSQL", "Git"],

        "preferred_skills": ["Next.js", "Docker", "AWS", "GraphQL", "Redis", "Kubernetes", "Testing", "System Design"],

        "salary_estimate": {

            "usd": "$80,000 - $155,000",

            "inr": "G5,00,000 - G22,00,000",

            "eur": "G50,000 - G95,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $55K-$85K",

            "Mid-Level (2-5 years): $85K-$130K",

            "Senior (5-8 years): $130K-$175K",

            "Lead/Staff (8+ years): $160K-$230K+"

        ],

        "career_growth": [

            "Junior Full Stack Developer G Mid-Level Developer",

            "Mid-Level G Senior Full Stack Developer",

            "Senior G Tech Lead / Architect",

            "Staff G Principal Engineer / VP of Engineering",

            "Specialization paths: Frontend Architecture, Backend Systems, DevOps, Product Engineering"

        ],

        "interview_topics": [

            "System design and architecture patterns",

            "Data structures and algorithms",

            "Database design and optimization",

            "API design (REST and GraphQL)",

            "Security best practices (OWASP)",

            "Cloud deployment and scaling strategies",

            "Code quality and testing methodologies"

        ],

        "industry_demand": "Very High",

        "growth_outlook": "Excellent G Full-stack skills are highly valued, especially with modern frameworks. Companies seek versatile developers who can own features end-to-end."

    },

    "devops engineer": {

        "overview": "A DevOps Engineer bridges software development and IT operations, automating and streamlining the build, test, and deployment processes. They ensure high availability, scalability, and security of infrastructure while implementing CI/CD practices that enable rapid, reliable software delivery.",

        "responsibilities": [

            "Design, build, and maintain CI/CD pipelines for automated testing and deployment",

            "Manage cloud infrastructure (AWS, Azure, GCP) using Infrastructure as Code",

            "Implement containerization and orchestration with Docker and Kubernetes",

            "Monitor system performance, set up alerts, and ensure high availability",

            "Automate repetitive operational tasks and improve developer workflows",

            "Manage secrets, access control, and security compliance",

            "Incident response and post-mortem analysis",

            "Optimize cloud costs and resource utilization"

        ],

        "required_skills": ["Docker", "Kubernetes", "CI/CD", "AWS", "Linux", "Terraform", "Python", "Git"],

        "preferred_skills": ["Ansible", "Prometheus", "Grafana", "Jenkins", "GitHub Actions", "Helm", "Istio", "Pulumi"],

        "salary_estimate": {

            "usd": "$90,000 - $165,000",

            "inr": "G8,00,000 - G30,00,000",

            "eur": "G55,000 - G105,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $60K-$95K",

            "Mid-Level (2-5 years): $95K-$140K",

            "Senior (5-8 years): $140K-$185K",

            "Lead/SRE (8+ years): $170K-$250K+"

        ],

        "career_growth": [

            "Junior DevOps Engineer G Mid-Level DevOps Engineer",

            "Mid-Level G Senior DevOps / SRE",

            "Senior G Platform Engineering Manager",

            "Staff G VP of Infrastructure / CTO",

            "Specialization paths: SRE, Cloud Architecture, Platform Engineering, Security Engineering"

        ],

        "interview_topics": [

            "CI/CD pipeline design and implementation",

            "Container orchestration with Kubernetes",

            "Infrastructure as Code (Terraform, CloudFormation)",

            "Monitoring, logging, and alerting strategies",

            "Incident management and on-call practices",

            "Cloud networking and security",

            "Linux system administration and scripting"

        ],

        "industry_demand": "Very High",

        "growth_outlook": "Excellent G Cloud-native, Kubernetes, and platform engineering are top priorities. Every company with digital products needs DevOps expertise."

    },

    "machine learning engineer": {

        "overview": "A Machine Learning Engineer designs, builds, and deploys ML models at scale. They combine software engineering best practices with deep knowledge of machine learning algorithms to create production-ready AI systems. This role requires strong programming skills alongside mathematical foundations in statistics and linear algebra.",

        "responsibilities": [

            "Design and implement ML models for classification, regression, NLP, and computer vision",

            "Build end-to-end ML pipelines: data ingestion, feature engineering, training, evaluation, deployment",

            "Optimize model performance, latency, and resource utilization for production",

            "Set up experiment tracking and model versioning (MLflow, Weights & Biases)",

            "Collaborate with data scientists to transition research prototypes to production",

            "Implement A/B testing frameworks for model evaluation",

            "Monitor model drift and implement retraining strategies",

            "Stay current with latest research and evaluate new techniques"

        ],

        "required_skills": ["Python", "TensorFlow", "PyTorch", "Scikit-learn", "Deep Learning", "SQL", "Docker", "AWS"],

        "preferred_skills": ["Kubernetes", "MLOps", "Feature Stores", "Kubeflow", "Spark", "NLP", "Computer Vision", "MLflow"],

        "salary_estimate": {

            "usd": "$110,000 - $200,000",

            "inr": "G10,00,000 - G40,00,000",

            "eur": "G70,000 - G130,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $80K-$120K",

            "Mid-Level (2-5 years): $120K-$170K",

            "Senior (5-8 years): $170K-$230K",

            "Lead/Staff (8+ years): $220K-$350K+"

        ],

        "career_growth": [

            "Junior ML Engineer G Mid-Level ML Engineer",

            "Mid-Level G Senior ML Engineer",

            "Senior G Staff ML Engineer / ML Architect",

            "Staff G Director of ML / VP of AI",

            "Specialization paths: NLP, Computer Vision, MLOps, AI Platform, Research"

        ],

        "interview_topics": [

            "ML algorithms: supervised, unsupervised, reinforcement learning",

            "Deep learning architectures (CNNs, RNNs, Transformers)",

            "Feature engineering and data preprocessing",

            "Model evaluation, bias-variance tradeoff, regularization",

            "System design for ML systems",

            "ML pipeline design and MLOps practices",

            "Coding: Python, data structures, algorithms"

        ],

        "industry_demand": "Very High",

        "growth_outlook": "Exceptional G AI/ML is the most in-demand field in tech. Generative AI expertise commands premium compensation."

    },

    "data analyst": {

        "overview": "A Data Analyst interprets data to help organizations make informed business decisions. They collect, process, and analyze datasets, creating visualizations and reports that translate complex data into actionable insights for stakeholders across departments.",

        "responsibilities": [

            "Collect, clean, and transform raw data from multiple sources",

            "Perform statistical analysis to identify trends and patterns",

            "Create interactive dashboards and reports using BI tools",

            "Collaborate with stakeholders to understand business requirements",

            "Present findings and recommendations to management",

            "Maintain data quality and integrity across databases",

            "Automate recurring reports and data processes",

            "Support A/B testing and experimental analysis"

        ],

        "required_skills": ["SQL", "Excel", "Python", "Data Visualization", "Statistics", "Pandas", "Tableau", "Power BI"],

        "preferred_skills": ["R", "Google Analytics", "A/B Testing", "ETL", "Machine Learning basics", "Git", "BigQuery", "Looker"],

        "salary_estimate": {

            "usd": "$55,000 - $100,000",

            "inr": "G3,50,000 - G14,00,000",

            "eur": "G35,000 - G65,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $40K-$65K",

            "Mid-Level (2-5 years): $65K-$90K",

            "Senior (5-8 years): $90K-$125K",

            "Lead (8+ years): $115K-$160K+"

        ],

        "career_growth": [

            "Junior Data Analyst G Data Analyst",

            "Data Analyst G Senior Data Analyst",

            "Senior G Analytics Manager / Data Science Manager",

            "Specialization paths: Business Intelligence, Product Analytics, Marketing Analytics, Data Engineering"

        ],

        "interview_topics": [

            "SQL queries: joins, subqueries, window functions",

            "Statistical concepts: mean, median, standard deviation, hypothesis testing",

            "Data visualization best practices",

            "Excel advanced functions and pivot tables",

            "Python for data analysis (Pandas, NumPy)",

            "Business acumen and storytelling with data",

            "Data cleaning and wrangling techniques"

        ],

        "industry_demand": "High",

        "growth_outlook": "Strong G Every organization needs analysts to drive data-informed decisions. Entry point into data careers."

    },

    "ui/ux designer": {

        "overview": "A UI/UX Designer creates intuitive, engaging, and accessible digital experiences. They research user needs, design wireframes and prototypes, and collaborate with development teams to build interfaces that are both visually appealing and functionally effective. This role blends creativity with analytical thinking.",

        "responsibilities": [

            "Conduct user research: interviews, surveys, usability testing",

            "Create wireframes, prototypes, and high-fidelity mockups",

            "Design intuitive information architectures and user flows",

            "Build and maintain design systems and component libraries",

            "Collaborate closely with product managers and developers",

            "Analyze user behavior data to inform design decisions",

            "Ensure accessibility standards (WCAG) are met",

            "Present design concepts and rationale to stakeholders"

        ],

        "required_skills": ["Figma", "Adobe XD", "User Research", "Wireframing", "Prototyping", "HTML5", "CSS3", "Design Systems"],

        "preferred_skills": ["Sketch", "InVision", "Zeplin", "Usability Testing", "A/B Testing", "Animation", "Accessibility", "Design Thinking"],

        "salary_estimate": {

            "usd": "$70,000 - $130,000",

            "inr": "G4,00,000 - G16,00,000",

            "eur": "G42,000 - G80,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $45K-$75K",

            "Mid-Level (2-5 years): $75K-$110K",

            "Senior (5-8 years): $110K-$150K",

            "Lead/Principal (8+ years): $140K-$190K+"

        ],

        "career_growth": [

            "Junior UI/UX Designer G UX/UI Designer",

            "Designer G Senior UX Designer",

            "Senior G Design Lead / Design Manager",

            "Staff G Head of Design / VP of Design",

            "Specialization paths: UX Research, Interaction Design, Design Systems, Motion Design, Product Design"

        ],

        "interview_topics": [

            "Design process: research G wireframe G prototype G test",

            "User empathy and persona development",

            "Interaction design principles",

            "Visual design: typography, color theory, layout",

            "Portfolio presentation and design rationale",

            "Responsive and mobile-first design",

            "Accessibility and inclusive design"

        ],

        "industry_demand": "High",

        "growth_outlook": "Strong G User experience is a key differentiator. Companies invest heavily in design to retain users and improve conversion."

    },

    "ai engineer": {

        "overview": "An AI Engineer builds and integrates artificial intelligence systems into products and services. They combine software engineering with machine learning expertise to create intelligent features such as recommendation engines, natural language processing systems, computer vision applications, and generative AI solutions.",

        "responsibilities": [

            "Design and implement AI/ML models for production systems",

            "Build scalable AI inference pipelines and APIs",

            "Integrate LLMs and generative AI into applications",

            "Optimize model performance for latency and throughput",

            "Develop prompt engineering strategies for LLM applications",

            "Implement RAG (Retrieval-Augmented Generation) systems",

            "Monitor AI model performance and manage retraining cycles",

            "Evaluate and compare AI/ML tools and frameworks"

        ],

        "required_skills": ["Python", "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "NLP", "Docker", "REST API"],

        "preferred_skills": ["LangChain", "Hugging Face", "LLMs", "RAG", "Vector Databases", "Kubernetes", "AWS", "MLOps"],

        "salary_estimate": {

            "usd": "$100,000 - $190,000",

            "inr": "G8,00,000 - G38,00,000",

            "eur": "G65,000 - G120,000",

            "note": "Salaries vary significantly by location, company size, and experience level."

        },

        "experience_levels": [

            "Junior (0-2 years): $70K-$110K",

            "Mid-Level (2-5 years): $110K-$160K",

            "Senior (5-8 years): $160K-$220K",

            "Lead/Staff (8+ years): $200K-$320K+"

        ],

        "career_growth": [

            "Junior AI Engineer G AI Engineer",

            "AI Engineer G Senior AI Engineer",

            "Senior G Staff AI Engineer / AI Architect",

            "Staff G Director of AI / VP of AI",

            "Specialization paths: NLP, Computer Vision, Generative AI, AI Platform, AI Safety"

        ],

        "interview_topics": [

            "Machine learning fundamentals and algorithms",

            "Deep learning architectures and training strategies",

            "LLM integration patterns (RAG, fine-tuning, agents)",

            "System design for AI-powered applications",

            "Model evaluation and benchmarking",

            "AI ethics and responsible AI practices",

            "Software engineering best practices"

        ],

        "industry_demand": "Very High",

        "growth_outlook": "Exceptional G The AI revolution is creating unprecedented demand. Every company is exploring AI integration."

    },

}





# Aliases users commonly type G canonical guide key. Displayed titles

# always use the canonical name so different queries never show

# identical bodies under different titles.

ROLE_ALIASES: Dict[str, str] = {

    "python dev": "python developer",

    "py developer": "python developer",

    "django developer": "python developer",

    "flask developer": "python developer",

    "backend developer": "python developer",

    "backend dev": "python developer",

    "frontend dev": "frontend developer",

    "front end developer": "frontend developer",

    "front-end developer": "frontend developer",

    "react developer": "frontend developer",

    "angular developer": "frontend developer",

    "vue developer": "frontend developer",

    "fullstack developer": "full stack developer",

    "full-stack developer": "full stack developer",

    "full stack dev": "full stack developer",

    "mern developer": "full stack developer",

    "devops": "devops engineer",

    "sre": "devops engineer",

    "site reliability engineer": "devops engineer",

    "data science": "data scientist",

    "ml engineer": "machine learning engineer",

    "machine learning": "machine learning engineer",

    "data analysis": "data analyst",

    "bi analyst": "data analyst",

    "business intelligence analyst": "data analyst",

    "ux designer": "ui/ux designer",

    "ui designer": "ui/ux designer",

    "product designer": "ui/ux designer",

    "ux/ui designer": "ui/ux designer",

    "ai developer": "ai engineer",

    "genai engineer": "ai engineer",

    "llm engineer": "ai engineer",

    "deep learning engineer": "ai engineer",

    "dl engineer": "ai engineer",

    "computer vision engineer": "ai engineer",

    "nlp engineer": "ai engineer",

}





_generated_role_guides: Dict[str, Dict] = {}   # in-process cache





def _generate_role_guide_with_llm(role_name: str) -> Optional[Dict[str, Any]]:

    """Ask the LLM to generate a complete role guide for any role not in ROLE_GUIDES_DB.

    Returns None silently when LLM is unavailable so the caller falls back gracefully."""

    cache_key = role_name.lower().strip()

    if cache_key in _generated_role_guides:

        return _generated_role_guides[cache_key]



    try:

        llm = get_llm_provider()

        if not llm.health_check()["available"]:

            return None



        guide = llm.generate_json(

            f"Generate a comprehensive career role guide for: {role_name}\n\n"

            "Return a JSON object with exactly these keys:\n"

            "  role_title (string), overview (string, 3-4 sentences),\n"

            "  responsibilities (list of 6 strings),\n"

            "  required_skills (list of 6-8 skill name strings),\n"

            "  preferred_skills (list of 4-5 skill name strings),\n"

            "  salary_estimate: { usd: string, inr: string, eur: string },\n"

            "  experience_levels: list of {level, years, description} objects (3 items: Entry/Mid/Senior),\n"

            "  career_growth (list of 4 role title strings showing progression),\n"

            "  interview_topics (list of 5 topic strings),\n"

            "  industry_demand (one of: Low / Moderate / High / Very High),\n"

            "  growth_outlook (string, 1-2 sentences).\n"

            "Use realistic, current market data. Be specific to this role, not generic.",

            system_prompt=(

                "You are an expert technical career advisor with deep knowledge of the "

                "current job market. Generate accurate, specific, and useful career guides. "

                "Output ONLY valid JSON."

            ),

            max_tokens=900,

        )



        if not guide or not isinstance(guide, dict):

            return None



        guide["guide_available"] = True

        guide["generated"] = True  # flag so UI can optionally note it's AI-generated

        guide.setdefault("role_title", role_name)

        _generated_role_guides[cache_key] = guide

        return guide



    except Exception as exc:

        logger.warning("LLM role guide generation failed for '%s': %s", role_name, exc)

        return None





def get_role_guide(role: str) -> Dict[str, Any]:

    """Return the DISTINCT guide for a role G no shared generic copy.



    Rules:

    - exact match G that role's own curated guide verbatim;

    - known alias / unambiguous containment G that guide, but the

      displayed title keeps the canonical name so two different queries

      never show identical bodies under different titles;

    - anything else G honest "no dedicated guide yet" payload listing the

      roles that DO have guides, never a relabeled clone.

    """

    name = (role or "").strip()

    key = name.lower()



    def _with_title(guide_key):

        guide = dict(ROLE_GUIDES_DB[guide_key])

        guide["role_title"] = guide.get("role_title") or guide_key.title()

        guide["guide_available"] = True

        return guide



    if key in ROLE_GUIDES_DB:

        return _with_title(key)

    alias_target = ROLE_ALIASES.get(key)

    if alias_target and alias_target in ROLE_GUIDES_DB:

        return _with_title(alias_target)

    candidates = [k for k in ROLE_GUIDES_DB if key == k or key in k or k in key]

    if candidates:

        best = sorted(candidates, key=len, reverse=True)[0]

        return _with_title(best)



    # No curated guide exists G try to generate one via LLM.

    # This runs synchronously (adds ~2-3s on first call per role with Groq).

    # A simple in-process cache (_generated_role_guides) avoids re-calling

    # the LLM for the same role within a server session.

    llm_guide = _generate_role_guide_with_llm(name)

    if llm_guide:

        return llm_guide



    # Hard fallback: LLM also unavailable G honest generic guide with real

    # content so sections aren't empty, but clearly marked as generic.

    title = name or "Unknown role"

    return {

        "role_title": title,

        "overview": (

            f"{title} professionals design, build, and deliver technical solutions "

            "in their area of expertise. They collaborate with teams to solve complex "

            "problems and drive results through applied skill and domain knowledge."

        ),

        "responsibilities": [

            f"Design and implement {title.lower()} solutions",

            "Collaborate with cross-functional teams on deliverables",

            "Maintain and improve existing systems and processes",

            "Stay current with industry trends and best practices",

            "Contribute to technical documentation and knowledge sharing",

        ],

        "required_skills": ["Problem solving", "Communication", "Domain expertise", "Teamwork"],

        "preferred_skills": ["Leadership", "Mentoring", "System design", "Agile/Scrum"],

        "salary_estimate": {

            "usd": "$60,000 - $130,000",

            "inr": "G5,00,000 - G20,00,000",

            "eur": "G45,000 - G100,000",

        },

        "experience_levels": [

            {"level": "Entry", "years": "0-2", "description": "Learning fundamentals and building core skills"},

            {"level": "Mid", "years": "2-5", "description": "Independent contributor, owns features end-to-end"},

            {"level": "Senior", "years": "5+", "description": "Technical leadership, mentoring, system design"},

        ],

        "career_growth": [f"Senior {title}", f"Lead {title}", "Engineering Manager", "Principal/Staff Engineer"],

        "interview_topics": [

            "Core technical fundamentals",

            "Problem solving and algorithms",

            "System design basics",

            "Behavioral/STAR method questions",

            "Domain-specific concepts",

        ],

        "industry_demand": "Moderate to High",

        "growth_outlook": "Roles in this area are generally in demand across industries.",

        "guide_available": True,

        "generated": True,

    }





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




def get_role_skills(role: str) -> List[str]:

    """Get typical skills for a given role.



    Resolution mirrors get_role_guide (exact G alias G containment) and

    returns [] for unknown roles instead of a misleading shared fallback

    list that made every unknown role look identical.

    """

    role_lower = (role or "").lower().strip()



    role_skills_map = {

        "python developer": ["Python", "Django", "Flask", "FastAPI", "REST API", "PostgreSQL", "MySQL", "Git", "Docker", "AWS", "Redis", "Celery", "SQLAlchemy", "HTML5", "CSS3", "JavaScript"],

        "frontend developer": ["HTML5", "CSS3", "JavaScript", "TypeScript", "React", "Angular", "Vue.js", "Redux", "Webpack", "SASS", "Git", "REST API", "Responsive Design", "Testing"],

        "data scientist": ["Python", "R", "SQL", "Pandas", "NumPy", "Scikit-learn", "TensorFlow", "PyTorch", "Machine Learning", "Deep Learning", "Statistics", "Data Visualization", "Jupyter", "Feature Engineering", "NLP"],

        "full stack developer": ["JavaScript", "TypeScript", "React", "Node.js", "Express.js", "MongoDB", "PostgreSQL", "REST API", "GraphQL", "Docker", "AWS", "Git", "HTML5", "CSS3", "Redis"],

        "devops engineer": ["Docker", "Kubernetes", "Jenkins", "GitHub Actions", "Terraform", "Ansible", "AWS", "Azure", "GCP", "Linux", "Bash", "Python", "Prometheus", "Grafana", "CI/CD"],

        "mobile developer": ["React Native", "Flutter", "Swift", "Kotlin", "Android SDK", "iOS SDK", "Firebase", "REST API", "Git", "UI/UX", "Testing"],

        "machine learning engineer": ["Python", "TensorFlow", "PyTorch", "Scikit-learn", "Deep Learning", "NLP", "Computer Vision", "MLOps", "Docker", "Kubernetes", "AWS", "Feature Engineering", "Model Deployment", "SQL", "Pandas"],

        "blockchain developer": ["Solidity", "Ethereum", "Web3.js", "Smart Contracts", "JavaScript", "TypeScript", "Node.js", "React", "Rust", "Go", "Cryptography", "DeFi", "NFT", "IPFS"],

        "cloud architect": ["AWS", "Azure", "GCP", "Terraform", "Docker", "Kubernetes", "Networking", "Security", "Linux", "Python", "CI/CD", "Microservices", "Serverless", "Cost Optimization"],

        "product manager": ["Agile", "Scrum", "Jira", "SQL", "Data Analysis", "A/B Testing", "User Research", "Wireframing", "Stakeholder Management", "Roadmapping", "KPIs", "Market Research"],

        "data analyst": ["SQL", "Excel", "Python", "Pandas", "Tableau", "Power BI", "Statistics", "Data Visualization", "R", "Google Analytics", "A/B Testing", "ETL", "BigQuery", "Looker"],

        "ui/ux designer": ["Figma", "Adobe XD", "Sketch", "InVision", "User Research", "Wireframing", "Prototyping", "HTML5", "CSS3", "Design Systems", "Usability Testing", "Accessibility", "Design Thinking"],

        "ai engineer": ["Python", "TensorFlow", "PyTorch", "Scikit-learn", "Deep Learning", "NLP", "LangChain", "Hugging Face", "Docker", "Kubernetes", "AWS", "REST API", "LLMs", "Vector Databases", "RAG"]

    }



    if role_lower in role_skills_map:

        return role_skills_map[role_lower]

    alias_target = ROLE_ALIASES.get(role_lower)

    if alias_target and alias_target in role_skills_map:

        return role_skills_map[alias_target]

    for key, skills in role_skills_map.items():

        if key in role_lower or role_lower in key:

            return skills



    return []





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




def analyze_resume_text(text: str, target_role: str = "") -> Dict[str, Any]:

    """

    Advanced ATS Resume Analyzer with weighted scoring.

    Mimics real Applicant Tracking Systems like Jobscan/ResumeWorded.

    """

    resume_skills = _extract_skills_from_text(text)

    

    # Extract all text in lowercase for analysis

    text_lower = text.lower()

    words = text.split()

    word_count = len(words)

    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]

    avg_words_per_sentence = word_count / max(len(sentences), 1)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # SECTION DETECTION (Weight: 10%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    sections = {

        "contact": bool(re.search(r'[\w.-]+@[\w.-]+\.\w+', text)),

        "summary": bool(re.search(r'(summary|objective|profile|about\s+me|professional\s+summary)', text, re.I)),

        "experience": bool(re.search(r'(experience|work\s+history|employment|professional\s+experience)', text, re.I)),

        "education": bool(re.search(r'(education|degree|university|college|bachelor|master|phd|b\.tech|m\.tech)', text, re.I)),

        "skills": bool(re.search(r'(skills|technologies|technical\s+skills|core\s+competencies)', text, re.I)),

        "projects": bool(re.search(r'(projects|portfolio|personal\s+projects)', text, re.I)),

        "certifications": bool(re.search(r'(certification|certificate|certified|credentials)', text, re.I)),

        "achievements": bool(re.search(r'(achievements|accomplishments|awards)', text, re.I)),

    }

    

    section_score = 0

    if sections["contact"]: section_score += 2

    if sections["summary"]: section_score += 2

    if sections["experience"]: section_score += 2

    if sections["education"]: section_score += 1

    if sections["skills"]: section_score += 1.5

    if sections["projects"]: section_score += 1

    if sections["certifications"]: section_score += 0.5

    section_score = min(section_score, 10)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # CONTACT INFORMATION (Weight: 5%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    email_match = re.search(r'[\w.-]+@[\w.-]+\.\w+', text)

    phone_match = re.search(r'[\+]?[\d\s\-\(\)]{10,}', text)

    linkedin_match = re.search(r'linkedin\.com/in/[\w-]+', text, re.I)

    github_match = re.search(r'github\.com/[\w-]+', text, re.I)

    portfolio_match = re.search(r'(portfolio|website|blog)\.(com|io|dev|me|app)', text, re.I)

    

    contact = {

        "email": email_match.group() if email_match else None,

        "phone": phone_match.group().strip() if phone_match else None,

        "linkedin": linkedin_match.group() if linkedin_match else None,

        "github": github_match.group() if github_match else None,

        "portfolio": portfolio_match.group() if portfolio_match else None,

    }

    

    contact_score = 0

    if contact["email"]: contact_score += 1.5

    if contact["phone"]: contact_score += 1.5

    if contact["linkedin"]: contact_score += 1

    if contact["github"]: contact_score += 0.5

    if contact["portfolio"]: contact_score += 0.5

    contact_score = min(contact_score, 5)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # KEYWORD MATCH (Weight: 30%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    keyword_score = 0

    matched_keywords = []

    missing_keywords = []

    

    if target_role:

        role_skills = get_role_skills(target_role)

        role_keywords = [skill.lower() for skill in role_skills]

        

        # Count keyword matches

        matches = 0

        for keyword in role_keywords:

            if keyword in text_lower:

                matches += 1

                matched_keywords.append(keyword)

            else:

                missing_keywords.append(keyword)

        

        # Score based on match percentage

        if role_keywords:

            match_pct = matches / len(role_keywords)

            keyword_score = match_pct * 30

    else:

        # ========================================================================
# Role Guide Search API
# ========================================================================


        common_keywords = ['python', 'javascript', 'java', 'sql', 'git', 'docker', 'aws', 'react', 'node.js', 'api', 'agile', 'ci/cd']

        matches = sum(1 for kw in common_keywords if kw in text_lower)

        keyword_score = min(matches * 2, 30)

        matched_keywords = [kw for kw in common_keywords if kw in text_lower]



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # FORMATTING & READABILITY (Weight: 10%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    formatting_score = 0

    

    # Bullet points

    has_bullet_points = bool(re.search(r'[G\-\*]\s', text))

    if has_bullet_points:

        formatting_score += 3

    

    # Quantifiable achievements (numbers/metrics)

    has_numbers = bool(re.search(r'\d+', text))

    has_percentages = bool(re.search(r'\d+%', text))

    has_dollar_amounts = bool(re.search(r'\$[\d,]+', text))

    if has_numbers:

        formatting_score += 2

    if has_percentages or has_dollar_amounts:

        formatting_score += 2

    

    # Action verbs

    action_verbs = re.findall(

        r'\b(developed|implemented|designed|led|managed|created|built|improved|'

        r'reduced|increased|launched|optimized|delivered|achieved|engineered|'

        r'architected|spearheaded|orchestrated|streamlined|enhanced|drove)\b',

        text, re.I

    )

    if len(action_verbs) >= 5:

        formatting_score += 3

    elif len(action_verbs) >= 3:

        formatting_score += 2

    elif len(action_verbs) >= 1:

        formatting_score += 1

    

    formatting_score = min(formatting_score, 10)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # SKILLS MATCH (Weight: 15%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    skills_score = 0

    if resume_skills:

        # Score based on number of skills found

        if len(resume_skills) >= 15:

            skills_score = 15

        elif len(resume_skills) >= 10:

            skills_score = 12

        elif len(resume_skills) >= 5:

            skills_score = 8

        else:

            skills_score = 4

    

    # Bonus for technical skills

    technical_skills = [s for s in resume_skills if s in SKILLS_DATABASE.get('ai_ml', []) + 

                       SKILLS_DATABASE.get('cloud', []) + SKILLS_DATABASE.get('devops', [])]

    if len(technical_skills) >= 5:

        skills_score = min(skills_score + 2, 15)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # EXPERIENCE RELEVANCE (Weight: 20%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    experience_score = 0

    if sections["experience"]:

        # Check for experience indicators

        exp_indicators = re.findall(r'\d+\+?\s*(years?|yrs?|months?)', text, re.I)

        if exp_indicators:

            experience_score += 5

        

        # Check for job titles

        job_titles = re.findall(r'\b(engineer|developer|manager|analyst|designer|architect|lead|senior|junior)\b', text, re.I)

        if len(job_titles) >= 3:

            experience_score += 5

        elif len(job_titles) >= 1:

            experience_score += 3

        

        # Check for company names or work descriptions

        if re.search(r'(company|inc|corp|technologies|solutions|labs)', text, re.I):

            experience_score += 5

        else:

            experience_score += 2

        

        experience_score = min(experience_score, 20)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # EDUCATION (Weight: 5%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    education_score = 0

    if sections["education"]:

        education_score = 3

        

        # Bonus for degree level

        if re.search(r'\b(phd|doctorate|doctoral)\b', text, re.I):

            education_score = 5

        elif re.search(r'\b(master|m\.tech|mba|msc|ma)\b', text, re.I):

            education_score = 4.5

        elif re.search(r'\b(bachelor|b\.tech|bsc|ba|bs)\b', text, re.I):

            education_score = 4

        

        # Bonus for relevant certifications

        if sections["certifications"]:

            education_score = min(education_score + 1, 5)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # PROJECTS & ACHIEVEMENTS (Weight: 10%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    projects_score = 0

    if sections["projects"]:

        projects_score += 5

        

        # Check for project details

        project_count = len(re.findall(r'project', text, re.I))

        if project_count >= 3:

            projects_score += 3

        elif project_count >= 1:

            projects_score += 2

        

        # Check for technologies used in projects

        if re.search(r'(technologies|tech\s+stack|built\s+with|using)', text, re.I):

            projects_score += 2

    

    if sections["achievements"]:

        projects_score = min(projects_score + 2, 10)

    

    projects_score = min(projects_score, 10)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ========================================================================
# Role Guide Search API
# ========================================================================


    grammar_score = 10  # Start with perfect score

    

    # Check for common grammar issues

    grammar_issues = []

    

    # Repeated words

    repeated_words = re.findall(r'\b(\w+)\s+\1\b', text, re.I)

    if repeated_words:

        grammar_score -= 1

        grammar_issues.append("Repeated words detected")

    

    # Very long sentences (>30 words)

    long_sentences = [s for s in sentences if len(s.split()) > 30]

    if len(long_sentences) > 3:

        grammar_score -= 2

        grammar_issues.append("Too many long sentences")

    

    # Very short sentences (<3 words) - might indicate fragments

    short_sentences = [s for s in sentences if 0 < len(s.split()) < 3]

    if len(short_sentences) > 5:

        grammar_score -= 1

        grammar_issues.append("Too many sentence fragments")

    

    # Check for professional language

    unprofessional_words = re.findall(r'\b(um|uh|like|basically|stuff|things)\b', text, re.I)

    if len(unprofessional_words) > 3:

        grammar_score -= 2

        grammar_issues.append("Informal language detected")

    

    grammar_score = max(grammar_score, 0)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # RESUME LENGTH (Weight: 5%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    length_score = 0

    if 400 <= word_count <= 800:

        length_score = 5  # Optimal

    elif 300 <= word_count <= 1000:

        length_score = 4  # ========================================================================
# Role Guide Search API
# ========================================================================


    elif 200 <= word_count <= 1200:

        length_score = 3  # Acceptable

    elif word_count < 200:

        length_score = 1  # Too short

    else:

        length_score = 2  # Too long



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ATS COMPATIBILITY (Weight: 5%)

    # ========================================================================
# Role Guide Search API
# ========================================================================


    ats_score = 0

    

    # Check for ATS-friendly formatting

    ats_issues = []

    

    # No tables (simple check)

    if re.search(r'\|.*\|', text):

        ats_issues.append("Tables detected - may not parse well in ATS")

    

    # No special characters in headers

    if re.search(r'[^\w\s\-\.\,\:\;\(\)\/]', text[:500]):

        ats_issues.append("Special characters in header section")

    

    # Standard section headers

    standard_headers = ['experience', 'education', 'skills', 'summary', 'objective']

    has_standard_headers = sum(1 for header in standard_headers if re.search(header, text_lower))

    if has_standard_headers >= 3:

        ats_score += 3

    else:

        ats_issues.append("Non-standard section headers")

    

    # Plain text format

    if not re.search(r'<[^>]+>', text):  # No HTML tags

        ats_score += 2

    

    ats_score = min(ats_score, 5)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # CALCULATE TOTAL SCORE

    # ========================================================================
# Role Guide Search API
# ========================================================================


    total_score = (

        section_score +           # 10%

        contact_score +           # 5%

        keyword_score +           # 30%

        skills_score +            # 15%

        experience_score +        # 20%

        education_score +         # 5%

        projects_score +          # 10%

        grammar_score +           # 10%

        length_score +            # 5%

        ats_score                 # 5%

    )

    

    ats_score = min(max(round(total_score), 0), 100)



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ========================================================================
# Role Guide Search API
# ========================================================================


    ats_breakdown = {

        "sections": round(section_score, 1),

        "contact_info": round(contact_score, 1),

        "keyword_match": round(keyword_score, 1),

        "skills_match": round(skills_score, 1),

        "experience": round(experience_score, 1),

        "education": round(education_score, 1),

        "projects_achievements": round(projects_score, 1),

        "grammar_language": round(grammar_score, 1),

        "length": round(length_score * 2, 1),  # Scale to 10

        "ats_compatibility": round(ats_score * 2, 1),  # Scale to 10

    }



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # IDENTIFY STRENGTHS

    # ========================================================================
# Role Guide Search API
# ========================================================================


    strengths = []

    if len(resume_skills) >= 10:

        strengths.append(f"Strong technical skill set with {len(resume_skills)} identified skills")

    if sections["experience"] and experience_score >= 15:

        strengths.append("Well-detailed work experience section")

    if len(action_verbs) >= 5:

        strengths.append(f"Excellent use of action verbs ({len(action_verbs)} found)")

    if has_percentages or has_dollar_amounts:

        strengths.append("Includes quantifiable achievements with metrics")

    if contact["linkedin"]:

        strengths.append("LinkedIn profile included for professional networking")

    if contact["github"]:

        strengths.append("GitHub profile showcases code samples and projects")

    if sections["projects"] and projects_score >= 7:

        strengths.append("Strong projects section demonstrating practical skills")

    if sections["certifications"]:

        strengths.append("Certifications add credibility")

    if grammar_score >= 8:

        strengths.append("Professional language and good grammar")

    if 400 <= word_count <= 800:

        strengths.append("Optimal resume length (400-800 words)")

    if keyword_score >= 20:

        strengths.append(f"Excellent keyword match ({len(matched_keywords)} keywords matched)")



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # IDENTIFY WEAKNESSES & MISSING ITEMS

    # ========================================================================
# Role Guide Search API
# ========================================================================


    weaknesses = []

    missing_items = []

    

    if not sections["summary"]:

        missing_items.append("Professional summary/objective")

        weaknesses.append("Missing professional summary")

    if not sections["skills"]:

        missing_items.append("Dedicated skills section")

        weaknesses.append("No dedicated skills section")

    if not sections["projects"]:

        missing_items.append("Projects section")

        weaknesses.append("Missing projects section")

    if not sections["certifications"]:

        missing_items.append("Certifications section")

    if not contact["linkedin"]:

        missing_items.append("LinkedIn profile URL")

    if not contact["github"]:

        missing_items.append("GitHub profile URL")

    if not has_bullet_points:

        missing_items.append("Bullet-point formatting")

        weaknesses.append("No bullet points - difficult to scan")

    if not has_numbers:

        missing_items.append("Quantifiable achievements")

        weaknesses.append("Lacks quantifiable metrics")

    if len(action_verbs) < 3:

        missing_items.append("Action verbs")

        weaknesses.append("Insufficient use of action verbs")

    if word_count < 300:

        missing_items.append("More content")

        weaknesses.append("Resume appears too short")

    if word_count > 1200:

        missing_items.append("Concise content")

        weaknesses.append("Resume may be too long")

    if not contact["phone"]:

        missing_items.append("Phone number")

    if grammar_score < 7:

        weaknesses.append("Grammar and language improvements needed")

    if ats_score < 4:

        weaknesses.append("ATS compatibility issues detected")



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ========================================================================
# Role Guide Search API
# ========================================================================


    # ========================================================================
# Role Guide Search API
# ========================================================================


    suggestions = []

    

    if not sections["summary"]:

        suggestions.append({

            "section": "Professional Summary",

            "current": "Not found",

            "improvement": "Add a 2-3 line professional summary at the top highlighting your key skills, experience, and career objectives",

            "priority": "High",

            "impact": "+8% ATS score"

        })

    

    if not has_bullet_points:

        suggestions.append({

            "section": "Formatting",

            "current": "No bullet points detected",

            "improvement": "Use bullet points (G) to list achievements and responsibilities. ATS systems and recruiters prefer scannable formats.",

            "priority": "High",

            "impact": "+5% ATS score"

        })

    

    if not has_numbers:

        suggestions.append({

            "section": "Achievements",

            "current": "No quantifiable metrics found",

            "improvement": "Add numbers and metrics to demonstrate impact (e.g., 'Increased performance by 40%', 'Managed team of 8', 'Reduced costs by $50K')",

            "priority": "High",

            "impact": "+7% ATS score"

        })

    

    if len(action_verbs) < 3:

        suggestions.append({

            "section": "Action Verbs",

            "current": f"Only {len(action_verbs)} action verbs found",

            "improvement": "Start bullet points with strong action verbs: Developed, Implemented, Led, Optimized, Architected, Spearheaded, Drove",

            "priority": "High",

            "impact": "+5% ATS score"

        })

    

    if not sections["projects"]:

        suggestions.append({

            "section": "Projects",

            "current": "No projects section",

            "improvement": "Add 2-3 relevant projects with: project name, technologies used, your role, and measurable outcomes",

            "priority": "Medium",

            "impact": "+6% ATS score"

        })

    

    if not contact["linkedin"]:

        suggestions.append({

            "section": "LinkedIn Profile",

            "current": "Not included",

            "improvement": "Add your LinkedIn profile URL to enhance professional presence and networking opportunities",

            "priority": "Medium",

            "impact": "+2% ATS score"

        })

    

    if not contact["github"]:

        suggestions.append({

            "section": "GitHub Profile",

            "current": "Not included",

            "improvement": "Include GitHub profile to showcase code samples, contributions, and projects (especially for technical roles)",

            "priority": "Medium",

            "impact": "+2% ATS score"

        })

    

    if not sections["certifications"]:

        suggestions.append({

            "section": "Certifications",

            "current": "No certifications listed",

            "improvement": "Add relevant certifications (AWS, Google Cloud, Azure, Coursera, edX) to boost credibility",

            "priority": "Medium",

            "impact": "+3% ATS score"

        })

    

    if word_count < 300:

        suggestions.append({

            "section": "Resume Length",

            "current": f"Only {word_count} words",

            "improvement": "Expand to 400-800 words with more details about experience, skills, and achievements",

            "priority": "Medium",

            "impact": "+4% ATS score"

        })

    

    if keyword_score < 15 and target_role:

        suggestions.append({

            "section": "Keywords",

            "current": f"Only {len(matched_keywords)} keywords matched",

            "improvement": f"Include these missing keywords from job description: {', '.join(missing_keywords[:5])}",

            "priority": "High",

            "impact": "+15% ATS score"

        })



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # SKILL GAP ANALYSIS

    # ========================================================================
# Role Guide Search API
# ========================================================================


    skill_gap = {}

    if target_role:

        role_skills = get_role_skills(target_role)

        possessed = [s for s in resume_skills if s.lower() in {r.lower() for r in role_skills}]

        missing_skills = [s for s in role_skills if s.lower() not in {r.lower() for r in resume_skills}]

        skill_gap = {

            "target_role": target_role,

            "required_skills": role_skills,

            "possessed": possessed,

            "missing": missing_skills,

            "match_percentage": round(len(possessed) / max(len(role_skills), 1) * 100, 1)

        }



    # ========================================================================
# Role Guide Search API
# ========================================================================


    # RANKING

    # ========================================================================
# Role Guide Search API
# ========================================================================


    if ats_score >= 85:

        ranking = "Excellent"

        ranking_description = "Your resume is well-optimized and should pass most ATS systems"

    elif ats_score >= 70:

        ranking = "Good"

        ranking_description = "Your resume is solid but has room for improvement"

    elif ats_score >= 55:

        ranking = "Average"

        ranking_description = "Your resume needs several improvements to be competitive"

    elif ats_score >= 40:

        ranking = "Below Average"

        ranking_description = "Significant improvements needed to pass ATS screening"

    else:

        ranking = "Poor"

        ranking_description = "Major revisions required - unlikely to pass ATS systems"



    return {

        "ats_score": ats_score,

        "ranking": ranking,

        "ranking_description": ranking_description,

        "ats_breakdown": ats_breakdown,

        "sections_detected": sections,

        "contact_info": contact,

        "resume_skills": resume_skills,

        "matched_keywords": matched_keywords,

        "missing_keywords": missing_keywords[:10],  # Top 10 missing

        "word_count": word_count,

        "sentence_count": len(sentences),

        "avg_words_per_sentence": round(avg_words_per_sentence, 1),

        "action_verbs_found": len(action_verbs),

        "action_verbs_list": list(set([v.lower() for v in action_verbs]))[:10],

        "strengths": strengths,

        "weaknesses": weaknesses,

        "missing_items": missing_items,

        "suggestions": suggestions,

        "skill_gap": skill_gap,

        "readability": {

            "avg_words_per_sentence": round(avg_words_per_sentence, 1),

            "total_words": word_count,

            "total_sentences": len(sentences),

            "reading_level": "Easy" if avg_words_per_sentence < 15 else "Moderate" if avg_words_per_sentence < 20 else "Difficult"

        },

        "ats_issues": ats_issues,

        "grammar_issues": grammar_issues

    }





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




INTERVIEW_QUESTIONS = {

    "python developer": {

        "technical": [

            {"q": "What are Python decorators and how do you use them?", "tips": "Explain function decorators, class decorators, and practical use cases like @staticmethod, @property, and custom decorators for logging/authentication."},

            {"q": "Explain the difference between deepcopy and shallow copy in Python.", "tips": "Shallow copy creates a new object but references nested objects. Deep copy recursively copies all nested objects. Use copy module."},

            {"q": "What are generators and how are they different from iterators?", "tips": "Generators use yield keyword, are lazy-evaluated, memory efficient. Iterators implement __iter__ and __next__. Generators are a simpler way to create iterators."},

            {"q": "Explain the GIL (Global Interpreter Lock) in Python.", "tips": "GIL is a mutex that allows only one thread to execute Python bytecode at a time. It limits multi-threading for CPU-bound tasks but doesn't affect I/O-bound tasks or multiprocessing."},

            {"q": "How does memory management work in Python?", "tips": "Python uses reference counting + cyclic garbage collector. del reduces reference count. gc module provides access to collector. Uses private heap for memory allocation."},

            {"q": "Explain async/await in Python.", "tips": "asyncio provides concurrency for I/O-bound code. await suspends coroutine execution. asyncio.gather() runs multiple coroutines. Great for API calls, file I/O."},

            {"q": "What are the SOLID principles and how do they apply in Python?", "tips": "Single Responsibility, Open-Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. Show examples with Python classes."},

            {"q": "Explain dependency injection and its benefits.", "tips": "Passing dependencies as parameters rather than hard-coding. Improves testability, flexibility, and follows DIP. Show a simple example."},

            {"q": "Design a RESTful API for a library management system using Flask.", "tips": "Cover proper route design, HTTP methods, request validation, error handling, and database models."},

        ],

        "hr": [

            {"q": "Why do you want to work here?", "tips": "Research the company's products, culture, and recent news. Connect your skills to their needs. Show genuine interest."},

            {"q": "Tell me about a challenging project you worked on.", "tips": "Use STAR method. Describe the Situation, Task, Action, and Result. Focus on your problem-solving skills."},

            {"q": "Where do you see yourself in 5 years?", "tips": "Show ambition aligned with the company's growth path. Mention leadership and technical growth goals."},

            {"q": "How do you handle tight deadlines?", "tips": "Give specific examples. Mention prioritization, communication, and breaking down tasks."},

        ],

        "coding": [

            {"q": "Write a function to find the longest substring without repeating characters.", "tips": "Sliding window approach with a set or dictionary. Time O(n). Intermediate level."},

            {"q": "Implement a LRU Cache.", "tips": "Use OrderedDict from collections or doubly linked list + hashmap. Support get() and put() in O(1). Advanced level."},

            {"q": "Write a function to merge two sorted linked lists.", "tips": "Use dummy node technique. Compare heads, attach smaller. Handle edge cases. Beginner level."},

            {"q": "Design a rate limiter.", "tips": "Discuss token bucket, sliding window, or fixed window algorithms. Consider concurrency. Advanced level."},

            {"q": "Write a function to check if two strings are anagrams.", "tips": "Compare sorted strings or use character count dictionary. O(n log n) or O(n). Beginner level."},

        ],

        "behavioral": [

            {"q": "Describe a time when you had a conflict with a team member.", "tips": "Focus on resolution, communication, and what you learned. Show emotional intelligence."},

            {"q": "Tell me about a time you failed and what you learned.", "tips": "Be honest, show self-awareness, and emphasize the lessons learned and improvements made."},

            {"q": "How do you stay updated with new technologies?", "tips": "Mention blogs, courses, open source contributions, side projects, and tech communities."},

        ]

    },

    "frontend developer": {

        "technical": [

            {"q": "Explain the virtual DOM and how React uses it.", "tips": "Virtual DOM is a lightweight copy of real DOM. React compares (diffs) virtual DOM with previous version and updates only changed parts (reconciliation)."},

            {"q": "What is the difference between CSS Grid and Flexbox?", "tips": "Flexbox is 1D (row or column). Grid is 2D (rows and columns). Use Flexbox for component layouts, Grid for page layouts."},

            {"q": "Explain closures in JavaScript with examples.", "tips": "A closure is a function that remembers its lexical scope. Common use: data privacy, function factories, event handlers, callbacks."},

            {"q": "What are Web Workers and when would you use them?", "tips": "Web Workers run JavaScript in background threads. Use for CPU-intensive tasks like data processing, without blocking the main thread."},

            {"q": "Explain event delegation and why it's useful.", "tips": "Attach a single event listener to a parent element instead of multiple children. Uses event bubbling. More memory efficient, works with dynamic elements."},

            {"q": "What is the difference between var, let, and const?", "tips": "var is function-scoped with hoisting. let is block-scoped, can be reassigned. const is block-scoped, cannot be reassigned (but objects can be mutated)."},

            {"q": "How does CSS specificity work?", "tips": "Inline > IDs (#) > Classes (.) > Elements. Important (!important) overrides specificity. Use specificity calculators for complex cases."},

            {"q": "Explain the component lifecycle in React.", "tips": "Mounting (constructor, render, componentDidMount), Updating (shouldComponentUpdate, render, componentDidUpdate), Unmounting (componentWillUnmount). Use hooks equivalents."},

            {"q": "What are React hooks and what problems do they solve?", "tips": "Hooks let you use state and lifecycle features in functional components. useState, useEffect, useContext eliminate class complexity and promote code reuse."},

        ],

        "hr": [

            {"q": "Why are you interested in frontend development?", "tips": "Talk about passion for user experience, visual creativity, and the intersection of design and engineering."},

            {"q": "How do you handle feedback on your designs/code?", "tips": "Show openness to constructive criticism, mention specific examples where feedback improved your work."},

        ],

        "coding": [

            {"q": "Build a debounce function in JavaScript.", "tips": "Use setTimeout and clearTimeout. Return a function that delays execution until after wait ms of no invocations. Intermediate level."},

            {"q": "Implement a simple todo list with React.", "tips": "Use useState for state management, implement add, delete, toggle complete. Consider useReducer. Intermediate level."},

            {"q": "Write CSS for a responsive card grid without media queries.", "tips": "Use CSS Grid with auto-fit and minmax(). Example: grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)). Intermediate level."},

            {"q": "Implement a promise-based retry mechanism.", "tips": "Wrap fetch in a retry function that catches errors and retries up to N times with exponential backoff. Advanced level."},

            {"q": "Build an accordion component with vanilla JS.", "tips": "Use event delegation on a container, toggle active class, animate max-height. Beginner level."},

        ],

        "behavioral": [

            {"q": "How do you approach responsive design?", "tips": "Mobile-first approach, use CSS Grid/Flexbox, test across devices, consider accessibility."},

            {"q": "How do you ensure cross-browser compatibility?", "tips": "Use feature detection, polyfills, vendor prefixes, and test on multiple browsers and devices."},

        ]

    },

    "data scientist": {

        "technical": [

            {"q": "Explain the bias-variance tradeoff.", "tips": "Bias = error from oversimplified model. Variance = error from sensitivity to training data. Goal is to find the sweet spot that minimizes total error."},

            {"q": "What is regularization and why is it used?", "tips": "Regularization prevents overfitting by adding penalty term. L1 (Lasso) promotes sparsity. L2 (Ridge) shrinks coefficients. Elastic Net combines both."},

            {"q": "Explain cross-validation.", "tips": "K-fold CV splits data into K subsets, trains on K-1, tests on 1. Stratified CV maintains class distribution. Reduces overfitting and gives robust evaluation."},

            {"q": "What is the difference between supervised and unsupervised learning?", "tips": "Supervised: labeled data, predicts outcomes (classification/regression). Unsupervised: no labels, finds patterns (clustering, dimensionality reduction)."},

            {"q": "How do you handle imbalanced datasets?", "tips": "SMOTE, undersampling, oversampling, class weights, ensemble methods, threshold adjustment, appropriate metrics (F1, AUC-ROC instead of accuracy)."},

            {"q": "Explain PCA (Principal Component Analysis).", "tips": "Dimensionality reduction technique. Finds orthogonal components of maximum variance. Use for visualization, noise reduction, feature compression."},

            {"q": "What evaluation metrics would you use for a classification problem?", "tips": "Accuracy, precision, recall, F1-score, AUC-ROC, log loss. Choose based on class balance problem cost."},

            {"q": "Explain the difference between bagging and boosting.", "tips": "Bagging trains models in parallel, averages results (Random Forest). Boosting trains sequentially, correcting errors (XGBoost, AdaBoost)."},

        ],

        "hr": [

            {"q": "Tell me about a data science project you're proud of.", "tips": "Use STAR method. Emphasize business impact, technical approach, and lessons learned."},

            {"q": "How do you prioritize which problems to solve with ML?", "tips": "Evaluate business impact, data availability, feasibility, and ROI. Start with quick wins."},

        ],

        "coding": [

            {"q": "Write SQL to find the top 5 customers by total spending.", "tips": "Use GROUP BY, SUM(), ORDER BY DESC, LIMIT. Handle NULL values. Consider window functions. Intermediate level."},

            {"q": "Implement linear regression from scratch in Python.", "tips": "Use gradient descent or normal equation. Implement fit() and predict() methods. Include loss calculation. Advanced level."},

            {"q": "Write a function to clean a dataset with missing values.", "tips": "Check for nulls, decide imputation strategy (mean, median, mode, forward-fill), handle outliers. Beginner level."},

        ],

        "behavioral": [

            {"q": "How do you explain technical concepts to non-technical stakeholders?", "tips": "Use analogies, visualizations, focus on business impact rather than technical details."},

            {"q": "How do you validate that your model is production-ready?", "tips": "A/B testing, offline metrics, shadow deployment, monitoring for drift, performance benchmarks."},

        ]

    },

    "data analyst": {

        "technical": [

            {"q": "Explain the difference between INNER JOIN, LEFT JOIN, and FULL OUTER JOIN.", "tips": "INNER JOIN returns matching rows. LEFT JOIN returns all left table rows. FULL OUTER JOIN returns all rows from both. Use Venn diagrams to explain."},

            {"q": "What are window functions in SQL? Give an example.", "tips": "Window functions perform calculations across rows related to current row. ROW_NUMBER(), RANK(), SUM() OVER(PARTITION BY)."},

            {"q": "How do you handle missing or inconsistent data in a dataset?", "tips": "Identify nulls, decide imputation strategy (mean, median, mode), remove or flag outliers, standardize formats, document data quality issues."},

            {"q": "Explain the difference between descriptive and inferential statistics.", "tips": "Descriptive summarizes data (mean, median, std dev). Inferential draws conclusions from samples (hypothesis testing, confidence intervals)."},

            {"q": "What is a pivot table and how do you use it in Excel?", "tips": "Pivot tables summarize large datasets by rows, columns, and values. Drag fields to filter, group, and aggregate data interactively."},

            {"q": "How do you create a dashboard in Power BI?", "tips": "Connect to data sources, build data model with relationships, create measures (DAX), design visualizations, publish and share."},

            {"q": "What is the difference between correlation and causation?", "tips": "Correlation measures association. Causation means one variable directly affects another. Spurious correlations can mislead. Use controlled experiments for causation."},

            {"q": "How would you analyze A/B test results?", "tips": "Define null and alternative hypotheses, set significance level, calculate p-value, check for practical significance, consider sample size and duration."},

        ],

        "hr": [

            {"q": "Tell me about a time your analysis drove a business decision.", "tips": "Use STAR method. Describe the business question, data sources, analysis approach, and the impact on decision-making."},

            {"q": "How do you ensure data accuracy in your reports?", "tips": "Validate data sources, cross-check with raw data, write unit tests for transformations, document assumptions, peer review."},

        ],

        "coding": [

            {"q": "Write a SQL query to find duplicate email addresses in a users table.", "tips": "Use GROUP BY and HAVING COUNT(*) > 1. Beginner level."},

            {"q": "Write a Python function to clean and normalize a phone number column.", "tips": "Remove non-digit characters, check length, apply country code, handle edge cases. Intermediate level."},

            {"q": "Write SQL to calculate the running total of sales by date.", "tips": "Use SUM() OVER(ORDER BY date) window function. Intermediate level."},

        ],

        "behavioral": [

            {"q": "How do you handle conflicting requirements from stakeholders?", "tips": "Listen to all parties, clarify objectives, propose data-backed tradeoffs, find common ground."},

            {"q": "Describe a time you found an important insight that others missed.", "tips": "Show curiosity, thoroughness, and the ability to dig deeper into data beyond surface-level analysis."},

        ]

    },

    "ui/ux designer": {

        "technical": [

            {"q": "Explain the difference between a design system and a component library.", "tips": "Design system includes principles, guidelines, tokens, and patterns. Component library is the coded implementation. Systems ensure consistency at scale."},

            {"q": "What is the design thinking process?", "tips": "Empathize, Define, Ideate, Prototype, Test. It's a human-centered approach to problem-solving that iterates based on user feedback."},

            {"q": "How do you conduct user research and what methods do you use?", "tips": "Interviews, surveys, usability testing, card sorting, A/B testing, analytics review. Choose method based on research goals and stage."},

            {"q": "What is WCAG and why is accessibility important in design?", "tips": "WCAG provides guidelines for making content accessible to people with disabilities. Covers perceivable, operable, understandable, robust principles."},

            {"q": "How do you create and use a Figma component variant?", "tips": "Create a component, add properties (size, state, type), configure variants in the properties panel. Use variants for consistent, scalable design."},

            {"q": "Explain the concept of information architecture.", "tips": "Organization, labeling, and structure of content. Includes card sorting, sitemaps, navigation design, and search systems for findability."},

            {"q": "What is the difference between usability testing and user acceptance testing?", "tips": "Usability testing evaluates if design is easy to use. UAT validates if product meets business requirements. Different goals, different participants."},

            {"q": "How do you design for different screen sizes and devices?", "tips": "Use responsive design, fluid grids, flexible images, media queries. Design mobile-first then scale up. Test on real devices."},

        ],

        "hr": [

            {"q": "Tell me about a project where you improved the user experience significantly.", "tips": "Show your process: research, problem identification, design solution, testing results, and measurable improvements."},

            {"q": "How do you handle feedback that conflicts with your design decisions?", "tips": "Listen actively, ask clarifying questions, explain design rationale with data/research, be open to compromise."},

        ],

        "coding": [

            {"q": "Write CSS for a responsive two-column layout that stacks on mobile.", "tips": "Use CSS Grid or Flexbox with media query. grid-template-columns: 1fr 1fr; @media max-width: breakpoint to single column. Beginner level."},

            {"q": "Create a Figma auto-layout frame with nested elements.", "tips": "Use auto-layout for padding, spacing, and resizing. Nest frames for complex layouts. Set horizontal/vertical padding and gap. Intermediate level."},

        ],

        "behavioral": [

            {"q": "How do you balance user needs with business goals?", "tips": "Find win-win solutions. Use research to show how user-centric designs drive business metrics. Prioritize features that serve both."},

            {"q": "Describe a time you had to advocate for the user.", "tips": "Show how you used research/data to persuade stakeholders to prioritize user needs over assumptions."},

        ]

    },

    "full stack developer": {

        "technical": [

            {"q": "Explain the MVC architecture pattern.", "tips": "Model handles data, View handles UI, Controller handles logic/routing. Discuss how it separates concerns in web applications."},

            {"q": "What is CORS and how do you handle it?", "tips": "Cross-Origin Resource Sharing. Server sets Access-Control-Allow-Origin headers. Handle with middleware, configure origins for security."},

            {"q": "How do you optimize database queries for performance?", "tips": "Use indexes, avoid SELECT *, use JOINs efficiently, optimize queries with EXPLAIN, implement caching (Redis), paginate results."},

            {"q": "Explain the difference between REST and GraphQL.", "tips": "REST has fixed endpoints per resource. GraphQL has a single endpoint, client specifies exact data needed. GraphQL reduces over-fetching."},

            {"q": "How do you handle authentication in a web application?", "tips": "JWT tokens for stateless auth, session-based for server-side. Store tokens securely, implement refresh tokens, use HTTPS, hash passwords."},

            {"q": "What is the difference between SQL and NoSQL databases?", "tips": "SQL: structured schema, ACID compliant, joins. NoSQL: flexible schema, horizontal scaling, document/key-value/graph. Choose based on data needs."},

            {"q": "Explain how you would deploy a full-stack application.", "tips": "CI/CD pipeline, containerization with Docker, cloud provider (AWS/GCP/Azure), environment variables, health checks, monitoring."},

        ],

        "hr": [

            {"q": "Why do you prefer full-stack development over specialization?", "tips": "Enjoy end-to-end ownership, versatility, ability to see the big picture, valuable in startups and small teams."},

            {"q": "How do you stay productive when context-switching between frontend and backend?", "tips": "Block time for each, use task management, maintain clear APIs between layers, write documentation."},

        ],

        "coding": [

            {"q": "Build a simple CRUD API with Express.js for a todo list.", "tips": "Set up routes, use body-parser, connect to database, implement validation. Intermediate level."},

            {"q": "Write a function to flatten a nested array.", "tips": "Use recursion or reduce with concat. Handle different nesting depths. Beginner level."},

            {"q": "Design a URL shortener system.", "tips": "Hash function, store mapping in database, handle collisions, redirect with 301. Consider scalability. Advanced level."},

        ],

        "behavioral": [

            {"q": "Describe a full-stack feature you built end-to-end.", "tips": "Show ownership from database design to UI implementation. Discuss technical decisions, tradeoffs, and results."},

            {"q": "How do you approach debugging a complex issue that spans frontend and backend?", "tips": "Reproduce the issue, check network requests/logs, isolate the layer, use debugging tools, test fix in isolation."},

        ]

    },

    "devops engineer": {

        "technical": [

            {"q": "Explain CI/CD pipeline design and its benefits.", "tips": "CI: automatically build and test on every commit. CD: automatically deploy to staging/production. Reduces manual errors, speeds releases, improves quality."},

            {"q": "What is containerization and how does Docker work?", "tips": "Docker packages apps with dependencies into containers. Shares host OS kernel, isolated filesystem. Uses Dockerfile to define images."},

            {"q": "Explain Kubernetes architecture.", "tips": "Master node (API server, scheduler, controller manager) manages worker nodes (kubelet, kube-proxy). Pods are smallest deployable units."},

            {"q": "What is Infrastructure as Code and why is it important?", "tips": "Managing infrastructure through configuration files (Terraform, CloudFormation). Enables versioning, repeatability, automation, and disaster recovery."},

            {"q": "How do you monitor system health and set up alerts?", "tips": "Use Prometheus for metrics, Grafana for dashboards, alerting rules for threshold breaches. Set up PagerDuty/OpsGenie for on-call."},

            {"q": "Explain the concept of blue-green deployment.", "tips": "Two identical environments (blue and green). Route traffic to one while updating the other. Switch traffic after validation. Zero-downtime deployment."},

            {"q": "How do you handle secrets management?", "tips": "Use vault (HashiCorp), AWS Secrets Manager, encrypted environment variables, Kubernetes secrets. Never hard-code or commit secrets."},

        ],

        "hr": [

            {"q": "How do you handle on-call incidents and post-mortems?", "tips": "Follow incident response runbook, communicate status, fix or mitigate, conduct blameless post-mortem, implement preventive measures."},

            {"q": "How do you balance developer velocity with system stability?", "tips": "Implement feature flags, canary releases, automated testing, gradual rollouts, monitoring, and rollback plans."},

        ],

        "coding": [

            {"q": "Write a Dockerfile for a Python Flask application.", "tips": "Use multi-stage builds, copy requirements first for caching, use slim base images, set non-root user. Intermediate level."},

            {"q": "Write a bash script to backup a database and upload to S3.", "tips": "Use mysqldump/pg_dump, compress, upload with aws cli, handle errors, log output. Intermediate level."},

            {"q": "Write a Terraform configuration for an EC2 instance.", "tips": "Define provider, resource block for aws_instance, configure AMI, instance type, security group, key pair. Beginner level."},

        ],

        "behavioral": [

            {"q": "Describe a time you automated a manual process.", "tips": "Show impact: time saved, reduced errors, improved reliability. Discuss the automation tools and approach used."},

            {"q": "How do you handle a production incident?", "tips": "Stay calm, assess severity, mitigate impact, identify root cause, apply fix, document, conduct post-mortem."},

        ]

    },

    "machine learning engineer": {

        "technical": [

            {"q": "Explain the difference between supervised, unsupervised, and reinforcement learning.", "tips": "Supervised uses labeled data. Unsupervised finds patterns without labels. Reinforcement learning learns through rewards/penalties in an environment."},

            {"q": "What are CNNs and how do they work for image classification?", "tips": "CNNs use convolutional layers to detect features, pooling to reduce dimensions, fully connected layers for classification. Hierarchical feature learning."},

            {"q": "Explain how transformers work in NLP.", "tips": "Self-attention mechanism processes all tokens simultaneously. Encoder-decoder architecture. Positional encoding. BERT, GPT are transformer-based."},

            {"q": "What is model drift and how do you detect it?", "tips": "Data drift (input distribution changes) and concept drift (relationship changes). Monitor prediction distributions, retrain on new data, alert on threshold breaches."},

            {"q": "How do you handle data leakage in ML pipelines?", "tips": "Split train/test before any preprocessing. Don't use target information in features. Use proper cross-validation. Avoid look-ahead bias in time series."},

            {"q": "Explain gradient descent and its variants.", "tips": "Batch GD uses all data, SGD uses one sample, Mini-batch uses subset. Adam, RMSprop adapt learning rates. Momentum helps escape local minima."},

            {"q": "What is MLOps and why is it important?", "tips": "MLOps operationalizes ML: version control data/models, automate pipelines, monitor performance, manage deployment, ensure reproducibility."},

        ],

        "hr": [

            {"q": "Tell me about an ML model you deployed to production.", "tips": "Discuss problem, data, model selection, training, deployment infrastructure, monitoring, and business impact."},

            {"q": "How do you decide between using a simple vs complex model?", "tips": "Start simple (baseline). If performance insufficient, increase complexity. Consider tradeoffs: interpretability, training time, inference cost."},

        ],

        "coding": [

            {"q": "Implement a train-test split function from scratch.", "tips": "Shuffle indices, split by ratio, ensure reproducibility with random seed. Beginner level."},

            {"q": "Write a function to normalize features using min-max scaling.", "tips": "(x - min) / (max - min). Handle edge case where min == max. Beginner level."},

            {"q": "Implement a simple neural network forward pass with NumPy.", "tips": "Define weights, biases, activation function (sigmoid/ReLU), compute layer outputs. Intermediate level."},

        ],

        "behavioral": [

            {"q": "How do you collaborate with data scientists vs software engineers?", "tips": "Bridge the gap: translate research to production, create clear interfaces, document assumptions, align on success metrics."},

            {"q": "How do you evaluate if an ML solution is the right approach?", "tips": "Check if problem is well-defined, data is available, simpler heuristic could work, ROI justifies complexity, explainability requirements."},

        ]

    },

    "mobile developer": {

        "technical": [

            {"q": "What is the difference between React Native and Flutter?", "tips": "React Native uses JavaScript bridge to native components. Flutter compiles to native ARM code with its own rendering engine. Flutter has better performance."},

            {"q": "Explain the app lifecycle in iOS.", "tips": "Not Running, Inactive, Active, Background, Suspended. Use AppDelegate methods for transitions: didFinishLaunching, willResignActive, didEnterBackground."},

            {"q": "How do you manage state in a Flutter app?", "tips": "StatefulWidget, Provider, Riverpod, Bloc, Redux. Choose based on complexity. Provider is good for simple cases, Bloc for complex flows."},

            {"q": "What is the difference between native and hybrid mobile development?", "tips": "Native uses platform-specific languages (Swift/Kotlin). Hybrid uses web tech wrapped in native container (Cordova). Cross-platform like React Native bridges the gap."},

            {"q": "How do you handle offline data in a mobile app?", "tips": "Local database (SQLite, Realm), cached API responses, sync strategy (offline-first), conflict resolution, background sync."},

            {"q": "Explain push notifications architecture.", "tips": "Device registers with platform (APNs/FCM), server sends via push service, app receives in foreground/background. Handle permissions and payload."},

        ],

        "hr": [

            {"q": "What motivates you to build mobile apps?", "tips": "Passion for creating accessible, intuitive experiences that people use daily. Interest in mobile-specific challenges like performance and gestures."},

            {"q": "How do you ensure your app performs well on low-end devices?", "tips": "Optimize images, lazy loading, reduce bundle size, use efficient layouts, test on actual low-end devices, profile with tools."},

        ],

        "coding": [

            {"q": "Write a React Native component that fetches data from an API.", "tips": "Use useEffect with fetch, useState for loading/data/error states, display FlatList. Beginner level."},

            {"q": "Implement a custom hook for debounced search in React Native.", "tips": "Use useState for input, useEffect with setTimeout, clean up on input change. Intermediate level."},

        ],

        "behavioral": [

            {"q": "How do you handle different screen sizes and orientations?", "tips": "Use responsive layouts, auto-layout/constraints, test on multiple devices, handle orientation changes gracefully."},

            {"q": "Describe a challenging UI you implemented on mobile.", "tips": "Discuss the technical challenge, solution approach, animations, performance considerations, and testing."},

        ]

    },

    "product manager": {

        "technical": [

            {"q": "How do you prioritize features for a product roadmap?", "tips": "Use frameworks: RICE (Reach, Impact, Confidence, Effort), MoSCoW (Must-have, Should, Could, Won't), weighted scoring. Consider business goals."},

            {"q": "Explain the concept of MVP and why it's important.", "tips": "Minimum Viable Product: smallest feature set to validate learning. Reduces risk, speeds feedback, avoids building unwanted features."},

            {"q": "How do you define and track product KPIs?", "tips": "North Star metric, leading vs lagging indicators, OKRs. Examples: DAU/MAU, retention rate, NPS, conversion rate, LTV, CAC."},

            {"q": "What is the difference between quantitative and qualitative research?", "tips": "Quantitative: surveys, analytics, A/B tests (numbers, stats). Qualitative: user interviews, usability tests (insights, behaviors). Use both."},

            {"q": "How do you handle stakeholder communication and expectations?", "tips": "Regular updates, transparent about tradeoffs, data-backed decisions, clear documentation, manage scope creep with prioritization."},

            {"q": "Explain the concept of product-market fit.", "tips": "Product satisfies a strong market demand. Signs: organic growth, high retention, strong NPS, users actively seek alternatives when unavailable."},

        ],

        "hr": [

            {"q": "Tell me about a product you successfully launched.", "tips": "Use STAR: problem identified, market research, strategy, execution, launch metrics, lessons learned."},

            {"q": "How do you handle a product launch that didn't meet expectations?", "tips": "Analyze data, gather feedback, identify root causes, iterate, communicate learnings transparently, adjust strategy."},

        ],

        "coding": [

            {"q": "Write a simple SQL query to analyze feature adoption.", "tips": "Count distinct users who used a feature, group by date, calculate adoption rate. Beginner level."},

            {"q": "Create a Python script to calculate cohort retention.", "tips": "Group users by signup date, track activity periods, compute retention matrix. Intermediate level."},

        ],

        "behavioral": [

            {"q": "How do you handle disagreement with engineering about scope/effort?", "tips": "Listen to concerns, understand tradeoffs, explore alternatives, use data to support decisions, find compromise."},

            {"q": "Describe a time you had to make a decision with incomplete data.", "tips": "Show judgment: identify known and unknown, make best-informed decision, set up monitoring to validate, iterate."},

        ]

    }

}



DEFAULT_INTERVIEW = {

    "technical": [

        {"q": "Tell me about your technical background and key skills.", "tips": "Highlight your strongest technical skills, relevant projects, and how they align with the role."},

        {"q": "Describe your development process.", "tips": "Cover planning, design, implementation, testing, code review, deployment, and monitoring."},

        {"q": "How do you ensure code quality?", "tips": "Mention testing, code reviews, linting, CI/CD, documentation, and pair programming."},

    ],

    "hr": [

        {"q": "Tell me about yourself.", "tips": "Use the present-past-future formula: What you do now, relevant past experience, and what you're looking for."},

        {"q": "Why should we hire you?", "tips": "Connect your skills and experience directly to the job requirements. Give specific examples."},

        {"q": "What is your greatest strength?", "tips": "Choose a strength relevant to the role. Back it up with a concrete example."},

        {"q": "What is your greatest weakness?", "tips": "Choose a real but non-critical weakness. Show self-awareness and steps you're taking to improve."},

        {"q": "Where do you see yourself in 5 years?", "tips": "Show ambition and alignment with the company's growth. Be specific but flexible."},

        {"q": "Why are you leaving your current job?", "tips": "Stay positive. Focus on seeking growth and new challenges rather than complaints."},

        {"q": "How do you handle stress and pressure?", "tips": "Give a specific example. Mention prioritization, staying organized, and maintaining work-life balance."},

        {"q": "Do you have any questions for us?", "tips": "Always have questions prepared. Ask about team culture, growth opportunities, challenges, and the role's impact."},

    ],

    "coding": [

        {"q": "Reverse a string without using built-in reverse functions.", "tips": "Two-pointer approach or iterate backwards. Time O(n), Space O(1) or O(n) depending on approach."},

        {"q": "Find if a string is a valid palindrome.", "tips": "Two pointers from both ends, skip non-alphanumeric characters. Consider case-insensitive comparison."},

        {"q": "Implement a basic stack data structure.", "tips": "Use list with append() and pop() or linked list. Include push, pop, peek, is_empty, size methods."},

    ],

    "behavioral": [

        {"q": "Describe a time you had to learn a new technology quickly.", "tips": "Show adaptability and learning strategy. Mention resources used and how you applied the knowledge."},

        {"q": "Tell me about a time you went above and beyond.", "tips": "Show initiative, dedication, and the positive impact it had on the project or team."},

    ]

}





def get_interview_questions(role: str) -> Dict[str, Any]:

    role_lower = role.lower()

    for key in INTERVIEW_QUESTIONS:

        if key in role_lower or role_lower in key:

            return INTERVIEW_QUESTIONS[key]

    return DEFAULT_INTERVIEW





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




CAREER_INSIGHTS_DB = {

    "python developer": {

        "avg_salary_usd": 115000,

        "avg_salary_inr": "G8,00,000 - G25,00,000",

        "demand_level": "Very High",

        "growth_rate": "+25% (2024-2030)",

        "hiring_trend": "Increasing - Python is the #1 most popular language",

        "top_companies": ["Google", "Netflix", "Spotify", "Instagram", "Dropbox", "NASA", "Reddit", "Pinterest"],

        "future_outlook": "Excellent - Python dominates in AI/ML, data science, web development, and automation. Demand continues to grow across all sectors.",

        "key_industries": ["Technology", "Finance", "Healthcare", "E-commerce", "Education", "AI/ML"],

        "entry_level_salary": "$70,000 - $95,000",

        "senior_level_salary": "$150,000 - $250,000+"

    },

    "frontend developer": {

        "avg_salary_usd": 105000,

        "avg_salary_inr": "G6,00,000 - G20,00,000",

        "demand_level": "High",

        "growth_rate": "+18% (2024-2030)",

        "hiring_trend": "Steady - Strong demand for React/Vue/Angular developers",

        "top_companies": ["Meta", "Airbnb", "Stripe", "Shopify", "Netflix", "Uber", "Twitter"],

        "future_outlook": "Very Good - Web applications are essential. New frameworks and WebAssembly create new opportunities.",

        "key_industries": ["Technology", "E-commerce", "Media", "Finance", "SaaS"],

        "entry_level_salary": "$60,000 - $85,000",

        "senior_level_salary": "$130,000 - $200,000+"

    },

    "data scientist": {

        "avg_salary_usd": 130000,

        "avg_salary_inr": "G10,00,000 - G35,00,000",

        "demand_level": "Very High",

        "growth_rate": "+36% (2024-2030)",

        "hiring_trend": "Rapidly Increasing - AI/ML boom driving demand",

        "top_companies": ["Google", "Amazon", "Microsoft", "Meta", "Apple", "OpenAI", "Tesla", "JPMorgan"],

        "future_outlook": "Exceptional - Every industry needs data-driven decision making. AI/ML specialization commands premium salaries.",

        "key_industries": ["Technology", "Finance", "Healthcare", "Retail", "Manufacturing", "Government"],

        "entry_level_salary": "$80,000 - $110,000",

        "senior_level_salary": "$180,000 - $300,000+"

    },

    "full stack developer": {

        "avg_salary_usd": 110000,

        "avg_salary_inr": "G7,00,000 - G22,00,000",

        "demand_level": "Very High",

        "growth_rate": "+22% (2024-2030)",

        "hiring_trend": "Strong - Companies value versatile developers",

        "top_companies": ["Google", "Amazon", "Microsoft", "Shopify", "Stripe", "Uber", "Airbnb"],

        "future_outlook": "Excellent - Full-stack skills are highly valued, especially with modern frameworks.",

        "key_industries": ["Technology", "E-commerce", "Finance", "Healthcare", "Education", "Startups"],

        "entry_level_salary": "$65,000 - $90,000",

        "senior_level_salary": "$140,000 - $220,000+"

    },

    "devops engineer": {

        "avg_salary_usd": 125000,

        "avg_salary_inr": "G10,00,000 - G30,00,000",

        "demand_level": "Very High",

        "growth_rate": "+28% (2024-2030)",

        "hiring_trend": "Strongly Increasing - Cloud adoption drives demand",

        "top_companies": ["Amazon (AWS)", "Google (GCP)", "Microsoft (Azure)", "Netflix", "Spotify", "GitLab"],

        "future_outlook": "Excellent - Cloud-native, Kubernetes, and platform engineering are hot areas.",

        "key_industries": ["Technology", "Finance", "Healthcare", "Retail", "Government"],

        "entry_level_salary": "$75,000 - $100,000",

        "senior_level_salary": "$160,000 - $250,000+"

    },

    "machine learning engineer": {

        "avg_salary_usd": 140000,

        "avg_salary_inr": "G12,00,000 - G40,00,000",

        "demand_level": "Very High",

        "growth_rate": "+40% (2024-2030)",

        "hiring_trend": "Explosive Growth - AI revolution driving unprecedented demand",

        "top_companies": ["OpenAI", "Google DeepMind", "Anthropic", "Meta AI", "NVIDIA", "Tesla", "Apple"],

        "future_outlook": "Exceptional - AI/ML is the most in-demand field. Generative AI expertise commands premium.",

        "key_industries": ["Technology", "Finance", "Healthcare", "Automotive", "Robotics", "Aerospace"],

        "entry_level_salary": "$90,000 - $130,000",

        "senior_level_salary": "$200,000 - $350,000+"

    }

}





def get_career_insights(role: str) -> Dict[str, Any]:

    role_lower = role.lower()

    for key, data in CAREER_INSIGHTS_DB.items():

        if key in role_lower or role_lower in key:

            return data

    return {

        "avg_salary_usd": 95000,

        "avg_salary_inr": "G5,00,000 - G18,00,000",

        "demand_level": "Moderate to High",

        "growth_rate": "+15% (2024-2030)",

        "hiring_trend": "Steady Growth",

        "top_companies": ["Google", "Microsoft", "Amazon", "Apple", "Meta", "Various Startups"],

        "future_outlook": "Good - Growing demand across industries with increasing digital transformation.",

        "key_industries": ["Technology", "Finance", "Healthcare", "Education", "Retail"],

        "entry_level_salary": "$55,000 - $80,000",

        "senior_level_salary": "$120,000 - $180,000+"

    }





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




LEARNING_RESOURCES = {

    "Python": {"type": "Language", "difficulty": "Beginner", "time": "4-6 weeks", "resources": ["Python.org Tutorial", "Automate the Boring Stuff", "Corey Schafer YouTube"]},

    "JavaScript": {"type": "Language", "difficulty": "Beginner", "time": "4-6 weeks", "resources": ["MDN Web Docs", "JavaScript.info", "Eloquent JavaScript"]},

    "TypeScript": {"type": "Language", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["TypeScript Handbook", "Total TypeScript"]},

    "React": {"type": "Framework", "difficulty": "Intermediate", "time": "4-6 weeks", "resources": ["React.dev Official", "Kent C. Dodds Blog", "Epic React"]},

    "Angular": {"type": "Framework", "difficulty": "Intermediate", "time": "6-8 weeks", "resources": ["Angular.io Tour of Heroes", "Angular University"]},

    "Vue.js": {"type": "Framework", "difficulty": "Beginner-Intermediate", "time": "3-4 weeks", "resources": ["Vue.js Official Guide", "Vue Mastery"]},

    "Node.js": {"type": "Runtime", "difficulty": "Intermediate", "time": "3-4 weeks", "resources": ["Node.js Docs", "Node University"]},

    "Django": {"type": "Framework", "difficulty": "Intermediate", "time": "4-6 weeks", "resources": ["Django Official Tutorial", "Django for Beginners"]},

    "Flask": {"type": "Framework", "difficulty": "Beginner-Intermediate", "time": "2-3 weeks", "resources": ["Flask Mega-Tutorial", "Flask Official Docs"]},

    "FastAPI": {"type": "Framework", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["FastAPI Official Docs", "TestDriven.io"]},

    "Docker": {"type": "Tool", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["Docker Official Getting Started", "Docker Deep Dive"]},

    "Kubernetes": {"type": "Tool", "difficulty": "Advanced", "time": "6-8 weeks", "resources": ["Kubernetes.io Tutorials", "CKAD Certification"]},

    "AWS": {"type": "Cloud", "difficulty": "Intermediate", "time": "4-8 weeks", "resources": ["AWS Free Tier", "AWS Cloud Practitioner", "A Cloud Guru"]},

    "Azure": {"type": "Cloud", "difficulty": "Intermediate", "time": "4-8 weeks", "resources": ["Azure Free Account", "Microsoft Learn"]},

    "GCP": {"type": "Cloud", "difficulty": "Intermediate", "time": "4-8 weeks", "resources": ["GCP Free Tier", "Google Cloud Training"]},

    "TensorFlow": {"type": "ML Library", "difficulty": "Advanced", "time": "6-10 weeks", "resources": ["TensorFlow Official Tutorials", "Deep Learning Specialization"]},

    "PyTorch": {"type": "ML Library", "difficulty": "Advanced", "time": "6-10 weeks", "resources": ["PyTorch Tutorials", "Fast.ai"]},

    "PostgreSQL": {"type": "Database", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["PostgreSQL Tutorial", "Use The Index Luke"]},

    "MongoDB": {"type": "Database", "difficulty": "Beginner-Intermediate", "time": "2-3 weeks", "resources": ["MongoDB University", "MongoDB Docs"]},

    "Redis": {"type": "Database", "difficulty": "Intermediate", "time": "1-2 weeks", "resources": ["Redis University", "Redis Documentation"]},

    "Git": {"type": "Tool", "difficulty": "Beginner", "time": "1-2 weeks", "resources": ["Git Official Tutorial", "Pro Git Book", "Git Immersion"]},

    "Terraform": {"type": "IaC", "difficulty": "Intermediate", "time": "3-4 weeks", "resources": ["HashiCorp Learn", "Terraform Up & Running"]},

    "GraphQL": {"type": "API", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["GraphQL Official", "How to GraphQL"]},

    "REST API": {"type": "API", "difficulty": "Beginner", "time": "1-2 weeks", "resources": ["RESTful API Design", "Postman Learning Center"]},

    "CI/CD": {"type": "Practice", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["GitHub Actions Docs", "Jenkins Tutorial"]},

    "Machine Learning": {"type": "Field", "difficulty": "Advanced", "time": "12-16 weeks", "resources": ["Andrew Ng ML Course", "Hands-On ML with Scikit-Learn"]},

    "Deep Learning": {"type": "Field", "difficulty": "Advanced", "time": "10-14 weeks", "resources": ["Deep Learning Specialization", "fast.ai"]},

    "NLP": {"type": "Field", "difficulty": "Advanced", "time": "8-12 weeks", "resources": ["Hugging Face Course", "Stanford NLP Course"]},

    "Computer Vision": {"type": "Field", "difficulty": "Advanced", "time": "8-12 weeks", "resources": ["OpenCV Tutorials", "CS231n Stanford"]},

    "Agile": {"type": "Methodology", "difficulty": "Beginner", "time": "1-2 weeks", "resources": ["Agile Manifesto", "Scrum Guide"]},

    "SQL": {"type": "Language", "difficulty": "Beginner", "time": "3-4 weeks", "resources": ["SQLBolt", "Mode Analytics SQL Tutorial", "LeetCode SQL"]},

    "Pandas": {"type": "Library", "difficulty": "Intermediate", "time": "2-3 weeks", "resources": ["Pandas Official Docs", "10 Minutes to Pandas"]},

    "NumPy": {"type": "Library", "difficulty": "Intermediate", "time": "1-2 weeks", "resources": ["NumPy Official Tutorial"]},

    "Scikit-learn": {"type": "Library", "difficulty": "Intermediate", "time": "3-4 weeks", "resources": ["Scikit-learn Official Tutorials", "Hands-On ML"]},

}





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




@app.route('/login')

def login_page():

    return render_template('login.html')





@app.route('/signup')

def signup_page():

    return render_template('signup.html')





@app.route('/forgot-password')

def forgot_password_page():

    return render_template('forgot_password.html')





@app.route('/reset-password/<token>')

def reset_password_page(token):

    return render_template('reset_password.html', token=token)





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




@app.route('/api/auth/signup', methods=['POST'])

def api_auth_signup():

    """Register a new user account."""

    data = request.get_json() or {}

    email = data.get('email', '').strip()

    username = data.get('username', '').strip()

    password = data.get('password', '')

    confirm = data.get('confirm_password', '')



    # Validate required fields

    if not all([email, username, password]):

        return jsonify({'success': False, 'message': 'All fields are required.'}), 400



    if password != confirm:

        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400



    from utils.auth import create_user_account

    success, message, user = create_user_account(email, username, password)



    if success and user:

        login_user(user, remember=True)

        return jsonify({

            'success': True,

            'message': 'Account created successfully! Welcome to JobAgent.',

            'user': user.to_dict()

        })



    return jsonify({'success': False, 'message': message}), 400





@app.route('/api/auth/login', methods=['POST'])

def api_auth_login():

    """Authenticate user and create session."""

    data = request.get_json() or {}

    email = data.get('email', '').strip()

    password = data.get('password', '')

    remember = data.get('remember', False)



    if not email or not password:

        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400



    from utils.auth import authenticate_user

    success, message, user = authenticate_user(email, password, remember)



    if success and user:

        login_user(user, remember=remember)

        return jsonify({

            'success': True,

            'message': 'Login successful!',

            'user': user.to_dict()

        })



    return jsonify({'success': False, 'message': message}), 401





@app.route('/api/auth/logout', methods=['POST'])

@login_required

def api_auth_logout():

    """Log out the current user."""

    from utils.auth import logout_user_session

    logout_user_session(current_user)

    logout_user()

    return jsonify({'success': True, 'message': 'Logged out successfully.'})





@app.route('/api/auth/forgot-password', methods=['POST'])

def api_auth_forgot_password():

    """Initiate password reset flow."""

    data = request.get_json() or {}

    email = data.get('email', '').strip()



    if not email:

        return jsonify({'success': False, 'message': 'Email is required.'}), 400



    from utils.auth import initiate_password_reset

    success, message = initiate_password_reset(email)

    return jsonify({'success': success, 'message': message})





@app.route('/api/auth/reset-password', methods=['POST'])

def api_auth_reset_password():

    """Complete password reset with token."""

    data = request.get_json() or {}

    token = data.get('token', '').strip()

    password = data.get('password', '')

    confirm = data.get('confirm_password', '')



    if not token or not password:

        return jsonify({'success': False, 'message': 'Token and password are required.'}), 400



    if password != confirm:

        return jsonify({'success': False, 'message': 'Passwords do not match.'}), 400



    from utils.auth import reset_password

    success, message = reset_password(token, password)

    return jsonify({'success': success, 'message': message})





@app.route('/api/auth/me')

@login_required

def api_auth_me():

    """Return current authenticated user data."""

    from utils.auth import get_user_dashboard_data

    data = get_user_dashboard_data(current_user)

    return jsonify(data)





@app.route('/api/auth/check')

def api_auth_check():

    """Check if user is authenticated (for frontend)."""

    if current_user.is_authenticated:

        return jsonify({

            'authenticated': True,

            'user': current_user.to_dict()

        })

    return jsonify({'authenticated': False})





@app.route('/')

def index():

    return render_template('index.html')






@app.route('/health')

def health_check():

    """Public liveness probe for Render/uptime checks."""

    return jsonify({'status': 'ok'})


@app.route('/<path:path>')

def spa_fallback(path):

    """Serve the single-page app for client-side sections (/chat, /dashboard,

    /resume, etc.) so direct URL access does not return a 404 Not Found.



        Only real API/static routes (matched more specifically by Flask) reach here
    Only real API/static routes (matched more specifically by Flask) reach here
    as fallbacks for unknown or deep-linked SPA paths.
    """
    if path.startswith('api/'):
        return jsonify({'success': False, 'error': 'Not found'}), 404

    return render_template('index.html')





@app.route('/static/<path:filename>')

def serve_static(filename):

    return send_from_directory('static', filename)





# ========================================================================
# Role Guide Search API
# ========================================================================


@app.route('/api/search', methods=['POST'])

def api_search():

    data = request.get_json() or {}

    query = data.get('query', '').strip()

    roles = data.get('roles', [])



    if not query:

        return jsonify({"error": "Please provide a search query"}), 400



    if not roles:

        roles = get_related_roles(query)



    # primary query and each related title resolve to OWN guide
    # honest no-guide fallback dedupes by title so grid never shows dupes
    try:
        primary_guide = get_role_guide(query)
    except Exception:
        primary_guide = {
            "role_title": query or "Unknown role",
            "guide_available": False,
            "error": "Failed to retrieve role guide",
        }

    related_guides = []
    seen_titles = {primary_guide.get("role_title", "").lower()}
    for role in roles[:8]:
        try:
            guide = get_role_guide(role)
        except Exception:
            continue
        title = guide.get("role_title", "").lower()
        if title and title in seen_titles:
            continue
        seen_titles.add(title)
        related_guides.append(guide)
        if len(related_guides) >= 5:
            break

    # Localize salary: profile location wins, IP is fallback only
    try:
        location_info = resolve_location(
            user=current_user if current_user.is_authenticated else None,
            request_ip=request.remote_addr,
        )
    except Exception:
        location_info = {"currency_key": "usd", "country": "US", "city": None}

    try:
        primary_guide = annotate_salary_for_location(primary_guide, location_info["currency_key"])
    except Exception:
        pass

    try:
        related_guides = [annotate_salary_for_location(g, location_info["currency_key"]) for g in related_guides]
    except Exception:
        pass



    # Store search in session

    user_data = get_user_data()

    user_data['search_history'].append({

        "query": query,

        "date": datetime.now().strftime("%Y-%m-%d %H:%M")

    })



    return jsonify({

        "query": query,

        "roles": roles,

        "total": len(roles),

        "primary_guide": primary_guide,

        "related_guides": related_guides,

        "location_info": location_info,

        "platform_urls": {

            key: url.format(role=urllib.parse.quote(query))

            for key, url in PLATFORM_SEARCH_URLS.items()

        }

    })





# ========================================================================
# Role Guide Search API
# ========================================================================
# Role Expansion API

@app.route('/api/expand-roles', methods=['POST'])

def api_expand_roles():

    data = request.get_json() or {}

    role = data.get('role', '').strip()

    if not role:

        return jsonify({"error": "Please provide a role"}), 400


    try:
        related = get_related_roles(role)
    except Exception:
        related = []

    return jsonify({
        "role": role, "related_roles": related
    })





# ========================================================================
# Role Guide Search API
# ========================================================================
# Resume Analysis API

@app.route('/api/analyze-resume', methods=['POST'])

def api_analyze_resume():

    text = request.form.get('resume_text', '')

    target_role = request.form.get('target_role', '')



    if 'resume_file' in request.files:

        file = request.files['resume_file']

        if file.filename:

            filename = file.filename.lower()

            content = file.read()



            # Proper local extraction (PDF -> pdfplumber/PyPDF2,

            # DOCX -> python-docx, TXT -> decode). Falls back to the

            # pasted text when a binary file yields nothing.

            from utils.resume_parser import extract_resume_text

            extracted, meta = extract_resume_text(filename, content)

            if len(' '.join(extracted.split())) >= 50:

                text = extracted

            else:

                text = request.form.get('resume_text', '')



    if not text.strip():

        return jsonify({"error": "No resume content provided. Please paste your resume text or upload a file."}), 400



    result = analyze_resume_text(text, target_role)



    # Local resume intelligence layer (entities + evidence-based skills).

    # Kept non-fatal so ATS scoring always works, even if this layer

    # hits an unexpected edge case.

    try:

        from services.resume import extract_resume

        result["extracted"] = extract_resume(text=text)

    except Exception as exc:  # pragma: no cover

        result["extracted"] = {"meta": {"warnings": [f"extraction_error:{exc}"]}}



    # Step 3: evidence-based skill intelligence (additive, local only)

    try:

        from services.resume.skill_intelligence import analyze_skills

        result["skill_intelligence"] = analyze_skills(result["extracted"])

    except Exception as exc:  # pragma: no cover

        result["skill_intelligence"] = {"error": f"skill_intelligence:{exc}"}



    user_data = get_user_data()

    user_data['ats_scores'].append({

        "score": result['ats_score'],

        "role": target_role,

        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),

        "skills": result['resume_skills']

    })

    user_data['resume_versions'].append({

        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),

        "word_count": result['word_count'],

        "skills_count": len(result['resume_skills'])

    })



    return jsonify(result)





# ========================================================================
# Role Guide Search API
# ========================================================================
# Skill Gap Analysis API

@app.route('/api/skill-gap', methods=['POST'])

def api_skill_gap():

    data = request.get_json() or {}

    role = data.get('role', '')

    skills = data.get('skills', [])



    if not role:

        return jsonify({"error": "Please provide a target role"}), 400



    required_skills = get_role_skills(role)

    possessed = [s for s in skills if s.lower() in {r.lower() for r in required_skills}]

    missing = [s for s in required_skills if s.lower() not in {r.lower() for r in skills}]

    match_pct = round(len(possessed) / max(len(required_skills), 1) * 100, 1)



    critical = []

    important = []

    optional = []

    for s in missing:

        sl = s.lower()

        if sl in {"python", "javascript", "java", "sql", "git", "docker", "aws", "react", "node.js"}:

            critical.append(s)

        elif sl in {"kubernetes", "terraform", "graphql", "typescript", "redis", "mongodb", "postgresql"}:

            important.append(s)

        else:

            optional.append(s)



    roadmap = []

    for s in missing:

        if s in LEARNING_RESOURCES:

            roadmap.append({

                "skill": s,

                "type": LEARNING_RESOURCES[s]["type"],

                "difficulty": LEARNING_RESOURCES[s]["difficulty"],

                "time": LEARNING_RESOURCES[s]["time"],

                "resources": LEARNING_RESOURCES[s]["resources"]

            })

        else:

            roadmap.append({

                "skill": s,

                "type": "General",

                "difficulty": "Intermediate",

                "time": "2-4 weeks",

                "resources": ["Search for tutorials on Google", "YouTube tutorials", "Online courses"]

            })



    return jsonify({

        "role": role,

        "required_skills": required_skills,

        "possessed": possessed,

        "missing": missing,

        "match_percentage": match_pct,

        "critical_skills": critical,

        "important_skills": important,

        "optional_skills": optional,

        "learning_roadmap": roadmap

    })





# ========================================================================
# Role Guide Search API
# ========================================================================
# Live Job Search API (real, freshness-sorted, deduped)

@app.route('/api/jobs/search', methods=['POST'])

def api_jobs_search():

    """Actually searches live sources (Adzuna, JSearch, RemoteOK always;

    Naukri/Wellfound optionally) instead of just linking out to other

    sites. Every job returned here has been freshness-checked: expired

    postings are dropped, duplicates across sources are merged, and the

    list is sorted newest-first."""

    data = request.get_json() or {}

    job_title = (data.get('job_title') or data.get('query') or '').strip()

    location = (data.get('location') or '').strip()

    limit = min(int(data.get('limit', 30) or 30), 50)

    include_slow_sources = bool(data.get('include_slow_sources', True))

    max_age_days = int(data.get('max_age_days', 30) or 30)



    if not job_title:

        return jsonify({"error": "Please provide a job_title to search for"}), 400



    result = live_job_search(

        job_title,

        location=location,

        limit=limit,

        include_slow_sources=include_slow_sources,

        max_age_days=max_age_days,

    )



    if not result["sources_used"]:

        result["notice"] = (

            "No live sources returned results - this usually means no "

            "ADZUNA_API_KEY/ADZUNA_APP_ID or RAPIDAPI_KEY is configured, "

            "and the scraper-based sources (Naukri/Wellfound) either "

            "timed out or found nothing for this query."

        )



    return jsonify(result)





# ========================================================================
# Role Guide Search API
# ========================================================================
# Market Skill-Demand API

@app.route('/api/market/skill-demand', methods=['POST'])

def api_market_skill_demand():

    """Computes which skills are actually in demand for a role by

    sampling live postings and counting mentions - not a static list."""

    data = request.get_json() or {}

    job_title = (data.get('job_title') or '').strip()

    location = (data.get('location') or '').strip()

    sample_size = min(int(data.get('sample_size', 40) or 40), 60)

    resume_skills = data.get('resume_skills') or []



    if not job_title:

        return jsonify({"error": "Please provide a job_title"}), 400



    demand = analyze_skill_demand(job_title, location=location, sample_size=sample_size)



    if resume_skills:

        demand["resume_comparison"] = compare_resume_to_demand(resume_skills, demand)



    return jsonify(demand)





# ========================================================================
# Role Guide Search API
# ========================================================================
# Application Tracking API (Applied -> Interview -> Offer/Rejected)

_VALID_APPLICATION_STATUSES = {"applied", "screening", "interview", "offer", "rejected", "accepted"}





@app.route('/api/applications', methods=['GET'])

@login_required

def api_list_applications():

    """Lists the current user's tracked applications, grouped by status

    so the frontend can render an Applied/Interview/Offer/Rejected board."""

    applications = JobApplication.query.filter_by(user_id=current_user.id).order_by(JobApplication.last_updated.desc()).all()


    board: Dict[str, List[Dict]] = {status: [] for status in _VALID_APPLICATION_STATUSES}

    for application in applications:

        entry = {

            "id": application.id,

            "company": application.company,

            "role": application.role,

            "location": application.location,

            "job_url": application.job_url,

            "salary_range": application.salary_range,

            "status": application.status,

            "applied_date": application.applied_date.isoformat() if application.applied_date else None,

            "last_updated": application.last_updated.isoformat() if application.last_updated else None,

            "notes": application.notes,

        }

        board.setdefault(application.status, []).append(entry)



    return jsonify({"board": board, "total": len(applications)})





@app.route('/api/applications', methods=['POST'])

@login_required

def api_create_application():

    """Starts tracking a job application. Typically called right after

    the user finds a job via /api/jobs/search and clicks 'I applied'."""

    data = request.get_json() or {}

    company = (data.get('company') or '').strip()

    role = (data.get('role') or '').strip()



    if not company or not role:

        return jsonify({"error": "company and role are required"}), 400



    status = data.get('status', 'applied')

    if status not in _VALID_APPLICATION_STATUSES:

        status = 'applied'



    application = JobApplication(

        user_id=current_user.id,

        saved_job_id=data.get('saved_job_id'),

        company=company,

        role=role,

        location=data.get('location'),

        job_url=data.get('job_url'),

        salary_range=data.get('salary_range'),

        status=status,

        notes=data.get('notes'),

        resume_used=data.get('resume_used'),

    )

    db.session.add(application)

    db.session.commit()



    return jsonify({"status": "ok", "id": application.id})





@app.route('/api/applications/<int:application_id>', methods=['PATCH'])

@login_required

def api_update_application(application_id):

    """Moves an application through the pipeline (e.g. applied -> interview

    -> offer/rejected) or updates notes."""

    application = JobApplication.query.filter_by(
        id=application_id, user_id=current_user.id
    ).first()

    if not application:

        return jsonify({"error": "Application not found"}), 404



    data = request.get_json() or {}

    new_status = data.get('status')

    if new_status is not None:

        if new_status not in _VALID_APPLICATION_STATUSES:

            return jsonify({"error": f"status must be one of {sorted(_VALID_APPLICATION_STATUSES)}"}), 400

        application.status = new_status



    if 'notes' in data:

        application.notes = data['notes']

    if 'salary_range' in data:

        application.salary_range = data['salary_range']



    db.session.commit()

    return jsonify({"status": "ok", "id": application.id, "current_status": application.status})





@app.route('/api/applications/<int:application_id>', methods=['DELETE'])

@login_required

def api_delete_application(application_id):

    application = JobApplication.query.filter_by(
        id=application_id, user_id=current_user.id
    ).first()

    if not application:

        return jsonify({"error": "Application not found"}), 404



    db.session.delete(application)

    db.session.commit()

    return jsonify({"status": "ok"})





# ========================================================================
# Role Guide Search API
# ========================================================================
# Saved Jobs API (persisted, user-scoped)
# ========================================================================

@app.route('/api/jobs/saved', methods=['GET'])

@login_required

def api_list_saved_jobs():

    """The current user's saved jobs (DB-backed, newest first)."""

    rows = (SavedJob.query

            .filter_by(user_id=current_user.id)

            .order_by(SavedJob.saved_at.desc())

            .all())

    jobs = []

    for row in rows:

        guide = {}

        if row.guide_data:

            try:

                guide = json.loads(row.guide_data)

            except (ValueError, TypeError):

                guide = {}

        jobs.append({

            "id": row.id,

            "role_title": row.role_title,

            "company": row.company,

            "job_url": row.job_url,

            "status": row.status,

            "notes": row.notes,

            "saved_at": row.saved_at.isoformat() if row.saved_at else None,

            "updated_at": row.updated_at.isoformat() if row.updated_at else None,

            "guide": guide,

        })

    return jsonify({"success": True, "jobs": jobs, "total": len(jobs)})


@app.route('/api/jobs/saved/status', methods=['POST'])

@login_required

def api_update_saved_job_status():

    """Update the tracking status of one saved job owned by this user."""

    data = request.get_json() or {}

    job_id = data.get('id')

    status = (data.get('status') or '').strip().lower()

    valid = {'saved', 'applied', 'interviewing', 'offer', 'rejected'}

    if status and status not in valid:

        return jsonify({'success': False,

                        'error': 'status must be one of ' + str(sorted(valid))}), 400

    row = SavedJob.query.filter_by(id=job_id, user_id=current_user.id).first()

    if not row:

        return jsonify({'success': False, 'error': 'Saved job not found'}), 404

    if status:

        row.status = status

    if 'notes' in data:

        row.notes = data.get('notes')

    db.session.commit()

    return jsonify({'success': True, 'id': row.id, 'status': row.status})


# ========================================================================
# In-App Notifications API (re-engagement)

@app.route('/api/notifications', methods=['GET'])

@login_required

def api_list_notifications():

    """Generate due notifications, then return unread count + recent list."""

    generate_notifications_for_user(current_user)

    notifications = (Notification.query
                     .filter_by(user_id=current_user.id)
                     .order_by(Notification.created_at.desc())
                     .limit(30).all())

    unread_count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).count()

    return jsonify({
        "unread_count": unread_count,
        "notifications": [n.to_dict() for n in notifications],
    })


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required

def api_mark_notification_read(notification_id):

    notification = Notification.query.filter_by(
        id=notification_id, user_id=current_user.id
    ).first()

    if not notification:

        return jsonify({"success": False, "error": "Notification not found"}), 404



    notification.is_read = True

    notification.read_at = datetime.utcnow()
    db.session.commit()

    return jsonify({"status": "ok"})





@app.route('/api/notifications/read-all', methods=['POST'])

@login_required

def api_mark_all_notifications_read():

    """Mark every unread notification for this user as read (keeps rows)."""

    now = datetime.utcnow()

    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).update(
        {'is_read': True, 'read_at': now}, synchronize_session=False)

    db.session.commit()

    return jsonify({"status": "ok", "marked_count": count})
    return jsonify({"status": "ok", "marked_count": count})

# ========================================================================
# Role Guide Search API
# ========================================================================
# Adaptive Interview Preparation API



@app.route('/api/interview-prep/start', methods=['POST'])
def api_interview_prep_start():
    """Start a DB-persisted adaptive interview session."""
    data = request.get_json() or {}
    role = str(data.get('role', '') or '').strip()
    if not role:
        return jsonify({"error": "Please provide a role"}), 400

    session_id = str(uuid.uuid4())
    config = {
        "target_role": role,
        "company": data.get("company", ""),
        "interview_mode": data.get("interview_mode", "standard"),
        "experience_level": data.get("experience_level", "mid"),
        "resume_version_id": data.get("resume_version_id", ""),
        "job_id": data.get("job_id", ""),
    }
    resume_context = data.get("resume_context", {}) or {}
    job_context = data.get("job_context", {}) or {}
    required_skills = data.get("required_skills", []) or []
    preferred_skills = data.get("preferred_skills", []) or []

    state = InterviewState(session_id, config)
    state.user_id = str(current_user.id)
    state.resume_used = bool(resume_context)
    state.jd_used = bool(job_context)

    provider = get_llm_provider()
    question_gen = QuestionGenerator(llm_provider=provider)
    jd_skills = question_gen._skills_from_job(job_context)
    required_skills = list(required_skills) or jd_skills["required"]
    preferred_skills = list(preferred_skills) or jd_skills["preferred"]
    state.required_skills = required_skills
    state.preferred_skills = preferred_skills
    state.skills_remaining = list(required_skills)
    state.required_skills_not_tested = list(required_skills)
    state.preferred_skills_not_tested = list(preferred_skills)

    rag_results = []
    rag_pipeline = get_rag()
    if rag_pipeline:
        try:
            rag_query = (role + " " + str((resume_context or {}).get("text", ""))[:400]).strip()
            if rag_query:
                rag_results = rag_pipeline.retrieve(rag_query, top_k=2) or []
            if rag_results:
                state.rag_used = True
        except Exception as exc:
            logger.warning("Interview RAG start failed: %s", exc)

    resume_norm = question_gen._normalize_resume_skills(resume_context)
    context_str = question_gen._build_context_str(
        state, resume_norm, required_skills, job_context, [], rag_results
    )
    first_question = question_gen.get_first_question(
        state, resume_norm, required_skills, job_context, context_str
    )
    question_text = first_question.get("question", "")
    state.record_question(
        question_text,
        first_question.get("type", "behavioral"),
        first_question.get("skill", ""),
        source=str(first_question.get("source", "")),
        topic=str(first_question.get("topic", "")),
        difficulty=str(first_question.get("difficulty", "")),
        follow_up=False,
    )

    conversation = [{"role": "interviewer", "content": question_text}]
    extras = {
        "resume_context": resume_context,
        "job_context": job_context,
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "conversation": conversation,
        "resume_version_id": data.get("resume_version_id", ""),
        "job_description": (job_context or {}).get("description"),
    }

    # The database is the authoritative source. Never fall back to a worker-local
    # session because Render/Gunicorn can route the next request to another worker.
    row_id = InterviewSessionStore.create(state, extras)
    if row_id is None:
        return jsonify({
            "success": False,
            "error": "Could not create interview session. Please try again."
        }), 503
    InterviewSessionStore.add_message(
        row_id, "interviewer", question_text,
        question_type=str(first_question.get("type", "behavioral")),
        question_id=str(first_question.get("question_id", "")),
    )

    llm_info = provider.model_info() if provider else {
        "runtime": "none", "model": "", "base_url": ""
    }
    llm_info["available"] = bool(provider)
    llm_info["last_error"] = (
        getattr(provider, "last_error", "") if provider
        else "GROQ_API_KEY missing - deterministic mode"
    )

    return jsonify({
        "user_id": current_user.id,
        "session_id": session_id,
        "role": role,
        "question": first_question,
        "turn": state.turn_count,
        "status": "active",
        "llm_generated_question": bool(first_question.get("llm_generated")),
        "question_fallback_reason": first_question.get("fallback_reason"),
        "llm_available": bool(provider),
        "llm": llm_info,
        "llm_runtime": llm_info.get("runtime"),
        "llm_model": llm_info.get("model"),
        "rag_used": state.rag_used,
        "rag_chunks": len(rag_results),
    })


@app.route('/api/interview-prep/answer', methods=['POST'])
def api_interview_prep_answer():
    """Evaluate an answer and generate the next adaptive question from DB state."""
    import hashlib

    data = request.get_json() or {}
    session_id = str(data.get("session_id", "") or "").strip()
    answer = str(data.get("answer", "") or "")
    if not session_id:
        return jsonify({"error": "Invalid or expired session"}), 400
    if not answer.strip():
        return jsonify({"error": "Please provide a non-empty answer"}), 400

    loaded = InterviewSessionStore.load(session_id, current_user.id)
    if loaded is None:
        owner = InterviewSessionStore.lookup_owner(session_id)
        if owner is not None and owner != current_user.id:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 404
        return jsonify({"error": "Invalid or expired session"}), 400

    state, extras, row_id = loaded
    fingerprint = hashlib.sha256(
        ((state.current_question or {}).get("question", "") + "\n" + answer.strip()).encode("utf-8")
    ).hexdigest()

    # Persisted idempotency: retries across Gunicorn workers return the same response.
    if state.last_answer_fingerprint == fingerprint and isinstance(state.last_response, dict):
        return jsonify(state.last_response)

    resume_context = extras.get("resume_context", {}) or {}
    job_context = extras.get("job_context", {}) or {}
    required_skills = extras.get("required_skills", []) or []
    preferred_skills = extras.get("preferred_skills", []) or []
    conversation = list(extras.get("conversation", []) or [])

    last_question = ""
    for msg in reversed(conversation):
        if msg.get("role") == "interviewer" and str(msg.get("content", "")).strip():
            last_question = msg["content"]
            break
    if not last_question and state.current_question:
        last_question = state.current_question.get("question", "")

    provider = get_llm_provider()
    question_gen = QuestionGenerator(llm_provider=provider)
    evaluator = AnswerEvaluator(llm_provider=provider)
    context_builder = InterviewContextBuilder(rag_pipeline=None)

    rag_results = []
    rag_pipeline = get_rag()
    rag_query = (last_question + " " + answer)[:800].strip()
    if rag_pipeline and rag_query:
        try:
            rag_results = rag_pipeline.retrieve(rag_query, top_k=3) or []
            if rag_results:
                state.rag_used = True
        except Exception as exc:
            logger.warning("Interview RAG answer failed: %s", exc)

    prev_eval = state.previous_evaluations[-1] if state.previous_evaluations else None
    built = context_builder.build_context(
        resume_context, job_context, conversation, state.to_dict(),
        rag_query, ([prev_eval] if prev_eval else []), rag_results
    )
    context_str = built.get("context", "")
    if built.get("rag_chunks"):
        state.rag_used = True

    evaluation = evaluator.evaluate(last_question, answer, context_str, prev_eval)
    state.record_answer(answer, evaluation)

    conversation.append({"role": "candidate", "content": answer})
    follow_up = state.should_follow_up(evaluation)
    question_context = context_str
    if follow_up:
        question_context += (
            "\n\nFOLLOW-UP MODE: the previous answer scored %s/100 - "
            "do NOT switch topics. Ask exactly ONE probing follow-up "
            "about the same skill (%s), targeting the missing or incorrect parts."
            % (evaluation.get("overall_score"), state.current_skill or "the current topic")
        )

    next_question = question_gen.get_next_question(
        state, resume_context, required_skills, preferred_skills,
        conversation, rag_results, context_str=question_context,
        evaluation=evaluation
    )
    if follow_up and next_question:
        state.mark_follow_up()

    if next_question:
        next_text = next_question.get("question", "")
        state.record_question(
            next_text,
            next_question.get("type", "technical"),
            next_question.get("skill", ""),
            source=str(next_question.get("source", "")),
            topic=str(next_question.get("topic", "")),
            difficulty=str(next_question.get("difficulty", "")),
            follow_up=follow_up,
        )
        conversation.append({"role": "interviewer", "content": next_text})
        InterviewSessionStore.add_message(
            row_id, "candidate", answer,
            question_type=str((state.previous_evaluations[-1] if state.previous_evaluations else {}).get("question_type", "")),
            evaluation=evaluation,
        )
        InterviewSessionStore.add_message(
            row_id, "interviewer", next_text,
            question_type=str(next_question.get("type", "technical")),
            question_id=str(next_question.get("question_id", "")),
        )
    else:
        InterviewSessionStore.add_message(row_id, "candidate", answer, evaluation=evaluation)

    should_continue = state.should_continue()
    response = {
        "status": "active" if should_continue else "completed",
        "session_id": session_id,
        "turn": state.turn_count,
        "evaluation": evaluation,
        "next_question": next_question,
        "should_continue": should_continue,
        "llm_available": bool(provider),
        "llm_generated_question": bool((next_question or {}).get("llm_generated")),
        "question_fallback_reason": (next_question or {}).get("fallback_reason"),
        "eval_by": evaluation.get("evaluated_by"),
        "eval_fallback_reason": evaluation.get("fallback_reason"),
        "rag_used": state.rag_used,
        "rag_chunks": len(rag_results),
    }
    state.last_answer_fingerprint = fingerprint
    state.last_response = response
    extras["conversation"] = conversation
    if not InterviewSessionStore.save(state, extras, row_id):
        return jsonify({
            "success": False,
            "error": "Interview state could not be saved. Please retry."
        }), 503
    return jsonify(response)


@app.route('/api/interview-prep/end', methods=['POST'])
def api_interview_prep_end():
    """End a DB-persisted interview session and return the complete report."""
    data = request.get_json() or {}
    session_id = str(data.get("session_id", "") or "").strip()
    if not session_id:
        return jsonify({"error": "Invalid or expired session"}), 400

    loaded = InterviewSessionStore.load(session_id, current_user.id)
    if loaded is None:
        owner = InterviewSessionStore.lookup_owner(session_id)
        if owner is not None and owner != current_user.id:
            return jsonify({"success": False, "error": "Invalid or expired session"}), 404
        return jsonify({"error": "Invalid or expired session"}), 400

    state, extras, row_id = loaded
    state.finalize()
    report = state.generate_report()
    report["session_id"] = session_id
    report["target_role"] = state.target_role
    report["interview_mode"] = state.interview_mode
    report["resume_used"] = state.resume_used
    report["jd_used"] = state.jd_used
    report["rag_used"] = state.rag_used

    InterviewSessionStore.save(state, extras, row_id)
    return jsonify({"status": "completed", "summary": report})


@app.route('/api/interview-prep', methods=['POST'])

def api_interview_prep():

    """Backward-compatible endpoint: returns static questions for a role."""

    data = request.get_json() or {}

    role = data.get('role', '')

    if not role:

        return jsonify({"error": "Please provide a role"}), 400



    questions = get_interview_questions(role)

    return jsonify({

        "role": role,

        "questions": questions

    })





# ========================================================================
# Role Guide Search API
# ========================================================================
# Career Insights API

@app.route('/api/career-insights', methods=['POST'])

def api_career_insights():

    data = request.get_json() or {}

    role = data.get('role', '')

    if not role:

        return jsonify({"error": "Please provide a role"}), 400



    insights = get_career_insights(role)

    return jsonify({

        "role": role,

        "insights": insights

    })





# ========================================================================
# Role Guide Search API
# ========================================================================
# Dashboard API

@app.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    """Return dashboard data, with saved guides loaded from the authenticated DB user."""
    user_data = get_user_data()
    saved = []
    try:
        rows = SavedJob.query.filter_by(user_id=current_user.id).order_by(
            SavedJob.id.desc()
        ).all()
        for row in rows:
            guide = {}
            try:
                guide = json.loads(row.guide_data or "{}")
            except Exception:
                guide = {}
            if not isinstance(guide, dict):
                guide = {}
            guide.setdefault("role_title", row.role_title or "")
            guide.setdefault("saved_date", row.saved_at.strftime("%Y-%m-%d %H:%M") if row.saved_at else "")
            guide["id"] = row.id
            saved.append(guide)
    except Exception as exc:
        logger.warning("Dashboard saved-guide load failed: %s", exc)
        saved = []
    return jsonify({
        "saved_jobs": saved,
        "interview_calls": user_data['interview_calls'],
        "ats_scores": user_data['ats_scores'],
        "resume_versions": user_data['resume_versions'],
        "skill_progress": user_data['skill_progress'],
        "search_history": user_data['search_history']
    })


@app.route('/api/dashboard/save-job', methods=['POST'])

def api_save_job():

    data = request.get_json() or {}

    guide = data.get('guide', {}) or {}

    if current_user.is_authenticated:

        role_title = (guide.get('role_title') or '').strip()

        if not role_title:

            return jsonify({'success': False, 'error': 'role_title is required'}), 400

        existing = SavedJob.query.filter_by(

            user_id=current_user.id, role_title=role_title).first()

        if not existing:

            db.session.add(SavedJob(

                user_id=current_user.id,

                role_title=role_title,

                guide_data=json.dumps(guide),

                company=(guide.get('company') or None),

                job_url=(guide.get('job_url') or None),

            ))

            db.session.commit()

        total = SavedJob.query.filter_by(user_id=current_user.id).count()

        return jsonify({"status": "ok", "saved": total, "persisted": True})

    user_data = get_user_data()

    existing_titles = [j.get('role_title') for j in user_data['saved_jobs']]

    if guide.get('role_title') not in existing_titles:

        guide['saved_date'] = datetime.now().strftime("%Y-%m-%d %H:%M")

        user_data['saved_jobs'].append(guide)

    return jsonify({"status": "ok", "saved": len(user_data['saved_jobs'])})





@app.route('/api/dashboard/remove-job', methods=['POST'])

def api_remove_job():

    data = request.get_json() or {}

    role_title = data.get('role_title', '')

    if current_user.is_authenticated:

        removed = SavedJob.query.filter_by(

            user_id=current_user.id, role_title=role_title).delete()

        db.session.commit()

        total = SavedJob.query.filter_by(user_id=current_user.id).count()

        return jsonify({"status": "ok", "removed": removed, "saved": total, "persisted": True})

    user_data = get_user_data()

    user_data['saved_jobs'] = [j for j in user_data['saved_jobs'] if j.get('role_title') != role_title]

    return jsonify({"status": "ok", "saved": len(user_data['saved_jobs'])})





@app.route('/api/dashboard/update-skill-progress', methods=['POST'])

def api_update_skill_progress():

    data = request.get_json() or {}

    skill = data.get('skill', '')

    progress = data.get('progress', 0)

    user_data = get_user_data()

    user_data['skill_progress'][skill] = progress

    return jsonify({"status": "ok", "skill_progress": user_data['skill_progress']})





# ========================================================================
# Role Guide Search API
# ========================================================================
# Feedback & Ratings API

@app.route('/api/feedback', methods=['POST'])

def api_submit_feedback():

    """Submit user feedback."""

    from models.user_model import Feedback

    

    data = request.get_json() or {}

    

    # Validate required fields

    if not data.get('rating') or not data.get('comment'):

        return jsonify({"success": False, "message": "Rating and comment are required"}), 400

    

    if not (1 <= int(data.get('rating', 0)) <= 5):

        return jsonify({"success": False, "message": "Rating must be between 1 and 5"}), 400

    

    try:

        feedback = Feedback(

            user_id=current_user.id if current_user.is_authenticated else None,

            name=data.get('name', 'Anonymous'),

            email=data.get('email'),

            rating=int(data['rating']),

            comment=data['comment'],

            category=data.get('category', 'general'),

            is_anonymous=data.get('is_anonymous', False)

        )

        

        db.session.add(feedback)

        db.session.commit()

        

        return jsonify({

            "success": True,

            "message": "Thank you for your feedback!",

            "feedback_id": feedback.id

        })

        

    except Exception as e:

        db.session.rollback()

        return jsonify({"success": False, "message": str(e)}), 500





@app.route('/api/feedback', methods=['GET'])

def api_get_feedback():

    """Get all feedback (admin only)."""

    from models.user_model import Feedback

    

    try:

        page = request.args.get('page', 1, type=int)

        per_page = request.args.get('per_page', 20, type=int)

        

        # ========================================================================
# Role Guide Search API
# ========================================================================


        query = Feedback.query.order_by(

            Feedback.rating.desc(),

            Feedback.created_at.desc()

        )

        

        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        

        feedback_list = []

        for fb in paginated.items:

            feedback_list.append({

                'id': fb.id,

                'name': fb.name if not fb.is_anonymous else 'Anonymous',

                'rating': fb.rating,

                'comment': fb.comment,

                'category': fb.category,

                'created_at': fb.created_at.isoformat(),

                'is_verified': fb.is_verified,

                'admin_response': fb.admin_response

            })

        

        # Calculate average rating

        avg_rating = db.session.query(db.func.avg(Feedback.rating)).scalar() or 0

        

        return jsonify({

            "success": True,

            "feedback": feedback_list,

            "total": paginated.total,

            "pages": paginated.pages,

            "current_page": page,

            "average_rating": round(float(avg_rating), 1),

            "rating_distribution": {

                "5": Feedback.query.filter_by(rating=5).count(),

                "4": Feedback.query.filter_by(rating=4).count(),

                "3": Feedback.query.filter_by(rating=3).count(),

                "2": Feedback.query.filter_by(rating=2).count(),

                "1": Feedback.query.filter_by(rating=1).count()

            }

        })

        

    except Exception as e:

        return jsonify({"success": False, "message": str(e)}), 500





@app.route('/api/feedback/stats', methods=['GET'])

def api_feedback_stats():

    """Get feedback statistics."""

    from models.user_model import Feedback

    

    try:

        total_feedback = Feedback.query.count()

        avg_rating = db.session.query(db.func.avg(Feedback.rating)).scalar() or 0

        

        # Recent feedback (last 30 days)

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        recent_count = Feedback.query.filter(Feedback.created_at >= thirty_days_ago).count()

        

        # Verified reviews

        verified_count = Feedback.query.filter_by(is_verified=True).count()

        

        return jsonify({

            "success": True,

            "total_feedback": total_feedback,

            "average_rating": round(float(avg_rating), 1),

            "recent_feedback_count": recent_count,

            "verified_reviews_count": verified_count,

            "rating_breakdown": {

                "excellent": Feedback.query.filter(Feedback.rating >= 5).count(),

                "good": Feedback.query.filter(Feedback.rating == 4).count(),

                "average": Feedback.query.filter(Feedback.rating == 3).count(),

                "poor": Feedback.query.filter(Feedback.rating <= 2).count()

            }

        })

        

    except Exception as e:

        return jsonify({"success": False, "message": str(e)}), 500









# ========================================================================
# Role Guide Search API
# ========================================================================
# Resume Optimization API

@app.route('/api/resume-optimize', methods=['POST'])

def api_resume_optimize():

    data = request.get_json() or {}

    text = data.get('resume_text', '')

    target_role = data.get('target_role', '')



    if not text.strip():

        return jsonify({"error": "Please provide resume text"}), 400



    analysis = analyze_resume_text(text, target_role)

    role_skills = get_role_skills(target_role) if target_role else []



    optimized = {}



    skills_str = ", ".join(analysis['resume_skills'][:5]) if analysis['resume_skills'] else "your technical skills"

    optimized['summary'] = (

        f"Results-driven {target_role or 'software professional'} with expertise in {skills_str}. "

        f"Proven track record of delivering high-quality solutions and driving technical excellence. "

        f"Passionate about building scalable systems and collaborating with cross-functional teams."

    )



    optimized['headline'] = f"{target_role or 'Software Engineer'} | {skills_str} | Building Scalable Solutions"



    if target_role:

        missing_skills = [s for s in role_skills if s.lower() not in {r.lower() for r in analysis['resume_skills']}]

        optimized['keywords_to_add'] = missing_skills[:10]

    else:

        optimized['keywords_to_add'] = []



    optimized['section_improvements'] = []

    if not analysis['sections_detected'].get('summary'):

        optimized['section_improvements'].append({

            'section': 'Summary',

            'suggestion': 'Add a professional summary with 2-3 lines highlighting your key skills and career goals',

            'priority': 'High'

        })

    if not analysis['sections_detected'].get('projects'):

        optimized['section_improvements'].append({

            'section': 'Projects',

            'suggestion': 'Add 2-3 projects with descriptions, technologies used, and impact/results',

            'priority': 'High'

        })

    if not analysis['sections_detected'].get('certifications'):

        optimized['section_improvements'].append({

            'section': 'Certifications',

            'suggestion': 'Add relevant certifications to boost credibility',

            'priority': 'Medium'

        })



    return jsonify({

        "optimized": optimized,

        "original_score": analysis['ats_score'],

        "suggestions": analysis['suggestions']

    })





# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================


# ========================================================================
# Role Guide Search API
# ========================================================================




CHAT_PRIVACY_POLICY = {

    "title": "JobAgent Community Chat - Privacy & Conduct Policy",

    "last_updated": "2026-08-06",

    "sections": [

        {

            "icon": "fa-briefcase",

            "title": "Professional Chat Only",

            "content": "This chat group is strictly for professional discussions related to jobs, career advice, interview experiences, skill sharing, and feedback about the JobAgent platform. Any miscellaneous, off-topic, or spam messages will result in immediate removal from the group."

        },

        {

            "icon": "fa-ban",

            "title": "Zero Tolerance for Misconduct",

            "content": "Any form of harassment, hate speech, discrimination, abusive language, bullying, or inappropriate content is strictly prohibited. Violators will be permanently banned from the chat and reported to administrators."

        },

        {

            "icon": "fa-shield-halved",

            "title": "Privacy & Confidentiality",

            "content": "Do not share personal contact information (phone numbers, personal emails, home addresses) in the group without explicit consent. Respect the privacy of fellow members. Never share confidential information about companies, interviews, or proprietary data."

        },

        {

            "icon": "fa-comment-slash",

            "title": "No Spam or Promotions",

            "content": "Unsolicited promotion, advertising, self-promotion links, MLM schemes, or spam messages are forbidden. Job postings and relevant professional resources are allowed within reason."

        },

        {

            "icon": "fa-handshake",

            "title": "Be Respectful & Professional",

            "content": "Treat every member with respect and professionalism. Constructive criticism is welcome, but personal attacks are not. Disagreements should be handled maturely and professionally."

        },

        {

            "icon": "fa-gavel",

            "title": "Enforcement",

            "content": "Any violation of this policy may result in warnings, temporary suspension, or permanent removal from the group at the administrators' discretion. Repeated violations will lead to automatic permanent ban."

        }

    ],

    "disclaimer": "By clicking 'Accept', you agree to abide by these rules. The administrators reserve the right to remove any user who violates this policy without prior notice.",

    "banned_message": "You have been banned from the JobAgent community chat due to a policy violation. Please contact support if you believe this is a mistake."

}



def _get_chat_status(user):

    """Get or create chat status for user."""

    status = ChatUserStatus.query.filter_by(user_id=user.id).first()

    if not status:

        status = ChatUserStatus(user_id=user.id)

        db.session.add(status)

        db.session.commit()

    return status





def _check_chat_access(user):

    """Check if user has access to chat. Returns (allowed, message)."""

    if not user.is_authenticated:

        return False, "Please log in to access the community chat."

    status = _get_chat_status(user)

    if status.is_banned:

        return False, status.ban_reason or CHAT_PRIVACY_POLICY['banned_message']

    if not status.has_accepted_policy:

        return False, "policy_required"

    return True, ""





@app.route('/api/chat/policy', methods=['GET'])

@login_required

def api_chat_policy():

    """Get chat privacy policy."""

    status = _get_chat_status(current_user)

    return jsonify({

        'policy': CHAT_PRIVACY_POLICY,

        'has_accepted': status.has_accepted_policy,

        'is_banned': status.is_banned,

        'ban_reason': status.ban_reason

    })




@app.route('/api/chat/accept-policy', methods=['POST'])

@login_required

def api_chat_accept_policy():

    """Accept the chat privacy policy (idempotent, one join message ever)."""

    status = _get_chat_status(current_user)

    if status.is_banned:

        return jsonify({'success': False, 'message': status.ban_reason or 'You are banned from the chat.'}), 403

    first_time_acceptance = not status.has_accepted_policy

    status.has_accepted_policy = True

    status.accepted_at = status.accepted_at or datetime.utcnow()

    db.session.commit()

    # System message announcing the user joined - inserted only on the
    # very first acceptance so repeated calls never duplicate it.
    if first_time_acceptance:

        existing_join = ChatMessage.query.filter_by(

            user_id=current_user.id, message_type='system').first()

        if not existing_join:

            welcome = ChatMessage(

                user_id=current_user.id,

                message=f"= {current_user.username} has joined the JobAgent community chat!",

                message_type='system'

            )

            db.session.add(welcome)

            db.session.commit()

    return jsonify({'success': True, 'accepted': True,

                    'message': 'Policy accepted. Welcome to the community chat!'})





@app.route('/api/chat/messages', methods=['GET'])

@login_required

def api_chat_messages():

    """Get recent chat messages."""

    allowed, msg = _check_chat_access(current_user)

    if not allowed:

        return jsonify({'success': False, 'message': msg, 'policy_required': msg == 'policy_required'}), 403

    

    limit = request.args.get('limit', 100, type=int)

    before_id = request.args.get('before_id', type=int)

    

    query = ChatMessage.query.filter_by(is_deleted=False).order_by(ChatMessage.created_at.desc())

    if before_id:

        query = query.filter(ChatMessage.id < before_id)

    

    messages = query.limit(limit).all()

    

    # Return in chronological order

    messages.reverse()

    

    return jsonify({

        'success': True,

        'messages': [m.to_dict() for m in messages],

        'online_count': User.query.filter_by(is_active=True).count()

    })





@app.route('/api/chat/send', methods=['POST'])

@login_required

def api_chat_send():

    """Send a chat message."""

    allowed, msg = _check_chat_access(current_user)

    if not allowed:

        return jsonify({'success': False, 'message': msg, 'policy_required': msg == 'policy_required'}), 403

    

    data = request.get_json() or {}

    message_text = data.get('message', '').strip()

    

    if not message_text:

        return jsonify({'success': False, 'message': 'Message cannot be empty.'}), 400

    

    if len(message_text) > 1000:

        return jsonify({'success': False, 'message': 'Message is too long (max 1000 characters).'}), 400

    

    # Basic profanity/inappropriate content check

    inappropriate_sentinel = ['spam', 'scam', 'paid promotion', 'click here to win']

    message_lower = message_text.lower()

    auto_flag = any(s in message_lower for s in inappropriate_sentinel)

    

    message = ChatMessage(

        user_id=current_user.id,

        message=message_text,

        message_type='text',

        is_flagged=auto_flag,

        flag_reason='Auto-flagged: Contains potentially promotional content' if auto_flag else None

    )

    db.session.add(message)

    db.session.commit()

    

    return jsonify({

        'success': True,

        'message_obj': message.to_dict()

    })





@app.route('/api/chat/feedback', methods=['POST'])

@login_required

def api_chat_feedback():

    """Submit feedback about the app via chat."""

    allowed, msg = _check_chat_access(current_user)

    if not allowed:

        return jsonify({'success': False, 'message': msg, 'policy_required': msg == 'policy_required'}), 403

    

    data = request.get_json() or {}

    feedback_text = data.get('feedback', '').strip()

    

    if not feedback_text:

        return jsonify({'success': False, 'message': 'Feedback cannot be empty.'}), 400

    

    if len(feedback_text) > 2000:

        return jsonify({'success': False, 'message': 'Feedback is too long (max 2000 characters).'}), 400

    

    # Save as a special feedback message in chat

    message = ChatMessage(

        user_id=current_user.id,

        message=f"= App Feedback from {current_user.username}: {feedback_text}",

        message_type='feedback'

    )

    db.session.add(message)

    db.session.commit()

    

    # Also try to save to feedback table

    try:

        from models.user_model import Feedback

        feedback = Feedback(

            user_id=current_user.id,

            name=current_user.username,

            email=current_user.email,

            rating=5,

            comment=feedback_text,

            category='chat_feedback',

            is_anonymous=False

        )

        db.session.add(feedback)

        db.session.commit()

    except Exception:

        db.session.rollback()

    

    return jsonify({

        'success': True,

        'message': 'Thank you for your feedback! It has been shared with the community.',

        'message_obj': message.to_dict()

    })





@app.route('/api/chat/users', methods=['GET'])

@login_required

def api_chat_users():

    """Get list of users in the chat."""

    allowed, msg = _check_chat_access(current_user)

    if not allowed:

        return jsonify({'success': False, 'message': msg, 'policy_required': msg == 'policy_required'}), 403

    

    # ========================================================================
# Role Guide Search API
# ========================================================================


    statuses = ChatUserStatus.query.filter_by(has_accepted_policy=True, is_banned=False).all()

    users = []

    for s in statuses:

        if s.user:

            users.append({

                'id': s.user.id,

                'username': s.user.username,

                'joined_at': s.accepted_at.isoformat() if s.accepted_at else None,

            })

    

    return jsonify({

        'success': True,

        'users': users,

        'count': len(users)

    })





# ========================================================================
# Role Guide Search API
# ========================================================================
# End of APIs in the app

# Start the notification scheduler when the module is imported by a WSGI
# server (gunicorn/Render) as well as by `python app.py`. Set
# NOTIFY_SCHEDULER_START_ON_IMPORT=0 on hosts that use a cron job instead.

if os.environ.get('NOTIFY_SCHEDULER_START_ON_IMPORT', '1') == '1':

    try:

        from services.notifications.scheduler import start_notification_scheduler

        start_notification_scheduler(app)

    except Exception:

        pass


if __name__ == '__main__':

    _port = int(os.environ.get('PORT', '5000'))

    _host = os.environ.get('HOST', '0.0.0.0')

    app.run(debug=os.environ.get('FLASK_DEBUG', '1') == '1', host=_host, port=_port)

