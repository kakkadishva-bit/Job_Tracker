# Job Matching Engine (Step 5)

## Overview

The Explainable Resume ↔ Job Matching Engine calculates a match score (0-100) between a resume and a job description, providing detailed explanations, skill gaps, and recommendations.

## Status: COMPLETE

## Architecture

```
Resume (structured) + Job Description (raw text)
    ↓
JD Analysis (jd_analyzer.py)
    - Required skills
    - Preferred skills
    - Responsibilities
    - Experience years
    - Seniority level
    - Education
    - Certifications
    - Work mode
    ↓
Matching (matcher.py)
    - Exact skill matching (with false-match prevention)
    - Evidence strength scoring
    - Experience relevance
    - Seniority compatibility
    ↓
Scoring (scorer.py)
    - Job relevance: 30%
    - Evidence strength: 20%
    - Technical skills: 15%
    - Experience relevance: 15%
    - ATS compatibility: 10%
    - Achievements: 5%
    - Education/Certs: 5%
    ↓
Result
    - Score / 100
    - Matched/missing required skills
    - Matched/missing preferred skills
    - Recommendation (APPLY / APPLY WITH PREPARATION / LOW PRIORITY)
    - Detailed explanation
```

## API

### `match_resume_to_job(resume, job_description)`

Main entry point for matching.

**Args:**
- `resume`: Extracted resume structure (from `services.resume.extractor`)
- `job_description`: Raw job description text

**Returns:** `MatchResult` with:
- `score`: float (0-100)
- `recommendation`: "APPLY" | "APPLY WITH PREPARATION" | "LOW PRIORITY"
- `matched_required`: List[str]
- `missing_required`: List[str]
- `matched_preferred`: List[str]
- `missing_preferred`: List[str]
- `evidence`: Dict[str, Dict]
- `explanation`: List[str]

### `analyze_job_description(text)`

Analyze a job description and extract structured information.

**Args:**
- `text`: Raw job description text

**Returns:** `JobDescription` with:
- `title`: str
- `required_skills`: List[str]
- `preferred_skills`: List[str]
- `responsibilities`: List[str]
- `experience_years_min`: Optional[int]
- `experience_years_max`: Optional[int]
- `seniority`: Optional[str]
- `education`: List[str]
- `certifications`: List[str]
- `work_mode`: Optional[str]
- `all_skills`: List[str]

## Scoring Weights

| Component | Weight | Description |
|-----------|--------|-------------|
| Job relevance | 30% | Skill overlap between resume and JD |
| Evidence strength | 20% | Quality of resume evidence for matched skills |
| Technical skills | 15% | Technical skill matches |
| Experience relevance | 15% | Years of experience and seniority match |
| ATS compatibility | 10% | Resume structure quality |
| Achievements | 5% | Quantifiable achievements |
| Education/Certs | 5% | Education and certification match |

## False Match Prevention

The engine prevents false matches between similar-sounding skills:

- Java ≠ JavaScript
- C ≠ C++
- C ≠ C#
- React ≠ React Native
- AWS ≠ Azure
- MySQL ≠ PostgreSQL
- Go ≠ R
- Vue ≠ React
- TensorFlow ≠ PyTorch

## Recommendation Logic

| Score | Missing Critical | Recommendation |
|-------|------------------|----------------|
| >= 70 | 0 | APPLY |
| >= 50 | <= 2 | APPLY WITH PREPARATION |
| < 50 | > 2 | LOW PRIORITY |

## Usage Example

```python
from services.matching import match_resume_to_job
from services.resume.extractor import extract_resume

# Extract resume
resume = extract_resume(text="John Doe...")

# Match against job description
result = match_resume_to_job(resume, """
    Machine Learning Engineer
    Required: Python, Machine Learning, Docker
    Experience: 3+ years
""")

print(f"Score: {result.score}/100")
print(f"Recommendation: {result.recommendation}")
print(f"Matched: {result.matched_required}")
print(f"Missing: {result.missing_required}")
```

## Testing

Run matching tests:

```bash
python -m pytest tests/test_job_matching_part1.py tests/test_job_matching_part2a.py tests/test_job_matching_part2b1.py tests/test_job_matching_part2b2.py -v
```

## Limitations

1. Semantic similarity uses simple cosine similarity (sentence-transformers optional)
2. No deep semantic understanding of responsibilities
3. Keyword stuffing prevention is basic
4. No salary matching
5. No culture fit analysis

## Files

- `services/matching/__init__.py` - Module exports
- `services/matching/jd_analyzer.py` - JD analysis
- `services/matching/matcher.py` - Main matching logic
- `services/matching/scorer.py` - Score calculation
- `tests/test_job_matching_part1.py` - JD analyzer tests
- `tests/test_job_matching_part2a.py` - Matcher tests
- `tests/test_job_matching_part2b1.py` - False match tests
- `tests/test_job_matching_part2b2.py` - Score/recommendation tests
