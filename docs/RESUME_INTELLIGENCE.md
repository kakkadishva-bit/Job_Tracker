# Resume Intelligence Layer

> **Status:** Implemented (backend only - UI untouched)
> **Constraint compliance:** 100% local. No OpenAI, Gemini, Claude, or
> any paid/cloud AI API is called anywhere in this pipeline.

## 1. What This Is

A local resume extraction pipeline that turns an uploaded resume
(PDF / DOCX / TXT / pasted text) into a normalized, evidence-carrying
structure consumed by the rest of JobAgent (ATS scoring, skill-gap,
matching - later phases).

```
file/text ──► utils/resume_parser.py             (PDF/DOCX/TXT -> text)
          ──► services/resume/section_splitter.py (sections)
          ──► services/resume/ner.py              (entities, backend chain)
          ──► services/resume/skill_extractor.py  (skills + evidence)
          ──► services/resume/extractor.py        (normalized structure)
```

## 2. Components (per docs/ARCHITECTURE.md)

| Concern | Implementation | Deps |
|---|---|---|
| PDF extraction | `pdfplumber` -> `PyPDF2`/`pypdf` -> raw decode fallback | pdfplumber (installed) |
| DOCX extraction | `python-docx` (incl. tables) -> zip/XML fallback | python-docx (installed) |
| TXT extraction | UTF-8 / UTF-8-sig / Latin-1 decode | stdlib |
| Resume NER | **oksomu/resume-ner** (transformers) -> **spaCy en_core_web_sm** -> built-in regex NER | optional; regex always on |
| Skill extraction | taxonomy + word-boundary matching + evidence scoring | stdlib only |

Dependency notes (checked before installing anything):
- `pypdf` was already installed -> **PyPDF2 was not added as a duplicate
  dependency**; `resume_parser` treats `PyPDF2`/`pypdf` as one
  capability (identical API).
- `pdfplumber` + `python-docx` were in requirements.txt but missing from
  the venv -> installed (0.11.8 / 1.2.0).
- `transformers` + `torch` (~2 GB) and `spaCy` are **not installed** on
  this constrained machine; the NER chain auto-detects and falls back to
  the zero-dependency regex NER. `meta.ner_backend` in the output
  reports which backend ran (`regex` today).

## 3. Entity Labels

`PERSON, EMAIL, PHONE, LOCATION, JOB_TITLE, COMPANY, DATE, EDUCATION,
DEGREE, INSTITUTION, SKILL, CERTIFICATION, PROJECT, EXPERIENCE`

The regex layer covers everything deterministically (email/phone/URLs,
dates, degree names, institution suffixes, role patterns, company
suffixes, City/State plus Indian-city knowledge from
`utils.query_parser`). When a model backend is enabled its predictions
are merged on top; model labels map to the canonical set via
`HF_LABEL_MAP`.

Enabling the HF model later (no code changes):

```powershell
pip install transformers torch
$env:RESUME_NER_BACKEND = "auto"     # or "regex" to force the light path
```

## 4. Normalized Structure

Returned by `services.resume.extract_resume()` and attached to
`/api/analyze-resume` responses under the `extracted` key:

```json
{
  "profile":   {"name": "Priya Sharma", "headline": "Frontend Developer",
                "summary": null, "years_experience": 4},
  "contact":   {"email": "...", "phone": "...", "linkedin": "...",
                "github": null, "portfolio": null,
                "location": "Mumbai, India"},
  "skills":    [{"skill": "React", "category": "frontend",
                 "confidence": 0.93,
                 "evidence": ["Built reusable React components with..."],
                 "source": "experience", "strength": "strong",
                 "sections_seen": ["skills", "experience", "projects"]}],
  "experience":[{"job_title": "Frontend Developer",
                 "company": "WebWorks Solutions", "location": null,
                 "start": "Jun 2021", "end": "Present",
                 "duration": "Jun 2021 - Present",
                 "highlights": ["Built reusable React components..."]}],
  "education": [{"degree": "B.Sc", "institution": "Mumbai University",
                 "year": "2019", "details": ["..."]}],
  "projects":  [{"name": "Portfolio Site",
                 "description": "personal portfolio built with...",
                 "technologies": ["React", "Tailwind CSS"]}],
  "certifications": [{"name": "AWS Certified Solutions Architect, 2022",
                      "issuer": null, "year": "2022"}],
  "raw_text":  "full extracted text",
  "meta":      {"parser_engine": "pdfplumber",
                "ner_backend": "regex", "warnings": []}
}
```
## 5. Skill Evidence Model (never keyword-trust alone)

Every skill carries a confidence derived from **where** it appears, not
just that it appears:

| Section found in | Base confidence |
|---|---|
| projects | 0.90 |
| experience | 0.88 |
| achievements | 0.85 |
| summary | 0.65 |
| education | 0.55 |
| header (headline) | 0.50 |
| contact | 0.40 |
| skills (list only) | 0.35 |

Adjustments:
- **+0.05** per additional distinct section mentioning the skill
  (corroboration), capped overall at **0.98**.
- **+0.02** per extra evidence sentence in the strongest section (max 3).

Strength labels: `strong >= 0.75`, `medium >= 0.50`, `weak < 0.50`.

Examples matching the spec:
```json
{"skill": "React", "confidence": 0.93, "source": "experience",
 "strength": "strong",
 "evidence": ["Built reusable React components with TypeScript."]}
```
```json
{"skill": "SQL", "confidence": 0.35, "source": "skills",
 "strength": "weak", "evidence": ["Python, PyTorch, ..., SQL"]}
```

Evidence entries are real sentences from the resume (trimmed to 160
chars, max 3), so downstream scoring can explain *why* a skill counts.

## 6. API Integration

`POST /api/analyze-resume` now uses `utils.resume_parser` for file
uploads (replacing the old raw-decode hack that corrupted PDFs/DOCX)
and attaches `result["extracted"]` from the intelligence layer. The
integration is wrapped in try/except: ATS scoring always succeeds even
if extraction hits an edge case. **No UI changes were made.**

## 7. Tests

`tests/test_resume_extraction.py` - 37 tests, all passing:

| Scenario | Tests |
|---|---|
| Normal resume | structure keys, profile, contact, evidence fields, experience/education, projects |
| Technical resume | strong ML skills, project-sourced skills, weak skills-only, evidence sentences, job history + certification |
| Fresher resume | empty experience tolerated, education, contact without headline, project-sourced skills, name |
| Resume with tables | DOCX table cells (python-docx), PDF table text (pdfplumber) |
| Multiple jobs | 3 jobs found, titles, dates not cross-contaminated, document order |
| Projects | names/descriptions, technologies, project-sourced skills |
| Noisy PDF | ligatures/soft-hyphens/smart quotes; never crashes, graceful degradation |
| Robustness | empty input, garbage bytes, plain text, capability report |

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_resume_extraction -v
```

Pre-existing scraper tests in `tests/` fail only because `bs4` and the
other scraper dependencies were never installed in this venv - that is
an environment issue unrelated to this layer.

## 8. Performance Notes (hardware constraint compliance)

- Regex NER: microseconds, zero model load, default on this machine.
- pdfplumber: pure-Python page parsing, ~100 ms per resume page.
- No embeddings/transformers are loaded unless explicitly installed and
  `RESUME_NER_BACKEND` allows it.
- Repeated parsing of identical input is avoided downstream by the DB
  cache plan in docs/ARCHITECTURE.md (not yet wired here).

## 9. Known Limitations / Next Steps

- Name detection is heuristic (first clean title-case header line);
  improves automatically once the HF NER backend is enabled.
- Company detection relies on `at`/pipe/dash splits and company-suffix
  regex; unusual names need the model backend.
- Multi-column PDF layouts are extracted linearly by pdfplumber.
- Next phase (per docs/ARCHITECTURE.md): sentence-transformer
  embeddings (all-MiniLM-L6-v2) for resume-job matching, with
  `EmbeddingCache` persistence.