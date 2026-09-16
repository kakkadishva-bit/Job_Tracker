"""
services/resume/skill_registry.py
Canonical skill taxonomy with aliases for the skill intelligence layer.

Design rules:
  - canonical_name is the normalized name stored on every skill record
  - aliases are alternate spellings/short forms found in real resumes
  - acronyms (ML, AI, NLP, ...) are matched case-sensitively to avoid
    false positives inside ordinary words
  - ambiguous single-letter/word skills (C, R, Go, Java vs JavaScript,
    React vs React Native, MySQL vs SQL) use GUARDS so different
    technologies are never merged
"""
from typing import Dict, List, Optional

# ── Alias -> canonical normalisation (spec examples) ────────────────
ALIAS_TO_CANONICAL: Dict[str, str] = {
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "machine-learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision", "computer vision": "Computer Vision",
    "js": "JavaScript", "javascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "reactjs": "React", "react.js": "React", "react": "React",
    "react native": "React Native",
    "nodejs": "Node.js", "node.js": "Node.js", "node": "Node.js",
    "expressjs": "Express.js", "express.js": "Express.js",
    "express": "Express.js",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "go": "Go", "golang": "Go",
    "r": "R",
    "ci/cd": "CI/CD", "ci cd": "CI/CD", "cicd": "CI/CD",
    "aws": "Amazon Web Services",
    "amazon web services": "Amazon Web Services",
    "gcp": "Google Cloud Platform", "google cloud": "Google Cloud Platform",
    "azure": "Microsoft Azure", "microsoft azure": "Microsoft Azure",
    "pytorch": "PyTorch", "tensorflow": "TensorFlow",
    "golang": "Go", "java": "Java",
    "c": "C", "c++": "C++", "cpp": "C++", "c#": "C#", "csharp": "C#",
    "python": "Python", "sql": "SQL", "mysql": "MySQL",
    "html": "HTML", "html5": "HTML", "css": "CSS", "css3": "CSS",
    "docker": "Docker", "terraform": "Terraform", "jenkins": "Jenkins",
    "git": "Git", "github": "Git", "gitlab": "Git",
    "apache spark": "Apache Spark", "spark": "Apache Spark",
    "pandas": "Pandas", "numpy": "NumPy",
    "scikit-learn": "Scikit-learn", "sklearn": "Scikit-learn",
    "xgboost": "XGBoost", "keras": "Keras",
    "matplotlib": "Matplotlib", "seaborn": "Seaborn",
    "hugging face": "Hugging Face", "huggingface": "Hugging Face",
    "transformers": "Hugging Face", "bert": "Hugging Face",
    "mlflow": "MLflow", "spacy": "SpaCy", "nltk": "NLTK",
    "opencv": "OpenCV",
    "fastapi": "FastAPI", "flask": "Flask", "django": "Django",
    "spring boot": "Spring Boot", "dotnet": "ASP.NET",
    "asp.net": "ASP.NET", "laravel": "Laravel",
    "rails": "Ruby on Rails", "ruby on rails": "Ruby on Rails",
    "webpack": "Webpack", "vite": "Vite", "redux": "Redux",
    "jquery": "jQuery", "bootstrap": "Bootstrap",
    "tailwind": "Tailwind CSS", "tailwind css": "Tailwind CSS",
    "rest api": "REST API", "restful": "REST API", "graphql": "GraphQL",
    "grpc": "gRPC", "microservices": "Microservices",
    "agile": "Agile", "scrum": "Scrum",
    "tdd": "Test-Driven Development",
    "unit testing": "Unit Testing", "pytest": "Unit Testing",
    "junit": "Unit Testing", "selenium": "Selenium", "cypress": "Cypress",
    "linux": "Linux", "bash": "Bash", "shell scripting": "Bash",
    "redis": "Redis", "elasticsearch": "Elasticsearch",
    "sqlite": "SQLite", "dynamodb": "DynamoDB", "snowflake": "Snowflake",
    "airflow": "Apache Airflow", "apache airflow": "Apache Airflow",
    "kafka": "Apache Kafka", "apache kafka": "Apache Kafka",
    "etl": "Data Engineering", "data pipeline": "Data Engineering",
    "big data": "Data Engineering", "mlops": "MLOps",
    "deep learning": "Deep Learning",
    "reinforcement learning": "Deep Learning",
    "computer vision": "Computer Vision", "ocr": "Computer Vision",
    "prompt engineering": "Generative AI", "llm": "Generative AI",
    "llms": "Generative AI", "generative ai": "Generative AI",
    "rag": "Generative AI", "langchain": "LangChain",
    "owasp": "Application Security",
    "penetration testing": "Penetration Testing",
    "oauth": "OAuth", "jwt": "JWT", "cryptography": "Cryptography",
    "leadership": "Leadership", "communication": "Communication",
    "teamwork": "Teamwork", "problem solving": "Problem Solving",
    "mentoring": "Mentoring", "project management": "Project Management",
    "excel": "Microsoft Excel", "power bi": "Power BI",
    "tableau": "Tableau", "jira": "Jira", "figma": "Figma",
    "postman": "Postman", "swagger": "Swagger",
}

# Alias spellings that regex must treat specially (regex chars / variants).
SPECIAL_PATTERNS = {
    "c++": r"c\+\+", "c#": r"c#", "asp.net": r"asp\.net",
    "node.js": r"node\.?js", "vue.js": r"vue\.?js",
    "express.js": r"express\.?js", "next.js": r"next\.?js",
    "ci/cd": r"ci\s*/?\s*cd", "c++": r"c\+\+",
}

# Ambiguous skills that need context in the same sentence (case-sensitive).
CONTEXT_GATED = {"C", "R", "Go", "AI", "ML", "CV", "NLP", "SQL"}

# Canonical -> exclusion regex fragments (never merged technologies).
EXCLUSIONS = {
    "React": [r"native"],
    "Java": [r"script", r"ee"],
    "C": [r"\+\+", r"#"],
}
# Canonical skill metadata (category per canonical name).
CATEGORIES: Dict[str, str] = {
    "Python": "Programming Languages", "Java": "Programming Languages",
    "JavaScript": "Programming Languages",
    "TypeScript": "Programming Languages",
    "Go": "Programming Languages", "C": "Programming Languages",
    "C++": "Programming Languages", "C#": "Programming Languages",
    "R": "Programming Languages", "SQL": "Programming Languages",
    "Bash": "Programming Languages",
    "HTML": "Frontend", "CSS": "Frontend", "React": "Frontend",
    "Redux": "Frontend", "Webpack": "Frontend", "Vite": "Frontend",
    "jQuery": "Frontend", "Bootstrap": "Frontend",
    "Tailwind CSS": "Frontend", "Angular": "Frontend",
    "Vue.js": "Frontend", "React Native": "Mobile",
    "Django": "Backend", "Flask": "Backend", "FastAPI": "Backend",
    "Express.js": "Backend", "Node.js": "Backend",
    "Spring Boot": "Backend", "ASP.NET": "Backend", "Laravel": "Backend",
    "Ruby on Rails": "Backend", "REST API": "Backend",
    "GraphQL": "Backend", "gRPC": "Backend", "Microservices": "Backend",
    "MySQL": "Databases", "PostgreSQL": "Databases", "MongoDB": "Databases",
    "Redis": "Databases", "Elasticsearch": "Databases",
    "SQLite": "Databases", "DynamoDB": "Databases",
    "Snowflake": "Databases",
    "Amazon Web Services": "Cloud", "Google Cloud Platform": "Cloud",
    "Microsoft Azure": "Cloud",
    "Docker": "DevOps", "Kubernetes": "DevOps", "Terraform": "DevOps",
    "Jenkins": "DevOps", "Linux": "DevOps", "CI/CD": "DevOps",
    "Git": "Tools", "Jira": "Tools", "Figma": "Tools",
    "Postman": "Tools", "Swagger": "Tools", "Tableau": "Tools",
    "Power BI": "Tools", "Microsoft Excel": "Tools",
    "Machine Learning": "Machine Learning",
    "Deep Learning": "Deep Learning",
    "Artificial Intelligence": "Artificial Intelligence",
    "Natural Language Processing": "NLP",
    "Computer Vision": "Computer Vision",
    "Generative AI": "Generative AI", "LangChain": "Generative AI",
    "Pandas": "Data Science", "NumPy": "Data Science",
    "Scikit-learn": "Data Science", "Matplotlib": "Data Science",
    "Seaborn": "Data Science", "Statistics": "Data Science",
    "PyTorch": "Deep Learning", "TensorFlow": "Deep Learning",
    "Keras": "Deep Learning", "XGBoost": "Machine Learning",
    "Hugging Face": "Machine Learning", "SpaCy": "NLP", "NLTK": "NLP",
    "OpenCV": "Computer Vision",
    "Apache Spark": "Data Engineering",
    "Apache Airflow": "Data Engineering",
    "Apache Kafka": "Data Engineering",
    "Data Engineering": "Data Engineering", "MLflow": "MLOps",
    "Application Security": "Cybersecurity",
    "Penetration Testing": "Cybersecurity", "OAuth": "Cybersecurity",
    "JWT": "Cybersecurity", "Cryptography": "Cybersecurity",
    "Unit Testing": "Testing", "Selenium": "Testing",
    "Cypress": "Testing", "Test-Driven Development": "Testing",
    "Agile": "Practices", "Scrum": "Practices",
    "Leadership": "Soft Skills", "Communication": "Soft Skills",
    "Teamwork": "Soft Skills", "Problem Solving": "Soft Skills",
    "Mentoring": "Soft Skills", "Project Management": "Soft Skills",
}


def canonical_for(alias: str) -> Optional[str]:
    """Normalise any alias to its canonical name (or None if unknown)."""
    return ALIAS_TO_CANONICAL.get(alias.strip().lower())


def category_for(canonical: str) -> str:
    return CATEGORIES.get(canonical, "Other")


def aliases_for(canonical: str) -> List[str]:
    return [a for a, c in ALIAS_TO_CANONICAL.items() if c == canonical]


def is_context_gated(canonical: str) -> bool:
    return canonical in CONTEXT_GATED


def is_acronym(canonical: str) -> bool:
    return canonical in CONTEXT_GATED or canonical in {
        "ML", "AI", "NLP", "CV", "JS", "TS", "SQL", "AWS", "GCP",
        "K8s", "CI/CD"}