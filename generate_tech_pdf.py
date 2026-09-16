"""
JobAgent - Complete Site Functions, Languages & ML Models Guide (PDF Generator)

Generates a professional PDF explaining every function in the JobAgent site,
the programming languages used to build it, and the ML/AI models powering it.
"""
import os
from datetime import date

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen.canvas import Canvas

OUTPUT_PDF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "JobAgent_Complete_Functions_Guide.pdf")


def esc(s: str) -> str:
    """Escape XML special characters for ReportLab paragraphs."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


# ─────────────────────────────────────────────────────────────────────
#  STYLES
# ─────────────────────────────────────────────────────────────────────
base = getSampleStyleSheet()

ST_TITLE = ParagraphStyle('TitleX', parent=base['Title'], fontSize=30,
                          leading=36, alignment=TA_CENTER,
                          textColor=colors.HexColor("#1a1d2e"),
                          fontName='Helvetica-Bold')
ST_SUB = ParagraphStyle('SubX', parent=base['Normal'], fontSize=14,
                        leading=20, alignment=TA_CENTER,
                        textColor=colors.HexColor("#4b5563"))
ST_H1 = ParagraphStyle('H1X', parent=base['Heading1'], fontSize=20,
                       leading=26, spaceAfter=8, spaceBefore=4,
                       textColor=colors.HexColor("#0e7490"),
                       fontName='Helvetica-Bold')
ST_H2 = ParagraphStyle('H2X', parent=base['Heading2'], fontSize=15,
                       leading=20, spaceBefore=10, spaceAfter=5,
                       textColor=colors.HexColor("#134e4a"),
                       fontName='Helvetica-Bold')
ST_H3 = ParagraphStyle('H3X', parent=base['Heading3'], fontSize=12,
                       leading=16, spaceBefore=6, spaceAfter=3,
                       textColor=colors.HexColor("#1f2937"),
                       fontName='Helvetica-Bold')
ST_BODY = ParagraphStyle('BodyX', parent=base['BodyText'], fontSize=10,
                         leading=15, spaceAfter=6, alignment=TA_LEFT)
ST_BODY_IND = ParagraphStyle('BodyInd', parent=ST_BODY, leftIndent=14)
ST_BULLET = ParagraphStyle('BulletX', parent=ST_BODY, leftIndent=14,
                           bulletIndent=4, spaceAfter=3)
ST_CAPTION = ParagraphStyle('CaptionX', parent=base['Normal'], fontSize=8.5,
                            leading=11, textColor=colors.HexColor("#6b7280"))
ST_CODE = ParagraphStyle('CodeX', parent=base['Code'], fontSize=8.5,
                         leading=12, textColor=colors.HexColor("#0f172a"),
                         backColor=colors.HexColor("#f1f5f9"),
                         borderPadding=6, borderColor=colors.HexColor("#cbd5e1"),
                         borderWidth=0.5, spaceAfter=8)

# Colours used in function tables
C_LANG = colors.HexColor("#0e7490")     # teal
C_MODEL = colors.HexColor("#7c3aed")    # violet
C_PATH = colors.HexColor("#166534")     # green
C_BG = colors.HexColor("#f8fafc")
def header_footer(canvas: Canvas, doc):
    """Draw page number + footer band on every page except the cover."""
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#0e7490"))
    canvas.setLineWidth(0.6)
    canvas.line(20 * mm, 13 * mm, A4[0] - 20 * mm, 13 * mm)
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(20 * mm, 8.5 * mm,
                      "JobAgent - Languages & ML Models in Every Function  |  "
                      "Generated %s" % date.today().strftime("%d %b %Y"))
    canvas.drawRightString(A4[0] - 20 * mm, 8.5 * mm, "Page %d" % doc.page)
    canvas.restoreState()


def fn_block(story, name, lang, model, path, detail):
    """Render a structured 'function card' block."""
    rows = []
    if path:
        rows.append([Paragraph("<b>Route / File</b>",
                               ParagraphStyle('r1', parent=ST_CAPTION)),
                     Paragraph(esc(path), ParagraphStyle(
                         'r2', parent=ST_BODY, fontSize=9, leading=13,
                         textColor=C_PATH, fontName='Courier'))])
    rows.append([Paragraph("<b>Language / Tech</b>",
                           ParagraphStyle('r1', parent=ST_CAPTION)),
                 Paragraph(esc(lang), ParagraphStyle(
                     'r2', parent=ST_BODY, fontSize=9, leading=13,
                     textColor=C_LANG, fontName='Helvetica-Bold'))])
    rows.append([Paragraph("<b>ML / AI Model</b>",
                           ParagraphStyle('r1', parent=ST_CAPTION)),
                 Paragraph(esc(model), ParagraphStyle(
                     'r2', parent=ST_BODY, fontSize=9, leading=13,
                     textColor=C_MODEL, fontName='Helvetica-Bold'))])

    head = Table(
        [[Paragraph(esc(name), ParagraphStyle(
            'fnName', parent=ST_H3, textColor=colors.white,
            spaceBefore=0, spaceAfter=0)),
          ""]], colWidths=[128 * mm, 50 * mm])
    head.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_LANG),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    meta = Table(rows, colWidths=[30 * mm, 148 * mm])
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_BG),
        ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ('INNERGRID', (0, 0), (-1, -1), 0.2, colors.HexColor("#e2e8f0")),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))

    body = Paragraph(esc(detail), ST_BODY)

    block = [head, Spacer(1, 2), meta, Spacer(1, 6), body]
    story.append(KeepTogether(block))
    story.append(Spacer(1, 12))


def bullet(story, items):
    for it in items:
        story.append(Paragraph(it, ST_BULLET, bulletText="\u2022"))


def section_title(story, text):
    story.append(Paragraph(esc(text), ST_H1))
    story.append(HRFlowable(width="100%", thickness=1,
                            color=colors.HexColor("#0e7490"),
                            spaceAfter=8))
# ─────────────────────────────────────────────────────────────────────
#  COVER PAGE  +  TABLE OF CONTENTS
# ─────────────────────────────────────────────────────────────────────
def cover_and_toc(story):
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("JobAgent", ST_TITLE))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Smart Career Assistant", ST_SUB))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "Complete Technical Guide: The Languages and ML Models Behind "
        "Every Function in the Site", ST_SUB))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Generated %s &nbsp;|&nbsp; Prepared from the project source code "
        "(app.py, static/js, utils, models, scrapers, n8n workflows)"
        % date.today().strftime("%d %b %Y"), ST_CAPTION))
    story.append(PageBreak())

    section_title(story, "Table of Contents")
    toc = [
        "1. Project Overview &amp; Architecture",
        "2. Technology &amp; Programming Languages",
        "3. ML &amp; AI Models Used",
        "4. Frontend Functions (JavaScript / HTML / CSS)",
        "5. Backend Functions (Python / Flask)",
        "6. Core AI/ML Analysis Engines in Detail",
        "7. Authentication &amp; Security Functions",
        "8. Job Scraping Subsystem",
        "9. Community Chat &amp; Dashboard Functions",
        "10. Database Layer (SQLAlchemy Models)",
        "11. n8n AI Orchestration Workflows",
        "12. Hardware-Constrained Architecture Plan &amp; Proposed Local AI Stack",
        "13. Appendix - Sibling Projects in the Workspace",
    ]
    for t in toc:
        story.append(Paragraph("&bull;  " + t, ST_BODY_IND))
    story.append(PageBreak())


# ─────────────────────────────────────────────────────────────────────
#  SECTION 1 - OVERVIEW
# ─────────────────────────────────────────────────────────────────────
def s1_overview(story):
    section_title(story, "1. Project Overview & Architecture")
    story.append(Paragraph(
        "JobAgent is a full-stack web application that works as an "
        "AI-assisted career assistant. A user can search any job role and "
        "instantly receive a detailed career guide, find related job "
        "titles, analyze their resume with an ATS (Applicant Tracking "
        "System) scored report, discover skill gaps with a learning "
        "roadmap, practice interview questions, view market career "
        "insights, save everything to a personal dashboard, and join a "
        "moderated community chat.", ST_BODY))
    story.append(Paragraph(
        "The project also contains a command-line job scraping agent "
        "(main.py + scrapers/) that pulls live job listings from "
        "Naukri, RemoteOK and Wellfound into a CSV file, plus five n8n "
        "automation workflows that run the same role guides through an "
        "AI Large Language Model (gemini-pro) via webhooks.", ST_BODY))
    story.append(Paragraph("High-level layered architecture:", ST_BODY))
    bullet(story, [
        "<b>Client layer:</b> HTML5 + CSS3 SPAs served by Jinja2 "
        "templates (index.html, login.html, etc.), JavaScript (vanilla, "
        "no framework) via static/js/app.js and static/js/auth.js, "
        "Font Awesome icons and the Inter web font.",
        "<b>Server layer:</b> Python 3.9 + Flask 3.0 (REST JSON APIs "
        "under /api/*), Flask-Login sessions, Flask-SQLAlchemy.",
        "<b>AI/ML layer:</b> Google Gemini (gemini-pro) as the primary "
        "LLM; Hugging Face inference (facebook/bart-large-mnli zero-shot "
        "classifier) as a fallback; an internal, rule-based ATS scoring "
        "engine; regex/NLP-lite parsing utilities.",
        "<b>Data layer:</b> SQLite by default (jobagent.db), "
        "PostgreSQL-ready via DATABASE_URL, 13+ mapped models.",
        "<b>Automation layer:</b> n8n workflows that expose AI webhooks "
        "for resume analysis, interview prep, career insights, job "
        "recommendations and feedback processing.",
    ])
    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 2 - TECHNOLOGY & LANGUAGES
# ─────────────────────────────────────────────────────────────────────
def s2_tech(story):
    section_title(story, "2. Technology & Programming Languages")
    story.append(Paragraph(
        "These are the programming languages and core technologies used "
        "across the whole site, together with the exact job they perform "
        "inside JobAgent.", ST_BODY))

    data = [
        ["Language / Tech", "Version", "Where It Lives", "What It Does Here"],
        ["Python", "3.9+", "app.py, main.py, utils/, models/, scrapers/",
         "All backend logic: web server, REST APIs, ATS scoring engine, "
         "auth, data modelling, scrapers and API integrations."],
        ["JavaScript (vanilla ES6+)", "-", "static/js/app.js, auth.js",
         "All client-side interactivity: SPA page switching, fetch() API "
         "calls, rendering guides/scores/charts, chat polling, auth "
         "forms. No framework used on purpose."],
        ["HTML5", "-", "templates/*.html",
         "Page structure for the SPA (index.html) and auth pages "
         "(login, signup, forgot/reset password). Rendered by Jinja2."],
        ["CSS3", "-", "static/css/style.css, static/css/auth.css",
         "Premium dark SaaS theme, responsive layout, grids, cards, "
         "progress bars, toasts and chat UI styling."],
        ["Flask (Python micro-framework)", "3.0.0", "app.py",
         "Web framework routing every URL; JSON API responses, session "
         "handling, static file serving, SPA fallback routing."],
        ["SQL / SQLAlchemy ORM", "2.0.23", "models/*.py",
         "Relational persistence for users, jobs, chat, audit logs, "
         "tokens, dashboards. SQLite in dev, PostgreSQL in production."],
        ["Jinja2 (templating)", "bundled with Flask", "templates/",
         "Server-side template rendering for the HTML pages."],
        ["Bash / Batch", "-", "start_server.bat (job-platform)",
         "Startup scripts that launch the servers on Windows."],
        ["JSON", "-", "config files, n8n/workflows/*.json",
         "Configuration and the n8n AI workflow definitions."],
    ]
    t = Table(data, colWidths=[38 * mm, 20 * mm, 52 * mm, 68 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_LANG),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Key Python libraries in requirements.txt: pytest (tests), "
        "beautifulsoup4 + lxml + Playwright + Firecrawl (scraping), "
        "pandas + numpy (data), requests + httpx + aiohttp (HTTP APIs), "
        "google-generativeai + openai + huggingface-hub (AI/ML), "
        "python-docx + PyPDF2 + pdfplumber (resume documents), passlib[bcrypt] "
        "+ python-jose + email-validator (security), tenacity (retries) "
        "and cachetools (caching).", ST_BODY))
    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 3 - ML & AI MODELS
# ─────────────────────────────────────────────────────────────────────
def s3_models(story):
    section_title(story, "3. ML & AI Models Used")

    story.append(Paragraph(
        "JobAgent combines three kinds of intelligence. The first is a "
        "commercial LLM accessed over the network (Google Gemini). The "
        "second is a fine-tuned open-source transformer model served by "
        "the Hugging Face inference API. The third is an in-house, "
        "transparent \"expert-system\" engine written in pure Python "
        "(weighted scoring + regular expressions) that mimics the "
        "behaviour of a trained ML model and works fully offline.", ST_BODY))

    model_rows = [
        ["Model / AI", "Provider / Runtime", "Tasks It Powers", "Type"],
        ["gemini-pro", "Google AI (generativelanguage API, 60 req/min "
         "free tier; also n8n Google AI node)",
         "Resume analysis, interview question generation, career "
         "insights, role guides", "Transformer LLM (decoder-only)"],
        ["facebook/bart-large-mnli", "Hugging Face Inference API "
         "hd-inference node (1000 req/month free tier)",
         "Zero-shot classification of resume sections (skills, "
         "experience, education...)", "Transformer encoder-decoder, "
         "zero-shot NLI classifier"],
        ["GPT-4 (optional)", "OpenAI API (openai 1.6.1 client)",
         "Advanced reasoning / complex analysis enhancement hook",
         "Transformer LLM"],
        ["ANS/ATS Scoring Engine", "In-process Python, app.py "
         "analyze_resume_text()",
         "Weighted multi-factor resume score, readability score, "
         "keyword matching", "Rule-based expert system (heuristic ML)"],
        ["Skill Extractor", "In-process Python, _extract_skills_from_text()",
         "Detects 150+ known skills from free text", "Dictionary / "
         "regex pattern matcher"],
        ["Query Parser", "Python, utils/query_parser.py",
         "Turns natural language like \"product manager role in "
         "bangalore\" into structured job title + location + keywords",
         "Regex-based NLP-lite parser"],
    ]
    t = Table(model_rows, colWidths=[30 * mm, 45 * mm, 63 * mm, 40 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_MODEL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    story.append(Paragraph("3.1 Google Gemini (gemini-pro)", ST_H2))
    story.append(Paragraph(
        "This is the primary Large Language Model. The code in "
        "utils/api_integrations.py configures the official SDK with "
        "genai.configure(api_key=...) and instantiates "
        "genai.GenerativeModel('gemini-pro'). For resume analysis it is "
        "prompted to output a detailed JSON report (ATS score, keyword "
        "score, strengths, weaknesses, missing keywords and suggestions). "
        "For interviews it generates 5 realistic questions per role with "
        "answers, difficulty and timing. The same model is reused inside "
        "the n8n resume-analysis and interview-prep workflows through the "
        "Google AI node, so the LLM capability works both from Python and "
        "from the automation layer.", ST_BODY))

    story.append(Paragraph("3.2 Hugging Face - bart-large-mnli", ST_H2))
    story.append(Paragraph(
        "Used as a zero-shot text classifier with multi-label support. "
        "The resume text is sent to "
        "https://api-inference.huggingface.co/models/facebook/bart-large-mnli "
        "with candidate labels such as \"has technical skills\", \"has "
        "work experience\", \"has education\", \"needs improvement\". "
        "This provides an independent ML opinion about the presence of "
        "each resume section, acting as a fallback path when the Gemini "
        "key is not configured.", ST_BODY))

    story.append(Paragraph("3.3 In-process Heuristic Engines", ST_H2))
    story.append(Paragraph(
        "The most heavily used \"ML\" in the live site is the rule-based "
        "analysis engine. analyze_resume_text() computes a 100-point ATS "
        "score from ten weighted components (section detection 10%, "
        "keywords 30%, experience 20%, contact 5%, skills 15%, education "
        "5%, projects 10%, grammar 10% scaled, length 5%, ATS "
        "compatibility 5%). Every component is a transparent function of "
        "regular-expression features, so the same input always produces "
        "the same score - ideal for a scoring product. The skill "
        "extractor and the natural-language query parser follow the same "
        "philosophy with heuristics instead of neural weights.", ST_BODY))
    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 4 - FRONTEND FUNCTIONS
# ─────────────────────────────────────────────────────────────────────
def s4_frontend(story):
    section_title(story, "4. Frontend Functions (JavaScript / HTML / CSS)")
    story.append(Paragraph(
        "All frontend logic lives in static/js/app.js (the career "
        "assistant) and static/js/auth.js (login/signup). The UI is a "
        "single HTML page (index.html) divided into sections with class "
        "toggling - no frontend framework is used. Every function talks "
        "to the Flask API through the fetch() wrapper below.", ST_BODY))

    story.append(Paragraph("4.1 Core UI plumbing", ST_H2))

    fn_block(story,
        "showPage(pageName)",
        "JavaScript (vanilla DOM API)",
        "None - plain DOM manipulation",
        "static/js/app.js",
        "Implements client-side single-page-app navigation. It removes the "
        "active class from all .page sections and .nav-link items, adds it "
        "to the requested section, closes the mobile menu, scrolls to the "
        "top, and lazily loads dashboard or chat content when those pages "
        "are opened.")

    fn_block(story,
        "toggleNav()",
        "JavaScript",
        "None - CSS class toggle",
        "static/js/app.js",
        "Opens and closes the responsive hamburger menu on small screens by "
        "toggling the open class on the navigation links container.")

    fn_block(story,
        "showToast(message, type)",
        "JavaScript",
        "None - pure DOM/CSS animation",
        "static/js/app.js",
        "Creates a temporary toast notification element, appends it to the "
        "body, auto-removes it after 3 seconds. Supports success and error "
        "variants using Font Awesome icons plus CSS animation.")

    fn_block(story,
        "apiCall(url, options)",
        "JavaScript (async/await + fetch)",
        "None - HTTP client wrapper",
        "static/js/app.js",
        "A promise-based wrapper around fetch() used by every other "
        "frontend function. It sends JSON headers, throws a descriptive "
        "error when the response is not OK, and parses JSON responses. "
        "This single function is the gateway between the browser and all "
        "the Python/Flask endpoints.")

    story.append(Paragraph("4.2 Search / Role-guide workflow", ST_H2))

    fn_block(story,
        "heroSearch() and quickSearch(role)",
        "JavaScript",
        "None - input plumbing",
        "static/js/app.js",
        "Captures the text typed in the hero search box, copies it into the "
        "main search input, navigates to the search page and triggers "
        "performSearch(). quickSearch fills the hero box first so the "
        "popular-role chips work with one click.")

    fn_block(story,
        "performSearch()",
        "JavaScript + calls Python APIs",
        "None directly - the Python side uses dictionary matching and "
        "AI-assisted role guides",
        "POST /api/expand-roles and POST /api/search",
        "The main search workflow. It shows a loading spinner, asks the "
        "backend to expand the query into related role titles "
        "(/api/expand-roles), renders those as clickable chips, then asks "
        "for the full role guide pack (/api/search) which contains the "
        "primary guide, related guides (top 5) and the platform search "
        "URLs.")

    fn_block(story,
        "showRoleExpansion(roles) and exploreRole(role)",
        "JavaScript",
        "None - display + re-trigger search",
        "static/js/app.js",
        "Renders the expanded role list as tag chips with the total role "
        "count. Clicking a chip calls exploreRole, which replaces the "
        "search input with that role and runs performSearch again, giving "
        "a drill-down experience without a full page reload.")

    fn_block(story,
        "renderGuides(data) and renderPlatformButtons(urls, query)",
        "JavaScript",
        "None - templating/rendering logic",
        "static/js/app.js",
        "Renders the results header (role title and subtitle), the guide "
        "cards grid showing overview, responsibilities, required and "
        "preferred skills, salary range, interview topics, key "
        "industries, and buttons that deep-link directly to LinkedIn, "
        "Indeed, Glassdoor and 14 other job boards with the role "
        "pre-filled.")
    story.append(Paragraph("4.3 Resume analysis UI", ST_H2))

    fn_block(story,
        "analyzeResume()",
        "JavaScript + multipart/form-data POST",
        "Uses the backend ATS engine (heuristic) plus optional file "
        "parsing; AI enhancement available via Gemini path",
        "POST /api/analyze-resume",
        "Builds a FormData object with the pasted resume text, optional "
        "target role and an optional uploaded .txt/.pdf/.docx file, then "
        "sends it to the Flask endpoint. The response contains the full "
        "ATS report which the UI then renders with scores, strengths, "
        "weaknesses and suggestions.")

    fn_block(story,
        "renderResumeAnalysis(data)",
        "JavaScript",
        "Display of the heuristic ATS scoring engine output; skills are "
        "detected by the regex skill extractor",
        "static/js/app.js",
        "Renders the ATS score badge, the component breakdown bars, "
        "detected sections, matched and missing keywords, action verbs "
        "found, readability level, strengths, weaknesses and "
        "improvement suggestions with priority and expected impact.")

    story.append(Paragraph("4.4 Interview preparation UI", ST_H2))

    fn_block(story,
        "loadInterviewQuestions()",
        "JavaScript",
        "Role-specific question bank from the Python dictionary "
        "INTERVIEW_QUESTIONS_DB; AI generation available through Gemini",
        "POST /api/interview-prep",
        "Reads the selected role and fetches the question pack. The "
        "backend returns grouped questions (technical, behavioral, "
        "coding) with answer tips for each.")

    fn_block(story,
        "renderInterviewQuestions(data)",
        "JavaScript",
        "None - rendering only",
        "static/js/app.js",
        "Groups questions by category with icons and counts, and renders "
        "expandable question cards that reveal answer tips when clicked.")

    story.append(Paragraph("4.5 Career insights UI", ST_H2))

    fn_block(story,
        "loadCareerInsights() and renderCareerInsights(data)",
        "JavaScript",
        "Data comes from the curated CAREER_INSIGHTS_DB dictionary; "
        "salary enhancement can use live APIs via utils/api_integrations.py",
        "POST /api/career-insights",
        "Requests salary, demand, growth and outlook data for a role and "
        "renders a grid of insight cards: average USD salary, INR salary "
        "range, demand level, growth rate, hiring trend, future outlook, "
        "top companies, key industries and entry/senior salary levels.")

    story.append(Paragraph("4.6 Dashboard UI", ST_H2))

    fn_block(story,
        "loadDashboard() and renderDashboard(data)",
        "JavaScript",
        "None - statistics aggregation by Flask from in-memory session "
        "store",
        "GET /api/dashboard",
        "Builds four stat cards (saved guides, resumes analyzed, skills "
        "tracked, searches) and lists saved role guides, ATS score "
        "history with colour-coded badges, recent search history and "
        "tracked skill progress bars.")

    story.append(Paragraph("4.7 Auth UI (auth.js)", ST_H2))

    fn_block(story,
        "handleSignup / handleLogin",
        "JavaScript",
        "None - client-side validation only; security handled in Python "
        "(bcrypt hashing, email-validator)",
        "POST /api/auth/signup and /api/auth/login",
        "Runs client-side validation (matching passwords, password "
        "strength meter, email format), shows inline field errors, "
        "disables the submit button while waiting and posts the "
        "credentials as JSON. On success it stores the user object and "
        "redirects to the dashboard.")

    fn_block(story,
        "handleForgotPassword / handleResetPassword",
        "JavaScript",
        "None - token flow implemented in Python",
        "POST /api/auth/forgot-password and /api/auth/reset-password",
        "Handles the two-step password recovery UX: request a reset link "
        "by email, then submit the new password together with the reset "
        "token from the URL. Shows success/error toasts in both steps.")

    fn_block(story,
        "handleLogout()",
        "JavaScript",
        "None - session invalidation in Python",
        "POST /api/auth/logout",
        "Calls the logout endpoint, clears the local user state and "
        "redirects to the home page.")

    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 5 - BACKEND FUNCTIONS (FLASK)
# ─────────────────────────────────────────────────────────────────────
def s5_backend_auth_pages(story):
    section_title(story, "5. Backend Functions (Python / Flask)")
    story.append(Paragraph(
        "Every backend function below is a Python route handler in "
        "app.py. They receive JSON or file data, execute the business "
        "logic, and return JSON to the JavaScript frontend. Type hints "
        "(Dict, List, Any, Optional) are used throughout, and seven of "
        "them are decorated with @login_required so they only work for "
        "authenticated users.", ST_BODY))

    story.append(Paragraph("5.1 Page routes (server-rendered HTML)", ST_H2))

    fn_block(story,
        "login_page(), signup_page(), forgot_password_page(), "
        "reset_password_page(token)",
        "Python - Flask render_template",
        "None - template rendering",
        "GET /login, /signup, /forgot-password, /reset-password/<token>",
        "Renders the four authentication HTML pages using the Jinja2 "
        "templating engine. The reset page receives the token from the "
        "URL so auth.js can submit it with the new password.")

    fn_block(story,
        "index() and spa_fallback(path)",
        "Python - Flask",
        "None - SPA routing",
        "GET / and /<path:path>",
        "Serves index.html for the root and for every client-side "
        "section URL (e.g. /chat, /dashboard, /resume), enabling browser "
        "deep links to SPA pages. Asset URLs under /static are exempt "
        "from the fallback.")

    fn_block(story,
        "serve_static(filename)",
        "Python - Flask send_from_directory",
        "None - static assets",
        "GET /static/<path:filename>",
        "Serves CSS, JavaScript, images and fonts from the static folder "
        "with proper MIME types, used by the HTML pages above.")

    story.append(Paragraph("5.2 Search and role-domain APIs", ST_H2))

    fn_block(story,
        "api_search()",
        "Python; dictionary lookups; string normalisation",
        "No neural model in the default path - the AI-assisted role "
        "guide data lives in ROLE_GUIDES_DB; the same capability is "
        "replicated by the n8n Gemini workflow",
        "POST /api/search",
        "The most important endpoint. It resolves the query into related "
        "roles using get_related_roles, generates the primary role guide "
        "plus the top 5 related guides via get_role_guide, records the "
        "search in the user session history and returns the complete "
        "package including deep links to 14 job platforms.")

    fn_block(story,
        "api_expand_roles()",
        "Python",
        "ROLE_MAP semantic grouping (expert-system over a curated "
        "dictionary of 10 role families)",
        "POST /api/expand-roles",
        "Accepts a single role and returns all related job titles by "
        "looking up the ROLE_MAP dictionary (e.g. python developer "
        "expands to 18 titles). If the role is unknown, _expand_generic "
        "constructs sensible variants automatically.")

    story.append(Paragraph("5.3 Analysis and career APIs", ST_H2))

    fn_block(story,
        "api_analyze_resume()",
        "Python; multipart file handling; PDF/DOCX decoding fallbacks",
        "Invokes the heuristic ATS scoring engine "
        "(analyze_resume_text) - a 10-category weighted expert model; "
        "Gemini and Hugging Face versions exist as AI upgrade paths",
        "POST /api/analyze-resume",
        "Accepts resume text or an uploaded .txt/.pdf/.docx file (up to "
        "16 MB), extracts plain text, runs the weighted ATS analysis, "
        "logs the score and resume version to the session dashboard, and "
        "returns the full JSON report: ats_score, ranking, breakdown, "
        "sections, contact info, skills, keywords, readability, "
        "strengths, weaknesses, suggestions and skill gap.")

    fn_block(story,
        "api_skill_gap()",
        "Python",
        "Set-based skill matching plus a rule-based priority classifier "
        "that labels missing skills as critical/important/optional; "
        "learning roadmap drawn from LEARNING_RESOURCES knowledge base",
        "POST /api/skill-gap",
        "Compares the user's skill list with the required skills for the "
        "target role, computes a match percentage, categorises missing "
        "skills by importance and returns a step-by-step learning "
        "roadmap (skill type, difficulty, estimated time and the best "
        "free learning resources).")

    fn_block(story,
        "api_interview_prep()",
        "Python",
        "INTERVIEW_QUESTIONS_DB curated question bank (expert-written); "
        "on-demand AI generation with gemini-pro in "
        "utils/api_integrations.py",
        "POST /api/interview-prep",
        "Returns the full interview question pack for the selected role "
        "grouped into technical, behavioral and coding categories, each "
        "question containing answer tips for the candidate.")

    fn_block(story,
        "api_career_insights()",
        "Python",
        "CAREER_INSIGHTS_DB curated market-data knowledge base; live "
        "salary data can be merged through FreeAPIIntegrations",
        "POST /api/career-insights",
        "Returns structured market intelligence for a role: average US "
        "salary, INR salary range, demand level, growth forecast, hiring "
        "trend, top hiring companies, key industries and entry/senior "
        "level salaries.")

    story.append(PageBreak())
    story.append(Paragraph("5.4 Dashboard session APIs", ST_H2))

    fn_block(story,
        "api_dashboard(), api_save_job(), api_remove_job(), and ATS "
        "history endpoints",
        "Python",
        "None - in-memory session store keyed by UUID (get_session_id + "
        "get_user_data)",
        "GET/POST /api/dashboard/*",
        "Persists the anonymous user's saved role guides, ATS score "
        "history, resume versions, tracked skill progress and search "
        "history inside the Flask session store, and exposes them to the "
        "dashboard page. Deduplication prevents the same job guide being "
        "saved twice.")

    story.append(Paragraph("5.5 Chat & moderation APIs", ST_H2))

    fn_block(story,
        "Chat policy, member, message and moderation endpoints",
        "Python + SQLAlchemy (ChatMessage, ChatUserStatus models)",
        "Rule-based moderation: message flagging keywords, ban/private "
        "status logic",
        "/api/chat/policy, /api/chat/accept-policy, /api/chat/messages, "
        "/api/chat/members, /api/chat/post, moderation routes",
        "A privacy-policy-gated group chat for logged-in users. First a "
        "policy screen must be accepted, then messages stream through a "
        "lightweight polling mechanism in app.js. Messages that violate "
        "the rules are flagged server-side, and users can be banned with "
        "an explanatory reason so the UI can block access. Members are "
        "listed with online status.")

    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 6 - CORE AI/ML ANALYSIS ENGINES
# ─────────────────────────────────────────────────────────────────────
def s6_engines(story):
    section_title(story, "6. Core AI/ML Analysis Engines in Detail")
    story.append(Paragraph(
        "These pure-Python functions are the analytical heart of the "
        "site. They are deterministic, explainable and require no GPU - "
        "a deliberate design choice that makes scores auditable.", ST_BODY))

    fn_block(story,
        "analyze_resume_text(text, target_role) - the ATS engine",
        "Python - regex, statistics and weighted aggregation (no "
        "external ML library)",
        "Heuristic expert system. Ten weighted components produce the "
        "100-point ATS score, mimicking commercial tools like Jobscan "
        "and ResumeWorded (weights below).",
        "app.py analyze_resume_text()",
        "Splits the resume into words and sentences; measures word count "
        "and average sentence length; detects 8 standard sections via "
        "regex; extracts email, phone, LinkedIn, GitHub and portfolio "
        "links; matches keywords against the targeted role; counts "
        "action verbs; checks grammar issues such as too many fragments "
        "or informal language (um/uh/basically); computes ATS "
        "compatibility; then combines: sections 10, contact 5, keywords "
        "30, experience 20, skills 15, education 5, projects 10, "
        "grammar 10, length 5, ATS 5 (scaled). Produces a ranking "
        "band (Poor through Excellent) plus actionable suggestions with "
        "priority and estimated score impact.")

    fn_block(story,
        "_extract_skills_from_text() - skill NLP extractor",
        "Python - regular expressions generated dynamically from the "
        "SKILLS_DATABASE of 150+ skills in 10 categories",
        "Dictionary/database matcher with word-boundary regex; a "
        "rule-based information-extraction model equivalent to a "
        "zero-shot tagger but fully offline",
        "app.py SKILLS_DATABASE",
        "Lower-cases the text and scans for every known skill wrapped in "
        "word boundaries (so 'python' is not matched by 'pythons'). "
        "Returns a de-duplicated sorted skill list used by both the ATS "
        "engine and the skill-gap endpoint.")

    fn_block(story,
        "get_related_roles(), _expand_generic() - semantic role "
        "expansion",
        "Python - dictionary index + text heuristics",
        "Curated semantic graph: ROLE_MAP groups 200+ job titles into "
        "10 role families by labour-market similarity",
        "app.py ROLE_MAP",
        "Looks up the canonical role family for any query, then returns "
        "all sibling job titles. For roles not in the map, "
        "_expand_generic manufactures a plausible list by combining the "
        "role stem with seniority and specialism keywords, so the "
        "search experience never returns empty.")
    fn_block(story,
            "QueryParser - natural-language job query parser",
            "Python - regex/NLP-lite",
            "Heuristic parser with a knowledge base of Indian cities and "
            "location/role indicator words (the NLP-lite cousin of a named "
            "entity recogniser)",
            "utils/query_parser.py",
            "Turns a sentence such as 'product manager role in bangalore' "
            "into a structured ParsedQuery with job title, location and "
            "keywords. It extracts the location first using indicator "
            "phrases and the city database, then strips role indicators "
            "and stop words to recover the job title, cleans extra spaces "
            "and returns the remaining meaningful words as keywords. It "
            "also builds Naukri, RemoteOK and Wellfound search URLs and "
            "queries from the parsed result.")

    fn_block(story,
        "FreeAPIIntegrations - AI extension layer",
        "Python - requests, google-generativeai, huggingface-hub",
        "gemini-pro (primary LLM); facebook/bart-large-mnli (zero-shot "
        "fallback); Adzuna, JSearch, ESCO and O*NET data APIs",
        "utils/api_integrations.py",
        "A single Python class that reads API keys from environment "
        "variables, adds a one-hour TTL cache with LRU helpers around "
        "every external call, exposes analyze_resume_with_gemini (with "
        "JSON extraction from the model output), "
        "analyze_resume_with_huggingface (multi-label zero-shot "
        "classification of resume sections), "
        "generate_interview_questions_ai, job search through Adzuna "
        "and JSearch, skills through ESCO, and reports which "
        "integrations are configured. Every method fails soft (returns "
        "empty results or an error dict) so the site keeps working "
        "without API keys.")

    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 7 - AUTH & SECURITY
# ─────────────────────────────────────────────────────────────────────
def s7_auth(story):
    section_title(story, "7. Authentication & Security Functions")
    story.append(Paragraph(
        "utils/auth.py implements enterprise-grade authentication on top "
        "of Flask-Login. The ML-relevant detail is that risk detection "
        "(brute-force lockout) is deterministic rule logic, while every "
        "password is hashed with bcrypt so no plaintext ever touches the "
        "database.", ST_BODY))

    fn_block(story,
        "validate_password(password), validate_email_address(email)",
        "Python - regex + email-validator library",
        "None - rule-based policy checks (password entropy policy model)",
        "utils/auth.py",
        "Enforces a strict password policy: minimum 8 and maximum 128 "
        "characters, at least one uppercase, one lowercase, one digit and "
        "one special character, and rejection of common patterns "
        "(password, 123456, qwerty...). Email addresses are validated "
        "against RFC standards by the email-validator package.")

    fn_block(story,
        "sanitize_input(text), sanitize_json(data)",
        "Python - regex",
        "None - XSS defence rules",
        "utils/auth.py",
        "Strips HTML tags, removes script blocks and inline event "
        "handlers (onclick, onload, ...) to neutralise stored and "
        "reflected XSS before data is stored or rendered.")

    fn_block(story,
        "create_user_account(), authenticate_user()",
        "Python - SQLAlchemy + werkzeug bcrypt",
        "None - the auth risk model is rule-based: 5 failed attempts "
        "lock the account for 15 minutes (record_login_attempt)",
        "utils/auth.py  (called by /api/auth/signup, /api/auth/login)",
        "Creates users with salted bcrypt hashes, a profile row and "
        "default preferences; logs every signup and login to the audit "
        "table with the IP address. authenticate_user applies the "
        "locked-until lockout, verifies the hash, and on success resets "
        "failed-attempt counters and records last_login.")

    fn_block(story,
        "initiate_password_reset(), reset_password()",
        "Python - secrets.token_urlsafe + SQLAlchemy",
        "None - cryptographic random tokens and expiry rules",
        "utils/auth.py  (called by /api/auth/* password routes)",
        "Generates a single-use random token with a fixed expiry, stores "
        "it in the PasswordResetToken table and simulates sending it by "
        "email (logged to the console). reset_password validates the "
        "token lifecycle, applies password rules, re-hashes the new "
        "password, invalidates every active session of the user and "
        "writes an audit log entry.")

    fn_block(story,
        "get_user_dashboard_data(user)",
        "Python - SQLAlchemy aggregations",
        "None - statistics queries",
        "utils/auth.py  (served by GET /api/auth/me)",
        "Collects saved jobs, applications and interviews for the logged-"
        "in user and computes derived statistics: total saved, total "
        "applications, total interviews, active applications and offers "
        "received.")

    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 8 - JOB SCRAPING SUBSYSTEM
# ─────────────────────────────────────────────────────────────────────
def s8_scrapers(story):
    section_title(story, "8. Job Scraping Subsystem")
    story.append(Paragraph(
        "The command-line agent (main.py + scrapers/) collects live job "
        "postings from three platforms and stores them in CSV. Each "
        "platform needs a different extraction technique, which is why "
        "three approaches coexist inside the same Python codebase.", ST_BODY))

    fn_block(story,
        "main() - CLI entry point",
        "Python - argparse",
        "None - orchestrator; a job-title relevance checker "
        "(_matches_job_role) filters results with word-overlap logic",
        "main.py",
        "Parses --job-role, --location, --output, --limit, --cache-html "
        "and --save-html, runs the three scrapers in sequence, filters "
        "every result for role relevance, de-duplicates by URL and "
        "saves the final list using CSVStorage.")

    fn_block(story,
        "NaukriScraper.scrape()",
        "Python - requests + BeautifulSoup + lxml, pandas for data",
        "None - HTML structure parsing + pagination rules",
        "scrapers/naukri_scraper.py",
        "Builds the Naukri search URL from the parsed query, fetches the "
        "HTML with requests (rotating through pages for pagination), "
        "parses job cards with BeautifulSoup CSS selectors and "
        "normalises each result into the Job dataclass. HTML can be "
        "cached for offline re-runs via utils/html_cache.py.")

    fn_block(story,
        "RemoteOKScraper.scrape()",
        "Python - requests against the public JSON API",
        "None - JSON mapping; a keyword-relevance heuristic keeps "
        "technical roles in the results",
        "scrapers/remoteok_scraper.py",
        "Fetches https://remoteok.com/api directly, selects jobs up to "
        "the requested limit, maps the flat JSON fields (position, "
        "company, location, salary, url, date, description) onto the Job "
        "model and filters by role keywords when needed.")

    story.append(PageBreak())
    fn_block(story,
        "WellfoundScraper.scrape()",
        "Python - Playwright (headless Chromium) + Firecrawl",
        "None - browser automation + network-response capture; not an ML "
        "model, but it renders JavaScript so the site's client-side "
        "logic executes",
        "scrapers/wellfound_scraper.py",
        "Launches a headless browser, registers a response listener that "
        "captures every JSON payload containing 'jobs', opens the "
        "Wellfound search URL and waits for the network calls to finish. "
        "This API-interception technique survives modern JavaScript-"
        "rendered SPAs and returns structured JSON without fragile DOM "
        "parsing. Firecrawl-py is available as a fallback service.")

    fn_block(story,
        "CSVStorage.save_to_csv() and Job/JobValidator models",
        "Python - csv module + dataclasses",
        "None - data validation rules",
        "storage/csv_storage.py, models/job_model.py",
        "Standardises scraped records (cleaning text, verifying URL "
        "protocols, checking required fields and allowed source "
        "platforms) and exports them to a CSV with columns job_title, "
        "company_name, location, job_url, salary, description, "
        "posted_date and source.")

    story.append(PageBreak())


# ─────────────────────────────────────────────────────────────────────
#  SECTION 9 - DATABASE LAYER
# ─────────────────────────────────────────────────────────────────────
def s9_database(story):
    section_title(story, "9. Database Layer (SQLAlchemy Models)")
    story.append(Paragraph(
        "All persistence is handled by Flask-SQLAlchemy ORM. In "
        "development the engine uses SQLite; in production DATABASE_URL "
        "switches to PostgreSQL with connection pooling "
        "(pool_pre_ping, pool_size 10, max_overflow 20). The schemas "
        "below are the 'memory' of every function described so far.", ST_BODY))

    data = [
        ["Model / Table", "Key Columns", "Functions It Backs"],
        ["User (users)", "email, username, password_hash, "
         "login_attempts, locked_until, last_login",
         "signup, login, lockout, password reset"],
        ["UserProfile (user_profiles)", "full_name, phone, location, "
         "headline, linkedin/github/portfolio, resume_text, skills",
         "dashboard /api/auth/me, profile view"],
        ["UserPreference", "language, theme, weekly_digest, "
         "search_radius_km, preferred_locations",
         "settings, job alert scoping"],
        ["SavedJob", "role_title, company, status, guide_data",
         "dashboard saved guides, save/remove-job APIs"],
        ["JobApplication", "company, role, status, applied_date",
         "application tracker stats"],
        ["InterviewHistory", "company, role, interview_type, status, "
         "date",
         "interview tracker stats"],
        ["UserSession", "user_id, token, is_active",
         "active-session invalidation on password reset"],
        ["AuditLog", "action, resource_type/ID, ip_address",
         "full audit trail for every security event"],
        ["PasswordResetToken", "token, expires_at, is_used",
         "forgot/reset password flow"],
        ["ChatMessage", "user_id, message, message_type, is_flagged",
         "community chat stream + moderation"],
        ["ChatUserStatus", "has_accepted_policy, is_banned, ban_reason",
         "chat policy gate and ban screen"],
        ["Job (dataclass, not a table)", "job_title, company, location, "
         "salary, source",
         "scraper normalisation + validation"],
    ]
    t = Table(data, colWidths=[48 * mm, 80 * mm, 50 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#134e4a")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 10 - N8N AI WORKFLOWS
# ─────────────────────────────────────────────────────────────────────
def s10_n8n(story):
    section_title(story, "10. n8n AI Orchestration Workflows")
    story.append(Paragraph(
        "The n8n/ folder contains five automation workflows defined in "
        "JSON (the JS-box language of n8n is JavaScript). Each workflow "
        "listens on a webhook, calls the Google AI node with gemini-pro, "
        "post-processes the output with JavaScript code nodes and writes "
        "the result to PostgreSQL. This duplicates and extends the "
        "in-app AI capabilities described in Section 3.", ST_BODY))

    wf_rows = [
        ["Workflow File", "Trigger", "AI Model", "Pipeline"],
        ["resume_analysis_workflow.json", "Webhook POST "
         "resume-analysis", "gemini-pro (temperature 0.3)",
         "Webhook -> Google AI -> JS parse/JSON-extract -> Postgres "
         "insert -> Respond"],
        ["interview_prep_workflow.json", "Webhook POST interview-prep",
         "gemini-pro",
         "Webhook -> Google AI -> JS structure -> Respond"],
        ["career_insights_workflow.json", "Webhook POST career-insights",
         "gemini-pro",
         "Webhook -> Google AI -> JS structure -> Respond"],
        ["job_recommendations_workflow.json", "Webhook POST "
         "recommendations", "gemini-pro",
         "Webhook -> Google AI -> JS structure -> Respond"],
        ["feedback_processing_workflow.json", "Webhook POST feedback",
         "gemini-pro",
         "Webhook -> Google AI (sentiment/summary) -> JS structure -> "
         "Postgres insert -> Respond"],
    ]
    t = Table(wf_rows, colWidths=[48 * mm, 40 * mm, 30 * mm, 60 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_MODEL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "The JS Code nodes include a JSON-extraction routine "
        "(const m = $json.message.content.match(/\\\\{[\"']s/...) with a "
        "fallback structure that guarantees a valid response even when "
        "the LLM output is malformed - the same fail-soft design used in "
        "the Python layer. Making requests through n8n instead of Python "
        "lets operations staff rewire prompts and model versions without "
        "deploying code.", ST_BODY))

    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  SECTION 11 - APPENDIX: SIBLING PROJECTS
# ─────────────────────────────────────────────────────────────────────
def s11_appendix(story):
    section_title(story, "13. Appendix - Sibling Projects in the Workspace")
    story.append(Paragraph(
        "The workspace folder also contains two additional projects. "
        "They are separate applications but live under the same directory "
        "tree - listed here for completeness.", ST_BODY))

    fn_block(story,
        "job-platform (investment tracking platform)",
        "Python Flask backend + JavaScript/HTML/CSS frontend + SQLite "
        "database (platform.db)",
        "None - however it interacts with market-data APIs; SIP "
        "simulation uses compounding math (future-value formula) rather "
        "than ML forecasting",
        "job-platform/app.py and job-platform/static/app/index.html",
        "A full investment platform with watchlists, portfolios and "
        "holdings CRUD, an SIP (Systematic Investment Plan) simulator, "
        "price/volume alerts, admin asset management and audit logs. "
        "Its own app.py defines portfolio, watchlist, alert, admin, "
        "config and SPA-routing endpoints.")

    fn_block(story,
        "farsan-showcase (Next.js product showcase site)",
        "TypeScript (SOLID JSX/React), Next.js, Tailwind CSS",
        "None - static marketing/showcase site",
        "farsan-showcase/src/app/page.tsx, layout.tsx, globals.css",
        "A Next.js 14-style App Router site with clearly separated "
        "server and client components (\"use client\" directives), a "
        "landing page, feature sections and product galleries. It uses "
        "TypeScript interfaces for typed props and Tailwind for "
        "styling.")

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        "End of guide. Every function described above can be verified "
        "directly in the project source code. The design principle is "
        "consistent across the whole system: heavy, explainable logic in "
        "Python rule engines for instant responses, and transformer "
        "models (gemini-pro, bart-large-mnli) reserved for the tasks "
        "that genuinely need generative or zero-shot intelligence.",
        ST_BODY_IND))


# ─────────────────────────────────────────────────────────────────────
#  SECTION 12 - HARDWARE-CONSTRAINED ARCHITECTURE PLAN
# ─────────────────────────────────────────────────────────────────────
def s12_architecture(story):
    section_title(story,
        "12. Hardware-Constrained Architecture Plan & Proposed Local AI Stack")
    story.append(Paragraph(
        "Full design is in docs/ARCHITECTURE.md. The development machine "
        "is an Intel Core i7-6820HQ (4 cores / 8 threads) with 32 GB RAM "
        "and a Quadro M2000M 4 GB GPU. The plan forbids running an LLM "
        "for every operation; each concern gets a specialised "
        "lightweight component, and any LLM work goes through a swappable "
        "LocalLLMProvider abstraction instead of hard-coding Ollama.",
        ST_BODY))

    story.append(Paragraph("12.1 Specialised lightweight components "
                           "(languages + models per function)", ST_H2))
    comp_rows = [
        ["#", "Function", "Implementation (Language + Local Model)", "Runtime"],
        ["1", "Resume PDF/DOCX extraction",
         "Python - pdfplumber, python-docx, PyPDF2 (local document parser)",
         "CPU"],
        ["2", "Resume entity extraction",
         "Python - local NER: spaCy small model or GLiNER (tiny/"
         "quantized); regex fallback for email/phone/LinkedIn/GitHub",
         "CPU"],
        ["3", "Skill extraction & normalization",
         "Python - NLP + skill taxonomy + rules/ML: SKILLS_DATABASE "
         "regex matcher + synonym alias table, optional TF-IDF",
         "CPU"],
        ["4", "Resume <-> Job matching",
         "Python - sentence-transformers all-MiniLM-L6-v2 (or "
         "ONNX-quantized MiniLM); cosine similarity + deterministic "
         "keyword score; embeddings cached in DB",
         "CPU"],
        ["5", "ATS scoring",
         "Python - existing deterministic explainable weighted engine",
         "CPU"],
        ["6", "Skill-gap analysis",
         "Python - rules + matching engine (LEARNING_RESOURCES + "
         "taxonomy normalization)",
         "CPU"],
        ["7", "Market-demand analysis",
         "Python - statistics computed from real Adzuna/JSearch job "
         "data (counts, salary median/percentiles); no generative AI",
         "CPU"],
        ["8", "Recommendations",
         "Python - rules + ML where useful; precomputed embedding "
         "similarity in batches; cached per user profile",
         "CPU, batch"],
        ["9", "Interview question generation",
         "Python - local small/quantized LLM (e.g. Qwen2.5-Instruct "
         "1.5B/3B, Llama 3.2 1B/3B in Q4_K_M/Q8_0) via "
         "LocalLLMProvider; curated INTERVIEW_QUESTIONS_DB remains "
         "offline primary",
         "Local LLM, CPU"],
        ["10", "Interview evaluation",
         "Python - rubric keyword/coverage scoring first; local LLM "
         "only for open-ended answers and only for uncached input",
         "Rules first, LLM sparingly"],
    ]
    t = Table(comp_rows, colWidths=[8 * mm, 40 * mm, 86 * mm, 44 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#166534")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f8fafc")]),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 8))

    story.append(Paragraph("12.2 Where LLM inference is allowed vs "
                           "forbidden", ST_H2))
    story.append(Paragraph(
        "<b>Allowed:</b> interview question generation (small quantized "
        "local LLM); interview evaluation for open-ended free-text only, "
        "after rubric scoring, only when not cached; optional occasional "
        "'explain my result' generation.", ST_BODY))
    story.append(Paragraph(
        "<b>Forbidden:</b> page loads, job matching, skill comparisons, "
        "database operations, ATS scores, skill-gap computation, "
        "market-demand stats, recommendations and resume parsing never "
        "call an LLM.", ST_BODY))

    story.append(Paragraph("12.3 LocalLLMProvider abstraction", ST_H2))
    story.append(Paragraph(
        "Backend never imports a provider SDK directly. A Python ABC "
        "(chat, complete, optional embed, health, model_info, metrics) "
        "plus a get_provider() factory sit in a planned "
        "services/llm/ package. Supported backends: Ollama, llama.cpp "
        "llama-server, LM Studio, Jan and any OpenAI-compatible local "
        "endpoint - selected by LOCAL_LLM_PROVIDER and "
        "LOCAL_LLM_BASE_URL. Because the interface is HTTP-shaped, "
        "inference can later move to a separate server for many "
        "concurrent users by changing one config value.", ST_BODY))

    story.append(Paragraph("12.4 Caching strategy (avoid repeated "
                           "inference)", ST_H2))
    bullet(story, [
        "<b>In-memory layer:</b> cachetools.TTLCache for hot results in "
        "the same process (e.g. repeated resume texts in one session).",
        "<b>Database layer (planned SQLAlchemy models):</b> "
        "ResumeAnalysisCache (per resume_text_hash + target_role: "
        "ats_score, entities, skills, embeddings, provider, model, "
        "expiry), JobAnalysisCache (per job_url_hash: embeddings, "
        "requirements, matched roles, model_used, expiry) and "
        "EmbeddingCache (unique text_hash + model_name -> vector).",
        "<b>Precomputed batches:</b> nightly jobs pre-embed the job "
        "corpus and pre-score popular role/resume pairs so the web layer "
        "only reads prepared rows.",
        "Keys are sha256 content hashes of normalized text, so identical "
        "input never runs inference twice. TTL defaults: resume "
        "analysis 24 h, job analysis 7 d, embeddings until model "
        "version changes (a model column invalidates stale rows).",
    ])

    story.append(Paragraph("12.5 Batch & asynchronous processing", ST_H2))
    story.append(Paragraph(
        "Resume NER, skill extraction and embedding runs process batches "
        "of documents (new jobs nightly, corpus re-embedding weekly) "
        "instead of running per request. Flask routes respond fast; "
        "long analysis is delegated to asyncio or a small worker queue "
        "and the client polls or is notified when ready. Market-demand "
        "statistics are recomputed by scheduled batch jobs from the "
        "cached job corpus, never via fresh model calls inside a "
        "request. Celery/RQ are optional later, not required on the "
        "constrained machine.", ST_BODY))

    story.append(Paragraph("12.6 Configurability (planned settings)", ST_H2))
    story.append(Paragraph(
        "LOCAL_LLM_PROVIDER (ollama | llama_cpp | lm_studio | jan | "
        "openai_compatible), LOCAL_LLM_BASE_URL, LOCAL_LLM_MODEL, "
        "LOCAL_LLM_QUANT, LOCAL_LLM_MAX_TOKENS, LOCAL_LLM_TIMEOUT, "
        "LOCAL_EMBEDDING_MODEL, LOCAL_EMBEDDING_DEVICE, "
        "CACHE_RESUME_ANALYSIS_DB, CACHE_JOB_ANALYSIS_DB.", ST_BODY))

    story.append(Paragraph("12.7 Benchmark-first runtime decision", ST_H2))
    story.append(Paragraph(
        "No replacement runtime is chosen yet. The plan benchmarks "
        "Ollama, llama.cpp llama-server, LM Studio and Jan on the dev "
        "machine with small quantized GGUF models (Qwen2.5-Instruct "
        "1.5B/3B, Llama 3.2 1B/3B, Phi-3-mini in Q4_K_M/Q8_0), measuring "
        "tokens/sec, first-token latency, peak RAM (< 8 GB), sustained "
        "CPU (< 60%), VRAM (< 3 GB) and temperature (< 85 C) over a "
        "10-request test. Adoption thresholds: role question pack under "
        "5 s on CPU and passing all resource limits; otherwise the "
        "curated INTERVIEW_QUESTIONS_DB runs 100% offline with no local "
        "LLM at all. Results recorded per run in docs/BENCHMARKS.md.",
        ST_BODY))

    story.append(Paragraph("12.8 Future proofing / separate server", ST_H2))
    story.append(Paragraph(
        "Migration order: (1) ship all dependency-free offline features; "
        "(2) add LocalLLMProvider + factory, benchmark, select runtime, "
        "flip config; (3) interview generation and evaluation use only "
        "the provider interface; (4) on bigger hardware or for many "
        "users, point LOCAL_LLM_BASE_URL at a dedicated inference "
        "server - no application code changes.", ST_BODY))

    story.append(PageBreak())
    story.append(PageBreak())
# ─────────────────────────────────────────────────────────────────────
#  BUILD & RUN
# ─────────────────────────────────────────────────────────────────────
def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT_PDF, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title="JobAgent - Languages & ML Models in Every Function",
        author="JobAgent Technical Documentation",
        subject="Site functions, programming languages and ML models")

    story = []
    cover_and_toc(story)
    s1_overview(story)
    s2_tech(story)
    s3_models(story)
    s4_frontend(story)
    s5_backend_auth_pages(story)
    s6_engines(story)
    s7_auth(story)
    s8_scrapers(story)
    s9_database(story)
    s10_n8n(story)
    s12_architecture(story)
    s11_appendix(story)

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print("PDF created:", OUTPUT_PDF)


if __name__ == "__main__":
    build_pdf()
