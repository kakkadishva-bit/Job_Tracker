"""
services/resume/taxonomy.py
Skill taxonomy for the resume extraction layer.

The canonical skill lists mirror app.py's SKILLS_DATABASE so the ATS
scoring engine and the extraction layer agree on what counts as a skill.
This module adds what the extraction layer needs on top:
  - ALIASES: normalise spelling/short forms to canonical names
  - SOURCE_WEIGHTS: how much each resume section strengthens a skill
"""
from typing import Dict, List

SKILL_CATEGORIES: Dict[str, List[str]] = {
    "programming_languages": [
        "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go",
        "Rust", "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "MATLAB",
        "Dart", "Elixir", "Haskell", "Lua", "Perl", "SQL", "Bash",
        "HTML5", "CSS3",
    ],
    "frontend": [
        "React", "Angular", "Vue.js", "SASS", "LESS", "Redux", "Next.js",
        "Nuxt.js", "Svelte", "jQuery", "Bootstrap", "Tailwind CSS",
        "Material UI", "Ant Design", "Webpack", "Vite", "Storybook",
        "Web Components",
    ],
    "backend": [
        "Node.js", "Express.js", "Django", "Flask", "FastAPI",
        "Spring Boot", "Ruby on Rails", "ASP.NET", "Laravel", "NestJS",
        "Gin", "Echo", "Fiber", "Actix", "Phoenix", "Ktor",
    ],
    "databases": [
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "SQLite", "Oracle", "SQL Server", "Cassandra", "DynamoDB",
        "Firebase", "Supabase", "Neo4j", "CouchDB", "InfluxDB",
        "TimescaleDB", "ClickHouse", "Snowflake",
    ],
    "cloud": [
        "AWS", "Azure", "GCP", "Heroku", "DigitalOcean", "Vultr",
        "Linode", "Cloudflare", "Vercel", "Netlify",
    ],
    "devops": [
        "Docker", "Kubernetes", "Jenkins", "GitLab CI", "GitHub Actions",
        "Terraform", "Ansible", "Puppet", "Chef", "Prometheus", "Grafana",
        "Nagios", "CircleCI", "Travis CI", "ArgoCD", "Helm", "Istio",
        "Pulumi",
    ],
    "ai_ml": [
        "TensorFlow", "PyTorch", "Scikit-learn", "Keras", "OpenCV",
        "NLTK", "SpaCy", "Hugging Face", "LangChain", "Pandas", "NumPy",
        "Matplotlib", "Seaborn", "XGBoost", "LightGBM", "MLflow",
        "Kubeflow", "Apache Spark", "Databricks", "Jupyter",
    ],
    "mobile": [
        "React Native", "Flutter", "SwiftUI", "Jetpack Compose",
        "Xamarin", "Ionic", "Cordova", "Android SDK", "iOS SDK",
    ],
    "tools": [
        "Git", "GitHub", "GitLab", "Bitbucket", "Jira", "Confluence",
        "Slack", "Notion", "Figma", "Adobe XD", "Postman", "Swagger",
        "VS Code", "IntelliJ IDEA", "PyCharm", "Vim", "Neovim",
    ],
    "methodologies": [
        "Agile", "Scrum", "Kanban", "TDD", "BDD", "CI/CD",
        "Microservices", "REST API", "GraphQL", "gRPC", "WebSockets",
        "Event-Driven Architecture", "Domain-Driven Design", "Serverless",
        "12-Factor App",
    ],
    "security": [
        "OAuth", "JWT", "SSL/TLS", "OWASP", "Penetration Testing",
        "SIEM", "Cryptography", "IAM", "Security Auditing",
        "Vulnerability Assessment",
    ],
}

# Normalisation map: raw token seen in resumes -> canonical taxonomy name.
ALIASES: Dict[str, str] = {
    "js": "JavaScript", "nodejs": "Node.js", "node": "Node.js",
    "vue": "Vue.js", "vuejs": "Vue.js", "nextjs": "Next.js",
    "nuxtjs": "Nuxt.js", "golang": "Go", "py": "Python",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "psql": "PostgreSQL", "mongo": "MongoDB", "mssql": "SQL Server",
    "k8s": "Kubernetes", "tf": "Terraform", "gh actions":
        "GitHub Actions", "ci cd": "CI/CD", "cicd": "CI/CD",
    "rest": "REST API", "restful": "REST API", "grpc": "gRPC",
    "amazon web services": "AWS", "microsoft azure": "Azure",
    "google cloud": "GCP", "gcp": "GCP", "sklearn": "Scikit-learn",
    "scikit": "Scikit-learn", "pytorch": "PyTorch", "tf2": "TensorFlow",
    "hf": "Hugging Face", "huggingface": "Hugging Face",
    "cpp": "C++", "c sharp": "C#", "csharp": "C#", "dotnet": "ASP.NET",
    ".net": "ASP.NET", "adobe xd": "Adobe XD", "vscode": "VS Code",
    "vs code": "VS Code", "ml": "Machine Learning", "nlp": "NLP",
    "springboot": "Spring Boot", "rb": "Ruby on Rails",
    "tailwind": "Tailwind CSS", "sass": "SASS",
}

# How strongly a section supports that a candidate truly has a skill.
SOURCE_WEIGHTS: Dict[str, float] = {
    "projects": 0.90,
    "experience": 0.88,
    "achievements": 0.85,
    "summary": 0.65,
    "education": 0.55,
    "header": 0.50,
    "contact": 0.40,
    "skills": 0.35,   # listing alone is the weakest evidence
}

# Thresholds for the strength label derived from confidence.
STRONG_THRESHOLD = 0.75
MEDIUM_THRESHOLD = 0.50


def strength_label(confidence: float) -> str:
    if confidence >= STRONG_THRESHOLD:
        return "strong"
    if confidence >= MEDIUM_THRESHOLD:
        return "medium"
    return "weak"


def all_skills() -> Dict[str, str]:
    """Flattened {canonical_name_lower: canonical_name} lookup."""
    flat: Dict[str, str] = {}
    for skills in SKILL_CATEGORIES.values():
        for s in skills:
            flat[s.lower()] = s
    return flat


def skill_category(skill: str) -> str:
    for cat, skills in SKILL_CATEGORIES.items():
        if skill in skills:
            return cat
    return "other"


def canonical_skill(raw: str) -> str:
    """Normalise a raw token through ALIASES, else title-ish fallback."""
    key = raw.strip().lower()
    if key in ALIASES:
        return ALIASES[key]
    flat = all_skills()
    if key in flat:
        return flat[key]
    return raw.strip()