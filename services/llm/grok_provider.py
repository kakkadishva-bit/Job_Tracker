"""services/llm/grok_provider.py - xAI Grok provider (OpenAI-compatible).

Grok is the reasoning/generation layer only. Resume parsing, skill
extraction, session state, duplicate detection and scoring safeguards
remain deterministic in services/interview/*. Server-side only:
never expose API keys to frontend JavaScript.
"""
import os
import json
import logging
from typing import Dict, Any, Optional

import requests

logger = logging.getLogger(__name__)

GROK_BASE_URL = "https://api.x.ai/v1"
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Preference order for auto-discovered chat models (no responses are hardcoded -
# this only picks which model name to call when the configured one is unavailable).
_GROQ_MODEL_PREF = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b",
                    "meta-llama/llama-3.3-70b-versatile", "llama-3.3-70b-versatile",
                    "groq/compound", "groq/compound-mini"]
_GROK_MODEL_PREF = ["grok-4", "grok-3", "grok-3-mini", "grok-2-1212"]

_model_cache: Dict[str, str] = {}


def _discover_model(base_url: str, api_key: str, preferred, cache_key: str) -> str:
    """Return a usable chat model id for an OpenAI-compatible endpoint.

    Cached per process. Returns "" when discovery is not possible, so callers
    keep whatever model name was configured."""
    if cache_key in _model_cache:
        return _model_cache[cache_key]
    try:
        r = requests.get(base_url.rstrip("/") + "/models",
                         headers={"Authorization": "Bearer " + api_key}, timeout=8)
        if r.status_code != 200:
            return ""
        ids = [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
    except Exception as e:
        logger.warning("Model discovery failed for %s: %s", base_url, e)
        return ""
    # Skip non-chat models.
    usable = [i for i in ids if not any(bad in i.lower() for bad in
                                        ("whisper", "guard", "orpheus", "tts", "embed", "vision"))]
    for want in preferred:
        if want in usable or want in ids:
            _model_cache[cache_key] = want
            return want
    if usable:
        _model_cache[cache_key] = usable[0]
        return usable[0]
    return ""


def _strip_fences(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def _first_json(text: str) -> Optional[str]:
    if not text:
        return None
    s = text.find("{")
    if s < 0:
        return None
    depth = 0
    instr = False
    esc = False
    for i in range(s, len(text)):
        c = text[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return text[s:i + 1]
    return None
class GrokProvider:
    """OpenAI-compatible xAI Grok provider. Mirrors LocalLLMProvider API."""

    def __init__(self, api_key="", model="",
                 base_url=GROK_BASE_URL, timeout=30,
                 temperature=0.7, max_tokens=1024):
        self.api_key = (api_key or "").strip()
        self.model = (model or os.environ.get("GROK_MODEL", "grok-3-mini")).strip()
        self.base_url = (base_url or GROK_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._available = None
        # Reason the last call could not be served (never silently empty).
        self.last_error = ""

    def model_info(self):
        return {"runtime": "grok", "model": self.model, "base_url": self.base_url}

    def status(self) -> Dict[str, Any]:
        """Diagnostics for this provider. Never exposes the API key itself."""
        return {"runtime": "grok", "model": self.model, "base_url": self.base_url,
                "api_key_configured": bool(self.api_key), "last_error": self.last_error}

    def health_check(self):
        if self._available is None:
            if not self.api_key:
                self._available = False
                return {"available": False, "runtime": "grok",
                        "error": "No GROK_API_KEY configured"}
            try:
                import requests as _rq
                r = _rq.get(self.base_url + "/models",
                            headers=self._hdrs(), timeout=5)
                self._available = (r.status_code == 200)
            except Exception:
                self._available = False
        return {"available": self._available, "runtime": "grok",
                "model": self.model}

    def _hdrs(self):
        return {"Authorization": "Bearer " + self.api_key,
                "Content-Type": "application/json"}

    def generate(self, prompt, system_prompt="", max_tokens=None, **kw):
        if not self.api_key:
            self.last_error = ("no_api_key: no GROK_API_KEY/XAI_API_KEY configured "
                               "(xAI Grok keys start with 'xai-')")
            logger.error("Grok call skipped: %s", self.last_error)
            return ""
        msgs = []
        if system_prompt:
            msgs.append({"role": "system", "content": system_prompt})
        msgs.append({"role": "user", "content": prompt})
        payload = {"model": self.model, "messages": msgs,
                   "temperature": float(kw.get("temperature", self.temperature)),
                   "max_tokens": max_tokens or self.max_tokens}
        try:
            import requests as _rq
            r = _rq.post(self.base_url + "/chat/completions",
                         json=payload, headers=self._hdrs(), timeout=self.timeout)
            r.raise_for_status()
            ch = r.json().get("choices", [])
            if ch:
                self.last_error = ""
                return ch[0].get("message", {}).get("content", "") or ""
            self.last_error = ("empty_response: %s returned no content for model %s"
                               % (self.base_url, self.model))
            logger.error("Grok call failed: %s", self.last_error)
            return ""
        except Exception as e:
            resp = getattr(e, "response", None)
            detail = ""
            if resp is not None:
                detail = " - HTTP %s %s" % (getattr(resp, "status_code", "?"),
                                            (getattr(resp, "text", "") or "")[:200])
            self.last_error = "request_failed: %s%s" % (e, detail)
            logger.error("Grok generation failed: %s", self.last_error)
            self._available = False
            return ""

    def generate_json(self, prompt, system_prompt="", max_tokens=None, **kw):
        sys = (system_prompt + "\nOutput ONLY valid JSON." if system_prompt
               else "Output ONLY valid JSON. No explanations.")
        raw = self.generate(prompt + "\n\nIMPORTANT: Output ONLY valid JSON.",
                            system_prompt=sys, max_tokens=max_tokens or 700, **kw)
        if not raw or not raw.strip():
            return None
        clean = _strip_fences(raw)
        try:
            return json.loads(clean)
        except Exception:
            pass
        cand = _first_json(clean)
        if cand:
            try:
                return json.loads(cand)
            except Exception as e:
                logger.warning("Grok JSON parse failed: %s", e)
        self.last_error = ("invalid_json: Grok replied but no JSON object could be "
                           "parsed")
        logger.error("Grok JSON parsing failed: %s", self.last_error)
        return None


def _looks_like_xai_key(key: str) -> bool:
    return (key or "").strip().lower().startswith("xai-")


def _looks_like_groq_key(key: str) -> bool:
    return (key or "").strip().startswith("gsk_")


def llm_config_status() -> Dict[str, Any]:
    """Report the interview LLM credential state, WITHOUT exposing any key.

    The interview system uses the Groq API (api.groq.com) EXCLUSIVELY.
    Ollama, xAI/Grok, OpenAI and Gemini are never selected. Misplaced keys are
    detected and reported instead of being silently ignored.
    """
    grok_var = ""
    if (os.environ.get("GROK_API_KEY", "") or "").strip():
        grok_var = "GROK_API_KEY"
    elif (os.environ.get("XAI_API_KEY", "") or "").strip():
        grok_var = "XAI_API_KEY"
    grok_key = (os.environ.get(grok_var, "") or "").strip() if grok_var else ""
    groq_key = (os.environ.get("GROQ_API_KEY", "") or "").strip()
    runtime = (os.environ.get("LLM_RUNTIME", "") or "").strip().lower()

    notes = []
    if groq_key and _looks_like_xai_key(groq_key):
        notes.append("GROQ_API_KEY holds an xAI ('xai-') key, but the interview "
                     "uses Groq (api.groq.com) only - this key will not work; "
                     "a Groq key starts with 'gsk_'")
    elif groq_key and not _looks_like_groq_key(groq_key):
        notes.append("GROQ_API_KEY does not look like a Groq key (Groq keys "
                     "start with 'gsk_')")
    if grok_key:
        notes.append("GROK/xAI keys are ignored - the interview uses the Groq "
                     "API only (never Ollama, xAI/Grok, OpenAI or Gemini)")
    if runtime and runtime not in ("", "auto", "groq"):
        notes.append("LLM_RUNTIME=%r is ignored - only 'groq' (or unset/auto) "
                     "is supported" % runtime)

    return {
        "grok_configured": bool(grok_key),
        "grok_key_variable": grok_var,
        "groq_configured": bool(groq_key),
        "llm_runtime_env": runtime,
        "selected_runtime": "groq" if groq_key else "none (deterministic fallback)",
        "notes": notes,
    }


def get_interview_llm():
    """Return the interview LLM provider: Groq (api.groq.com) ONLY.

    Uses the GROQ_API_KEY from .env. Ollama, xAI/Grok, OpenAI and Gemini are
    never selected. When Groq is not configured this returns None - callers
    (QuestionGenerator/AnswerEvaluator) then serve deterministic results that
    are tagged with the exact reason, and the real Groq error is logged and
    surfaced, never swallowed.
    """
    from services.llm.local_llm_provider import LocalLLMProvider
    status = llm_config_status()
    for note in status["notes"]:
        logger.error("LLM credential problem: %s", note)
    groq_key = (os.environ.get("GROQ_API_KEY", "") or "").strip()
    if not groq_key:
        logger.error("Interview LLM: GROQ_API_KEY missing - no Groq provider; "
                     "interview runs in deterministic mode (Ollama/xAI/OpenAI/"
                     "Gemini are never used).")
        return None
    model = (os.environ.get("LLM_MODEL", "") or "").strip()
    if not model:
        model = (_discover_model(GROQ_BASE_URL, groq_key, _GROQ_MODEL_PREF, "groq")
                 or "openai/gpt-oss-120b")
    try:
        timeout = int(os.environ.get("LLM_TIMEOUT", "30") or 30)
    except Exception:
        timeout = 30
    logger.info("Interview LLM: using Groq (model=%s, base=%s)", model, GROQ_BASE_URL)
    return LocalLLMProvider({"runtime": "groq", "model": model, "api_key": groq_key,
                             "timeout_seconds": timeout})
