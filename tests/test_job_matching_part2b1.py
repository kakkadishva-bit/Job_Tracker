"""
tests/test_job_matching.py - Part 2b-1: False match tests.
"""
import pytest
from services.matching import match_resume_to_job


class TestFalseMatchPrevention:
    def test_java_not_javascript(self):
        resume = {
            "skills": [{"skill": "Java", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "experience": [{"job_title": "Java Developer", "company": "X", "duration": "2 years", "highlights": []}],
            "raw_text": "Java developer with Spring Boot experience",
        }
        jd = "Required: JavaScript, React, Node.js"
        result = match_resume_to_job(resume, jd)
        assert "Java" not in result.matched_required

    def test_c_not_cpp(self):
        resume = {
            "skills": [{"skill": "C", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "raw_text": "C programming for embedded systems",
        }
        jd = "Required: C++, STL, Boost"
        result = match_resume_to_job(resume, jd)
        for skill in result.matched_required:
            assert skill.lower() != "c++"

    def test_react_not_react_native(self):
        resume = {
            "skills": [{"skill": "React", "category": "Framework", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "raw_text": "React web development with Redux",
        }
        jd = "Required: React Native, Expo, Mobile development"
        result = match_resume_to_job(resume, jd)
        for skill in result.matched_required:
            assert skill.lower() != "react native"

    def test_aws_not_azure(self):
        resume = {
            "skills": [{"skill": "AWS", "category": "Cloud", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []}],
            "raw_text": "AWS cloud services",
        }
        jd = "Required: Azure, .NET, C#"
        result = match_resume_to_job(resume, jd)
        for skill in result.matched_required:
            assert skill.lower() != "azure"

    def test_keyword_stuffing_prevention(self):
        resume = {
            "skills": [
                {"skill": "Python", "category": "Language", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []},
                {"skill": "Docker", "category": "Tool", "confidence": 0.9, "strength": "STRONG", "source": "experience", "mentions": 3, "evidence": []},
            ],
            "raw_text": "Python Docker Kubernetes AWS GCP Terraform Ansible Jenkins",
        }
        jd = "Required: Python, Docker"
        result = match_resume_to_job(resume, jd)
        assert result.score < 100
