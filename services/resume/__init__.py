"""
services/resume - local resume intelligence layer.

Pipeline: document -> text -> sections -> entities -> normalized resume.
All local, no paid/cloud AI APIs.
"""
from services.resume.extractor import (  # noqa: F401
    extract_resume, extraction_capabilities,
)
from services.resume.skill_intelligence import (  # noqa: F401
    extract_skills, analyze_skills, normalize_skill, is_known_skill,
)