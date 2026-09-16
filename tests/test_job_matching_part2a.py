"""
tests/test_job_matching.py - Part 2a: Matcher tests.
"""
import pytest
from services.matching import match_resume_to_job
from services.matching.matcher import MatchResult


@pytest.fixture
def sample_resume():
    return {
        "profile": {"name": "John Doe", "years_experience": 4},
        "contact": {"email": "john@example.com", "phone": "1234567890"},
        "skills": [
            {"skill": "Python", "category": "Language", "confidence": 0.95, "strength": "STRONG", "source": "experience", "mentions": 5, "evidence": ["Built Python apps"]},
            {"skill": "Machine Learning", "category": "Field", "confidence": 0.88, "strength": "STRONG", "source": "projects", "mentions": 3, "evidence": ["ML project"]},
            {"skill": "Docker", "category": "Tool", "confidence": 0.70, "strength": "DEVELOPING", "source": "experience", "mentions": 2, "evidence": []},
        ],
        "experience": [
            {"job_title": "ML Engineer", "company": "TechCorp", "duration": "2 years", "highlights": []},
        ],
        "education": [{"degree": "B.Tech", "institution": "IIT", "year": "2020"}],
        "raw_text": "Python ML experience",
    }


@pytest.fixture
def sample_jd():
    return """
Machine Learning Engineer
Required Skills: Python, Machine Learning, Docker, Kubernetes
Preferred Skills: AWS, RAG
Experience Required: 3+ years
"""


class TestMatcher:
    def test_basic_match(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        assert isinstance(result, MatchResult)
        assert 0 <= result.score <= 100

    def test_matched_required(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        assert "Python" in result.matched_required
        assert "Machine Learning" in result.matched_required

    def test_missing_required(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        assert "Kubernetes" in result.missing_required

    def test_recommendation_valid(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        assert result.recommendation in ("APPLY", "APPLY WITH PREPARATION", "LOW PRIORITY")

    def test_score_explanation(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        assert len(result.explanation) > 0

    def test_to_dict(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        d = result.to_dict()
        assert "score" in d
        assert "matched_required" in d

    def test_no_duplicate_skills(self, sample_resume, sample_jd):
        result = match_resume_to_job(sample_resume, sample_jd)
        assert len(result.matched_required) == len(set(result.matched_required))
