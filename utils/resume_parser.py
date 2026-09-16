"""
utils/resume_parser.py
Local, dependency-light resume text extraction for PDF / DOCX / TXT.

Strategy (best -> fallback):
  PDF : pdfplumber  ->  PyPDF2  ->  raw UTF-8 decode (last resort)
  DOCX: python-docx (zip+xml fallback)
  TXT : UTF-8 / Latin-1 decode

Every extractor degrades gracefully: if a library is missing we fall
through to the next strategy instead of raising. Callers always get a
plain string (plus a metadata dict) back.
"""

import io
import re
from typing import Dict, Any, Tuple

# ─── Optional imports (resolved lazily, never fatal) ───────────────
try:
    import pdfplumber  # type: ignore
    _HAS_PDFPLUMBER = True
except Exception:
    pdfplumber = None
    _HAS_PDFPLUMBER = False

try:
    import PyPDF2  # type: ignore
    _HAS_PYPDF2 = True
except Exception:
    PyPDF2 = None
    _HAS_PYPDF2 = False

# pypdf is the maintained fork of PyPDF2 with an identical API; treat the
# two as one capability so we never need both installed.
try:
    import pypdf as _pypdf  # type: ignore
    if not _HAS_PYPDF2:
        PyPDF2 = _pypdf
        _HAS_PYPDF2 = True
except Exception:
    pass

try:
    import docx  # python-docx  # type: ignore
    _HAS_PYTHON_DOCX = True
except Exception:
    docx = None
    _HAS_PYTHON_DOCX = False


def _clean_text(text: str) -> str:
    """Normalise whitespace while keeping line breaks for section detection."""
    if not text:
        return ""
    text = re.sub(r"[\u2018\u2019]", "'", text)
    text = re.sub(r"[\u201c\u201d]", '"', text)
    text = re.sub(r"[\u2013\u2014]", "-", text)
    text = re.sub(r"\u00a0", " ", text)          # nbsp
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()


def _squash_lines(text: str) -> str:
    """Fully collapse to single-spaced one-line text (for scoring engines)."""
    return re.sub(r"\s+", " ", text).strip()
# ─── PDF extractors ─────────────────────────────────────────────────

def _extract_pdf_pdfplumber(content: bytes) -> str:
    if not _HAS_PDFPLUMBER:
        return ""
    try:
        parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                if txt.strip():
                    parts.append(txt)
        return "\n".join(parts)
    except Exception:
        return ""


def _extract_pdf_pypdf2(content: bytes) -> str:
    if not _HAS_PYPDF2:
        return ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                txt = ""
            if txt.strip():
                parts.append(txt)
        return "\n".join(parts)
    except Exception:
        return ""


def _extract_pdf_raw(content: bytes) -> str:
    """Last resort: strip binary noise from a raw decode."""
    try:
        text = content.decode("utf-8", errors="ignore")
    except Exception:
        return ""
    text = re.sub(r"[^\x20-\x7e\n]", " ", text)
    return text if len(_squash_lines(text)) >= 50 else ""


def _extract_pdf(content: bytes) -> str:
    for fn in (_extract_pdf_pdfplumber, _extract_pdf_pypdf2, _extract_pdf_raw):
        text = _clean_text(fn(content))
        if len(_squash_lines(text)) >= 50:
            return text
    return ""
# ─── DOCX extractors ────────────────────────────────────────────────

def _extract_docx_pydocx(content: bytes) -> str:
    if not _HAS_PYTHON_DOCX:
        return ""
    try:
        document = docx.Document(io.BytesIO(content))
        parts = [p.text for p in document.paragraphs if p.text.strip()]
        # Tables often hold experience/skills in resumes
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    t = cell.text.strip()
                    if t:
                        parts.append(t)
        return "\n".join(parts)
    except Exception:
        return ""


def _extract_docx_zipxml(content: bytes) -> str:
    """Fallback: DOCX is a zip; pull text out of word/document.xml."""
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            with zf.open("word/document.xml") as f:
                tree = ET.parse(f)
        W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        parts = []
        for p in tree.iter(W + "p"):
            line = "".join(t.text or "" for t in p.iter(W + "t"))
            if line.strip():
                parts.append(line)
        return "\n".join(parts)
    except Exception:
        return ""


def _extract_docx(content: bytes) -> str:
    for fn in (_extract_docx_pydocx, _extract_docx_zipxml):
        text = _clean_text(fn(content))
        if len(_squash_lines(text)) >= 50:
            return text
    return ""


# ─── TXT ────────────────────────────────────────────────────────────

def _extract_txt(content: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return _clean_text(content.decode(enc))
        except Exception:
            continue
    return ""


# ─── Public API ─────────────────────────────────────────────────────

def extract_resume_text(filename: str, content: bytes) -> Tuple[str, Dict[str, Any]]:
    """
    Extract resume text from an uploaded file.

    Returns (text, meta) where meta reports which extractor succeeded.
    Never raises; returns ("", meta) on total failure so callers can
    fall back to pasted text.
    """
    name = (filename or "").lower()
    meta: Dict[str, Any] = {"filename": filename, "engine": None, "chars": 0}

    if name.endswith(".pdf") or (content[:5] == b"%PDF-"):
        text = _extract_pdf(content)
        if text:
            meta["engine"] = "pdfplumber" if _HAS_PDFPLUMBER else (
                "PyPDF2" if _HAS_PYPDF2 else "raw-decode")
    elif name.endswith(".docx"):
        text = _extract_docx(content)
        if text:
            meta["engine"] = "python-docx" if _HAS_PYTHON_DOCX else "zip-xml"
    else:
        text = _extract_txt(content)
        if text:
            meta["engine"] = "utf-8"

    meta["chars"] = len(_squash_lines(text))
    return text, meta


def is_extraction_available() -> Dict[str, bool]:
    """Expose which optional libraries are installed (for /health or UI hints)."""
    return {
        "pdfplumber": _HAS_PDFPLUMBER,
        "pypdf2": _HAS_PYPDF2,
        "python_docx": _HAS_PYTHON_DOCX,
    }