"""
tests/test_job_matching.py - Part 2b-2: Score, recommendations, edge cases.
"""
import pytest
from services.matching import match_resume_to_job
from services.matching.matcher import MatchResult


class TestScoreCalculation:
    def test_score_range(self):
        resume = {
            "skills": [{"skill": "Python", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "raw_text": "Python developer",
        }
        jd = "Required: Python, Machine Learning"
        result = match_resume_to_job(resume, jd)
        assert 0 <= result.score <= 100

    def test_higher_score_for_better_match(self):
        jd = "Required: Python, Machine Learning, Docker"
        good_resume = {
            "skills": [
                {"skill": "Python", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 5, "evidence": []},
                {"skill": "Machine Learning", "category": "Field", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 4, "evidence": []},
                {"skill": "Docker", "category": "Tool", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []},
            ],
            "experience": [{"job_title": "ML Engineer", "company": "X", "duration": "3 years", "highlights": []}],
            "education": [{"degree": "M.Tech", "institution": "IIT", "year": "2020"}],
            "contact": {"email": "test@test.com", "phone": "1234567890"},
            "raw_text": "Python ML Docker experience",
        }
        bad_resume = {
            "skills": [{"skill": "Python", "category": "Language", "confidence": 0.5, "strength": "LIMITED", "source": "skills", "mentions": 1, "evidence": []}],
            "experience": [],
            "education": [],
            "contact": {},
            "raw_text": "Python",
        }
        good_result = match_resume_to_job(good_resume, jd)
        bad_result = match_resume_to_job(bad_resume, jd)
        assert good_result.score > bad_result.score


class TestRecommendations:
    def test_apply_recommendation(self):
        resume = {
            "skills": [
                {"skill": "Python", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 5, "evidence": []},
                {"skill": "Docker", "category": "Tool", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []},
            ],
            "experience": [{"job_title": "Dev", "company": "X", "duration": "2 years", "highlights": []}],
            "education": [{"degree": "B.Tech", "institution": "IIT", "year": "2020"}],
            "contact": {"email": "test@test.com", "phone": "1234567890"},
            "raw_text": "Python Docker developer",
        }
        jd = "Required: Python, Docker"
        result = match_resume_to_job(resume, jd)
        assert result.recommendation in ("APPLY", "APPLY WITH PREPARATION")

    def test_low_priority_recommendation(self):
        resume = {"skills": [], "experience": [], "raw_text": ""}
        jd = "Required: Python, Machine Learning, Docker, Kubernetes, AWS"
        result = match_resume_to_job(resume, jd)
        assert result.recommendation == "LOW PRIORITY"


class TestEdgeCases:
    def test_empty_resume_and_jd(self):
        result = match_resume_to_job({}, "")
        assert result.score >= 0

    def test_malformed_resume(self):
        resume = {"skills": "not a list"}
        jd = "Required: Python"
        result = match_resume_to_job(resume, jd)
        assert isinstance(result, MatchResult)

    def test_very_long_jd(self):
        jd = "Required: Python\n" * 100 + "Preferred: Docker"
        resume = {
            "skills": [{"skill": "Python", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "raw_text": "Python developer",
        }
        result = match_resume_to_job(resume, jd)
        assert result.score > 0

    def test_special_characters_in_jd(self):
        jd = "Required: Python (3.8+), Docker & Kubernetes, AWS/GCP"
        resume = {
            "skills": [{"skill": "Python", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "raw_text": "Python developer",
        }
        result = match_resume_to_job(resume, jd)
        assert isinstance(result, MatchResult)
