"""
tests/test_job_matching.py - Part 1: Fixtures and JD Analyzer tests.
"""
import pytest
from services.matching import match_resume_to_job, analyze_job_description
from services.matching.jd_analyzer import JobDescription
from services.matching.matcher import MatchResult


@pytest.fixture
def sample_resume():
    return {
        "profile": {"name": "John Doe", "years_experience": 4},
        "contact": {"email": "john@example.com", "phone": "1234567890"},
        "skills": [
            {"skill": "Python", "category": "Language", "confidence": 0.95, "strength": "STRONG", "source": "experience", "mentions": 5, "evidence": ["Built Python apps"]},
            {"skill": "Machine Learning", "category": "Field", "confidence": 0.88, "strength": "STRONG", "source": "projects", "mentions": 3, "evidence": ["ML project"]},
            {"skill": "FastAPI", "category": "Framework", "confidence": 0.80, "strength": "DEVELOPING", "source": "experience", "mentions": 2, "evidence": ["FastAPI API"]},
            {"skill": "Docker", "category": "Tool", "confidence": 0.70, "strength": "DEVELOPING", "source": "experience", "mentions": 2, "evidence": ["Docker containers"]},
            {"skill": "AWS", "category": "Cloud", "confidence": 0.60, "strength": "LIMITED", "source": "skills", "mentions": 1, "evidence": []},
            {"skill": "RAG", "category": "Field", "confidence": 0.90, "strength": "STRONG", "source": "projects", "mentions": 4, "evidence": ["Built RAG chatbot using Python, LangChain and FAISS"]},
        ],
        "experience": [
            {"job_title": "ML Engineer", "company": "TechCorp", "duration": "2 years", "highlights": ["Built ML models"]},
            {"job_title": "Python Developer", "company": "StartupXYZ", "duration": "2 years", "highlights": ["Python web apps"]},
        ],
        "education": [{"degree": "B.Tech", "institution": "IIT", "year": "2020"}],
        "projects": [{"name": "RAG Chatbot", "description": "Built RAG chatbot using Python, LangChain and FAISS", "technologies": ["Python", "LangChain", "FAISS"]}],
        "certifications": [{"name": "AWS Certified Developer", "issuer": "AWS", "year": "2023"}],
        "raw_text": "John Doe\njohn@example.com\n\nExperience:\nML Engineer at TechCorp (2 years)\n- Built ML models using Python\n- 50% improvement in accuracy\n\nPython Developer at StartupXYZ (2 years)\n- Python web apps with FastAPI\n- Reduced costs by 20%\n\nProjects:\nRAG Chatbot: Built RAG chatbot using Python, LangChain and FAISS\n\nEducation: B.Tech from IIT 2020\nCertifications: AWS Certified Developer",
    }


@pytest.fixture
def sample_jd():
    return """
Machine Learning Engineer

About the role:
We are looking for a Machine Learning Engineer to join our team.

Required Skills:
- Python
- Machine Learning
- Docker
- Kubernetes
- SQL

Preferred Skills:
- AWS
- RAG
- MLOps
- Terraform

Responsibilities:
- Build and deploy ML models
- Design scalable ML pipelines
- Collaborate with cross-functional teams

Experience Required: 3+ years

Education: Bachelor's degree in Computer Science or related field

Work Mode: Hybrid

Requirements:
- 3+ years of experience in ML engineering
- Strong Python programming skills
- Experience with Docker and Kubernetes
- Knowledge of SQL databases
"""


@pytest.fixture
def empty_jd():
    return ""


@pytest.fixture
def minimal_resume():
    return {
        "profile": {},
        "contact": {},
        "skills": [],
        "experience": [],
        "education": [],
        "projects": [],
        "certifications": [],
        "raw_text": "",
    }


class TestJDAnalyzer:
    def test_extract_required_skills(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        assert "Python" in jd.required_skills
        assert "Machine Learning" in jd.required_skills
        assert "Docker" in jd.required_skills

    def test_extract_preferred_skills(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        # "AWS" is an alias for "Amazon Web Services" in the skill registry
        assert "Amazon Web Services" in jd.preferred_skills or "AWS" in jd.preferred_skills

    def test_extract_seniority(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        # JD may or may not have explicit seniority keywords
        assert jd.seniority in ("mid", "senior", None)

    def test_extract_seniority_explicit(self):
        jd_text = "Senior Machine Learning Engineer - 5+ years experience"
        jd = analyze_job_description(jd_text)
        assert jd.seniority == "senior"

    def test_extract_experience_years(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        assert jd.experience_years_min == 3

    def test_extract_work_mode(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        assert jd.work_mode == "hybrid"

    def test_extract_education(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        assert len(jd.education) > 0

    def test_extract_title(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        assert "Machine Learning" in jd.title or jd.title != ""

    def test_empty_jd(self, empty_jd):
        jd = analyze_job_description(empty_jd)
        assert jd.raw_text == ""
        assert jd.required_skills == []
        assert jd.preferred_skills == []

    def test_no_false_positive_java_vs_javascript(self):
        jd_text = "Required: Java programming"
        jd = analyze_job_description(jd_text)
        for skill in jd.required_skills:
            assert skill.lower() != "javascript"

    def test_no_false_positive_c_vs_cpp(self):
        jd_text = "Required: C programming"
        jd = analyze_job_description(jd_text)
        for skill in jd.required_skills:
            assert skill.lower() != "c++"
            assert skill.lower() != "c#"

    def test_preferred_not_in_required(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        for skill in jd.preferred_skills:
            assert skill not in jd.required_skills

    def test_all_skills_union(self, sample_jd):
        jd = analyze_job_description(sample_jd)
        assert set(jd.all_skills) == set(jd.required_skills + jd.preferred_skills)
