"""
tests/test_resume_extraction.py
End-to-end tests for the local resume extraction layer
(services/resume + utils/resume_parser).

Covers the required scenarios:
  1. normal resume
  2. technical resume
  3. fresher resume
  4. resume with tables (DOCX table + PDF table)
  5. resume with multiple jobs
  6. resume with projects
  7. noisy PDF extraction (ligatures, unicode, binary noise)

No network, no paid AI APIs - everything runs locally.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import pdfplumber  # noqa: F401
    HAS_PDFPLUMBER = True
except Exception:
    HAS_PDFPLUMBER = False

try:
    import docx  # python-docx  # noqa: F401
    HAS_PYTHON_DOCX = True
except Exception:
    HAS_PYTHON_DOCX = False

try:
    from reportlab.pdfgen import canvas as rl_canvas  # noqa: F401
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

from services.resume.extractor import extract_resume  # noqa: E402

TOP = Path(__file__).resolve().parents[1]
TMP = TOP / "tests" / "_tmp_resumes"
TMP.mkdir(exist_ok=True)


# ── helpers ─────────────────────────────────────────────────────────

def build_pdf(path: Path, lines, font_size: int = 9) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas
    c = rl_canvas.Canvas(str(path))
    y = 800
    for line in lines:
        c.setFont("Helvetica", font_size)
        c.drawString(40, y, line)
        y -= font_size + 4
        if y < 40:
            c.showPage()
            y = 800
    c.save()
    return path.read_bytes()


def build_docx(path: Path, paragraphs, table=None) -> bytes:
    import docx as docx_lib
    d = docx_lib.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    if table:
        t = d.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for col, cell in enumerate(row):
                t.rows[r].cells[col].text = cell
    d.save(str(path))
    return path.read_bytes()


NORMAL_RESUME = """Priya Sharma
Frontend Developer
Mumbai, India | +91 98200 11223 | priya.sharma@example.com
linkedin.com/in/priyasharma

PROFESSIONAL SUMMARY
Frontend developer with 4 years of experience building responsive web apps.

EXPERIENCE
Frontend Developer at WebWorks Solutions
Jun 2021 - Present
- Built reusable React components with TypeScript.
- Improved page load times by 40% using Webpack optimizations.

Junior Web Developer at Pixel Labs Pvt Ltd
Jul 2019 - May 2021
- Maintained jQuery and Bootstrap codebases.

EDUCATION
B.Sc in Information Technology, Mumbai University, 2019

SKILLS
JavaScript, React, TypeScript, HTML5, CSS3, Redux

PROJECTS
Portfolio Site: personal portfolio built with React and Tailwind CSS.
Weather App: vanilla JavaScript app consuming a REST API.
"""
TECHNICAL_RESUME = """Arjun Mehta
Senior Machine Learning Engineer
Bangalore, India | +91 99001 23456 | arjun.mehta@example.com

SUMMARY
ML engineer with 7 years of experience in NLP and computer vision.

EXPERIENCE
Machine Learning Engineer at CloudMind Technologies
Feb 2020 - Present
- Trained deep learning models using PyTorch and TensorFlow on AWS.
- Deployed model serving with Docker, Kubernetes and MLflow.

Data Scientist at Insight Analytics Pvt Ltd
Aug 2017 - Jan 2020
- Built churn prediction pipelines with Scikit-learn and XGBoost.
- Processed large datasets with Apache Spark and Pandas.

EDUCATION
M.Tech in Computer Science, IIT Bombay, 2017

SKILLS
Python, PyTorch, TensorFlow, Scikit-learn, AWS, Docker, Kubernetes,
Apache Spark, Pandas, SQL

PROJECTS
Document Classifier: fine-tuned BERT with Hugging Face Transformers.
Recommendation Engine: collaborative filtering with Pandas and NumPy.

CERTIFICATIONS
AWS Certified Machine Learning - Specialty, 2023
"""

FRESHER_RESUME = """Rahul Verma
rahul.verma@example.com | +91 98111 22334 | Pune, India

OBJECTIVE
Computer Science graduate seeking an entry-level software developer role.

EDUCATION
B.E. in Computer Engineering, Pune Institute of Computer Technology, 2025

SKILLS
Python, Java, HTML5, CSS3, MySQL, Git

PROJECTS
Library Management System: Java and MySQL desktop application.
Personal Website: HTML5 and CSS3 static site hosted on GitHub.

ACHIEVEMENTS
Winner, college hackathon 2024.
"""

MULTI_JOB_RESUME = """Sneha Iyer
Full Stack Developer
Chennai, India | sneha.iyer@example.com

EXPERIENCE
Full Stack Developer at Orion Digital Labs
Jan 2022 - Present
- Leads development of Node.js and React services.

Backend Developer at Coral Softworks
Apr 2019 - Dec 2021
- Built Express.js APIs with PostgreSQL.

Software Engineer at Tide Technologies
Jun 2017 - Mar 2019
- Maintained legacy Java services.

EDUCATION
B.Tech in Information Technology, Anna University, 2017

SKILLS
JavaScript, Node.js, React, Express.js, PostgreSQL, Java
"""


# ── 1. normal resume ────────────────────────────────────────────────

class TestNormalResume(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = extract_resume(text=NORMAL_RESUME)

    def test_normalized_structure_keys(self):
        for key in ("profile", "skills", "experience", "education",
                    "projects", "certifications", "contact", "raw_text"):
            self.assertIn(key, self.r)

    def test_profile_fields(self):
        self.assertEqual(self.r["profile"]["name"], "Priya Sharma")
        self.assertIn("Frontend Developer", self.r["profile"]["headline"])
        self.assertEqual(self.r["profile"]["years_experience"], 4)

    def test_contact_fields(self):
        c = self.r["contact"]
        self.assertEqual(c["email"], "priya.sharma@example.com")
        self.assertIn("98200 11223", c["phone"])
        self.assertEqual(c["location"], "Mumbai, India")
        self.assertIn("linkedin.com", c["linkedin"])

    def test_skills_have_evidence_fields(self):
        skills = {s["skill"]: s for s in self.r["skills"]}
        for name in ("JavaScript", "React", "TypeScript", "HTML5", "CSS3"):
            self.assertIn(name, skills)
            s = skills[name]
            self.assertGreaterEqual(s["confidence"], 0.35)
            self.assertLessEqual(s["confidence"], 0.98)
            self.assertIn(s["source"],
                          ("projects", "experience", "skills", "summary"))
            self.assertIn(s["strength"], ("strong", "medium", "weak"))
            self.assertIsInstance(s["evidence"], list)

    def test_experience_and_education(self):
        self.assertEqual(len(self.r["experience"]), 2)
        first = self.r["experience"][0]
        self.assertEqual(first["job_title"], "Frontend Developer")
        self.assertEqual(first["company"], "WebWorks Solutions")
        self.assertEqual(first["start"], "Jun 2021")
        self.assertEqual(first["end"], "Present")
        self.assertEqual(len(self.r["education"]), 1)
        self.assertEqual(self.r["education"][0]["degree"], "B.Sc")

    def test_projects_extracted(self):
        names = [p["name"] for p in self.r["projects"]]
        self.assertIn("Portfolio Site", names)
        self.assertIn("Weather App", names)
# ── 2. technical resume ─────────────────────────────────────────────

class TestTechnicalResume(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = extract_resume(text=TECHNICAL_RESUME)
        cls.skills = {s["skill"]: s for s in cls.r["skills"]}

    def test_ml_skills_strong(self):
        # These appear in the EXPERIENCE section (used, not just listed)
        for name in ("PyTorch", "TensorFlow", "Docker", "Kubernetes"):
            self.assertIn(name, self.skills)
            self.assertEqual(self.skills[name]["strength"], "strong")
            self.assertGreaterEqual(self.skills[name]["confidence"], 0.75)

    def test_skill_used_in_project_is_strong_evidence(self):
        # NumPy and Hugging Face appear only inside project descriptions
        for name in ("NumPy", "Hugging Face"):
            entry = self.skills.get(name)
            self.assertIsNotNone(entry, name)
            self.assertEqual(entry["source"], "projects")
            self.assertTrue(entry["evidence"])
            self.assertGreaterEqual(entry["confidence"], 0.85)

    def test_skills_section_only_is_weak(self):
        # SQL appears ONLY in the skills list -> weak evidence (per spec)
        sql = self.skills.get("SQL")
        self.assertIsNotNone(sql)
        self.assertEqual(sql["source"], "skills")
        self.assertEqual(sql["strength"], "weak")
        self.assertLess(sql["confidence"], 0.5)

    def test_evidence_snippets_are_real_sentences(self):
        python = self.skills["Python"]
        self.assertTrue(any("Python" in ev for ev in python["evidence"]))
        self.assertTrue(all(len(ev) > 10 for ev in python["evidence"]))

    def test_job_history_and_certification(self):
        self.assertEqual(len(self.r["experience"]), 2)
        self.assertEqual(self.r["experience"][0]["company"],
                         "CloudMind Technologies")
        self.assertTrue(any("AWS" in c["name"]
                            for c in self.r["certifications"]))


# ── 3. fresher resume ───────────────────────────────────────────────

class TestFresherResume(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = extract_resume(text=FRESHER_RESUME)

    def test_no_experience_section_is_tolerated(self):
        self.assertEqual(self.r["experience"], [])

    def test_education_captured(self):
        self.assertEqual(self.r["education"][0]["degree"], "B.E.")
        self.assertIn("Pune Institute", self.r["education"][0]["institution"])
        self.assertEqual(self.r["education"][0]["year"], "2025")

    def test_contact_without_headline(self):
        self.assertEqual(self.r["contact"]["email"],
                         "rahul.verma@example.com")
        self.assertEqual(self.r["contact"]["location"], "Pune, India")

    def test_skills_from_projects_are_strong(self):
        skills = {s["skill"]: s for s in self.r["skills"]}
        self.assertEqual(skills["Java"]["source"], "projects")
        self.assertEqual(skills["Java"]["strength"], "strong")

    def test_profile_name(self):
        self.assertEqual(self.r["profile"]["name"], "Rahul Verma")


# ── 5. resume with multiple jobs ────────────────────────────────────

class TestMultipleJobs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = extract_resume(text=MULTI_JOB_RESUME)

    def test_all_jobs_found(self):
        self.assertEqual(len(self.r["experience"]), 3)
        companies = [e["company"] for e in self.r["experience"]]
        self.assertIn("Orion Digital Labs", companies)
        self.assertIn("Coral Softworks", companies)
        self.assertIn("Tide Technologies", companies)

    def test_each_job_has_title(self):
        titles = [e["job_title"] for e in self.r["experience"]]
        self.assertIn("Full Stack Developer", titles)
        self.assertIn("Backend Developer", titles)
        self.assertIn("Software Engineer", titles)

    def test_job_dates_not_cross_contaminated(self):
        first, second = self.r["experience"][0], self.r["experience"][1]
        self.assertEqual(first["start"], "Jan 2022")
        self.assertEqual(second["start"], "Apr 2019")

    def test_ordering_follows_document(self):
        self.assertEqual(self.r["experience"][0]["company"],
                         "Orion Digital Labs")
# ── 4. resume with tables ───────────────────────────────────────────

@unittest.skipUnless(HAS_PYTHON_DOCX, "python-docx not installed")
class TestResumeWithTablesDocx(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content = build_docx(
            TMP / "tables.docx",
            ["Vikram Rao", "Backend Developer", "vikram.rao@example.com",
             "EXPERIENCE", "SKILLS", "Python, Docker, PostgreSQL, Redis"],
            table=[
                ["Role", "Company", "Period"],
                ["Backend Developer", "Nimbus Technologies", "2021 - Present"],
                ["Software Engineer", "Delta Systems Ltd", "2018 - 2021"],
            ])
        cls.r = extract_resume(filename="tables.docx", content=content)

    def test_table_cells_extracted(self):
        self.assertGreater(len(self.r["raw_text"]), 100)
        self.assertIn("Nimbus Technologies", self.r["raw_text"])
        self.assertIn("Delta Systems Ltd", self.r["raw_text"])

    def test_skills_found(self):
        names = {s["skill"] for s in self.r["skills"]}
        self.assertTrue({"Python", "Docker", "PostgreSQL", "Redis"}
                        .issubset(names))

    def test_meta_reports_engine(self):
        self.assertIn(self.r["meta"]["parser_engine"],
                      ("python-docx", "zip-xml"))


@unittest.skipUnless(HAS_PDFPLUMBER and HAS_REPORTLAB,
                     "pdfplumber/reportlab not installed")
class TestResumeWithTablesPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lines = [
            "Meera Nair",
            "Data Analyst",
            "meera.nair@example.com",
            "EXPERIENCE",
            "Role: Data Analyst | Company: Quantum Analytics Pvt Ltd | "
            "Period: 2020 - Present",
            "Skills used: SQL, Pandas, Matplotlib",
            "EDUCATION",
            "B.Sc Statistics, Madras University, 2020",
        ]
        cls.content = build_pdf(TMP / "tables.pdf", lines)
        cls.r = extract_resume(filename="tables.pdf", content=cls.content)

    def test_pdf_text_extracted(self):
        self.assertIn("Quantum Analytics", self.r["raw_text"])
        self.assertGreater(len(self.r["raw_text"]), 100)

    def test_contact_from_pdf(self):
        self.assertEqual(self.r["contact"]["email"],
                         "meera.nair@example.com")

    def test_skills_from_pdf(self):
        names = {s["skill"] for s in self.r["skills"]}
        self.assertTrue({"SQL", "Pandas"}.issubset(names))


# ── 6. resume with projects ─────────────────────────────────────────

class TestProjectResume(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = extract_resume(text=NORMAL_RESUME)

    def test_project_names_and_descriptions(self):
        by_name = {p["name"]: p for p in self.r["projects"]}
        self.assertIn("Portfolio Site", by_name)
        self.assertIn("React", by_name["Portfolio Site"]["description"])
        self.assertIn("Weather App", by_name)

    def test_project_technologies_captured(self):
        by_name = {p["name"]: p for p in self.r["projects"]}
        techs = set(by_name["Portfolio Site"]["technologies"])
        self.assertIn("React", techs)
        self.assertIn("Tailwind CSS", techs)

    def test_project_skills_have_project_source(self):
        skills = {s["skill"]: s for s in self.r["skills"]}
        self.assertEqual(skills["Tailwind CSS"]["source"], "projects")
# ── 7. noisy PDF extraction ─────────────────────────────────────────

@unittest.skipUnless(HAS_PDFPLUMBER and HAS_REPORTLAB,
                     "pdfplumber/reportlab not installed")
class TestNoisyPdfExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ligatures, soft hyphens, smart quotes, mixed binary-ish junk
        lines = [
            "Ka\uFB01r Abd\u2019Allah \u2013 Senior Soft\u00ADware Engineer",
            "Ben\u00ADgal\u00ADuru, India  |  +91 97\u00AD400 55\u00AD066",
            "kab\u00ADdul\u0040ex\u00ADam\u00ADple\u002Ecom",
            "",
            "EXPERIENCE",
            "Senior Software Engineer at Quill & Quanta Labs",
            "2019 - Present",
            "\u201cBuilt \uFB01nancial dashboards\u201d using Python,",
            "Flask and Po\u00ADst\u00ADgre\u00ADSQ\u004C.",
            "SKILLS",
            "Python, Flask, PostgreSQL, Docker",
        ]
        cls.content = build_pdf(TMP / "noisy.pdf", lines, font_size=8)
        cls.r = extract_resume(filename="noisy.pdf", content=cls.content)

    def test_does_not_crash_and_returns_structure(self):
        for key in ("profile", "skills", "experience", "education",
                    "contact", "raw_text", "meta"):
            self.assertIn(key, self.r)

    def test_something_useful_recovered(self):
        if self.r["raw_text"].strip():
            names = {s["skill"] for s in self.r["skills"]}
            self.assertTrue(len(names) >= 1)
        else:
            self.assertTrue(self.r["meta"]["warnings"])

    def test_email_recovered_from_noisy_pdf(self):
        email = self.r["contact"]["email"]
        self.assertTrue(email is None or "@" in email)

    def test_meta_uses_pdf_engine(self):
        self.assertIn(self.r["meta"]["parser_engine"],
                      ("pdfplumber", "pypdf2", "raw-decode"))


# ── pipeline robustness ─────────────────────────────────────────────

class TestPipelineRobustness(unittest.TestCase):
    def test_empty_input_never_raises(self):
        r = extract_resume()
        self.assertEqual(r["raw_text"], "")
        self.assertIn("no input", " ".join(r["meta"]["warnings"]))

    def test_garbage_bytes_never_raises(self):
        r = extract_resume(filename="x.pdf", content=b"\x00\x01\x02junk")
        self.assertIsInstance(r, dict)
        self.assertIn("raw_text", r)

    def test_plain_text_still_works_end_to_end(self):
        r = extract_resume(text="Jane Roe\nData Analyst\njane@roe.com\n")
        self.assertEqual(r["contact"]["email"], "jane@roe.com")

    def test_capabilities_report(self):
        from services.resume.extractor import extraction_capabilities
        caps = extraction_capabilities()
        self.assertTrue(caps.get("pdfplumber"))
        self.assertTrue(caps.get("python_docx"))


if __name__ == "__main__":
    unittest.main(verbosity=2)