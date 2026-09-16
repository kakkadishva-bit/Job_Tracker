"""
services/llm/local_llm_provider.py
Abstract local LLM provider supporting multiple runtimes.
"""
import os
import json
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
import requests

logger = logging.getLogger(__name__)


class LocalLLMProvider:
    """Unified interface to local LLM runtimes (Ollama, llama.cpp, LM Studio, etc.)."""

    # Transient HTTP statuses: rate limits, throttling, gateway/5xx.
    RETRYABLE_STATUS = (408, 409, 425, 429, 500, 502, 503, 504)
    MAX_RETRIES = 3
    # Reasoning models (e.g. gpt-oss) spend tokens on hidden reasoning before
    # emitting JSON, so a small budget truncates the reply mid-string. These
    # budgets are raised so structured output survives.
    JSON_TOKEN_BUDGET = 2048
    JSON_TOKEN_BUDGET_RETRY = 4096
    # Once an endpoint is known to be unreachable (connection refused), skip
    # calls for a short window instead of paying the full retry/backoff cost on
    # every single interview turn. Time-based, so a runtime that comes up later
    # is picked up automatically.
    UNREACHABLE_COOLDOWN = 30.0

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.runtime = self.config.get("runtime", "ollama")
        self.model = self.config.get("model") or ""
        self.base_url = (self.config.get("base_url") or
                         os.environ.get("LLM_BASE_URL") or
                         self._default_base_url())
        self.api_key = self.config.get("api_key")  # only needed for hosted runtimes (e.g. groq)
        try:
            self.timeout = int(self.config.get("timeout_seconds") or
                               os.environ.get("LLM_TIMEOUT", "30") or 30)
        except Exception:
            self.timeout = 30
        self.max_tokens = self.config.get("max_tokens", 1024)
        self.temperature = self.config.get("temperature", 0.7)
        self._available = None
        self._available_checked_at = 0.0
        self._unreachable_until = 0.0
        # Last reason a call could not be served. Never empty after a failure, so
        # callers can report WHY the interview fell back instead of hiding it.
        self.last_error = ""
        self._discovered_models: Optional[List[str]] = None
        # Model ranking: live models are discovered from the runtime, so a
        # retired/renamed model can never leave the interview on static
        # fallbacks. This is model-name resolution only - no response text is
        # ever hardcoded.
        self._model_preferences = {
            "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.8-27b",
                     "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                     "mixtral-8x7b-32768", "gemma2-9b-it"],
        }
        if not self.model:
            self.model = self._default_model()

    def _default_model(self) -> str:
        env_model = os.environ.get("LLM_MODEL", "").strip()
        if env_model:
            return env_model
        defaults = {
            "groq": "openai/gpt-oss-120b",
            "ollama": "phi3",
            "lm_studio": "local-model",
            "llama_cpp": "local-model",
            "jan": "local-model",
        }
        return defaults.get(self.runtime, "phi3")

    def _default_base_url(self) -> str:
        defaults = {
            "ollama": "http://localhost:11434",
            "llama_cpp": "http://localhost:8080",
            "lm_studio": "http://localhost:1234",
            "jan": "http://localhost:1313",
            "groq": "https://api.groq.com/openai/v1",  # hosted, free tier, OpenAI-compatible
        }
        return defaults.get(self.runtime, "http://localhost:11434")

    def _headers(self) -> Dict[str, str]:
        if self.api_key and self.runtime in ("groq", "grok", "xai"):
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def _models_url(self) -> Optional[str]:
        if self.runtime == "groq":
            return f"{self.base_url.rstrip('/')}/models"
        if self.runtime == "lm_studio":
            return f"{self.base_url.rstrip('/')}/v1/models"
        if self.runtime == "ollama":
            return f"{self.base_url.rstrip('/')}/api/tags"
        return None

    def discover_models(self) -> List[str]:
        """Ask the runtime which models actually exist. Deterministic cache.

        Prevents a retired/renamed model (e.g. llama-3.3-70b-versatile on
        Groq) from silently degrading every interview turn to static
        fallbacks. Returns [] when the runtime cannot be reached.
        """
        if self._discovered_models is not None:
            return self._discovered_models
        url = self._models_url()
        if not url or not self.api_key and self.runtime == "groq":
            self._discovered_models = []
            return self._discovered_models
        try:
            resp = requests.get(url, headers=self._headers(), timeout=5)
            if resp.status_code != 200:
                self._discovered_models = []
                return self._discovered_models
            payload = resp.json()
            if self.runtime == "ollama":
                ids = [m.get("name", "") for m in payload.get("models", [])]
            else:
                ids = [m.get("id", "") for m in payload.get("data", [])]
            self._discovered_models = [i for i in ids if i]
        except Exception:
            self._discovered_models = []
        return self._discovered_models

    def resolve_model(self) -> str:
        """Pick a live model: configured first, then discovered preferences."""
        live = self.discover_models()
        if not live:
            return self.model
        if self.model and self.model in live:
            return self.model
        prefs = self._model_preferences.get(self.runtime, [])
        for p in prefs:
            if p in live:
                logger.warning("Configured model %r unavailable; using %r", self.model, p)
                self.model = p
                return self.model
        if self.model not in live:
            logger.warning("Configured model %r unavailable; using %r", self.model, live[0])
            self.model = live[0]
        return self.model

    def health_check(self) -> Dict[str, Any]:
        """Check if the LLM runtime is available (TTL-cached, never permanent)."""
        import time
        now = time.time()
        if self._available is None or (not self._available and now - self._available_checked_at > 30):
            try:
                if self.runtime == "groq":
                    url = f"{self.base_url.rstrip('/')}/models"
                    if not self.api_key:
                        self._available = False
                        self._available_checked_at = now
                        self.last_error = ("no_api_key: runtime 'groq' has no API key "
                                           "(set GROQ_API_KEY in .env)")
                        return {"available": False, "runtime": self.runtime, "model": self.model,
                                "base_url": self.base_url,
                                "error": "No GROQ_API_KEY configured"}
                elif self.runtime == "lm_studio":
                    url = f"{self.base_url.rstrip('/')}/v1/models"
                elif self.runtime == "llama_cpp":
                    url = f"{self.base_url.rstrip('/')}/health"
                else:
                    url = f"{self.base_url.rstrip('/')}/api/tags"

                resp = requests.get(url, headers=self._headers(),
                                    timeout=min(5, self.timeout or 5))
                self._available = resp.status_code == 200
            except Exception:
                self._available = False
                # Don't re-probe a dead endpoint on every single call.
                self._unreachable_until = time.time() + self.UNREACHABLE_COOLDOWN
            self._available_checked_at = now
            if self._available:
                self.resolve_model()
        return {"available": self._available, "runtime": self.runtime,
                "model": self.model, "base_url": self.base_url}

    def _build_payload(self, prompt: str, system_prompt: str = "",
                       max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """Build runtime-specific request payload."""
        if self.runtime == "ollama":
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": max_tokens or self.max_tokens,
                }
            }
        else:
            # OpenAI-compatible (LM Studio, llama.cpp server, Jan, Groq, Grok)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": self.temperature,
                "max_tokens": max_tokens or self.max_tokens,
            }
            # Reasoning models burn the token budget on hidden reasoning, which
            # is what truncated structured JSON. Keep effort low for the short
            # interview turns so the visible answer/JSON is not cut off.
            if self.runtime in ("groq", "grok", "xai") and "gpt-oss" in (self.model or ""):
                payload["reasoning_effort"] = self.config.get("reasoning_effort", "low")
        return payload

    def _parse_response(self, resp_json: Dict[str, Any]) -> str:
        """Parse runtime-specific response into text."""
        if self.runtime == "ollama":
            return resp_json.get("response", "")
        # OpenAI-compatible
        choices = resp_json.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return resp_json.get("text", "")

    def generate(self, prompt: str, system_prompt: str = "",
                 max_tokens: Optional[int] = None, **kwargs) -> str:
        """Generate text from the LLM.

        Resilience rules (deterministic, code-level):
          * Rate limits (429) and 5xx/timeouts are TRANSIENT - back off and
            retry, and keep the provider available. A single 429 must never
            silently downgrade the whole interview to static questions.
          * Model-level errors (400/404/422) mean a retired/renamed model:
            re-resolve against the live model list and retry once.
          * Missing credentials is the only case where we skip the call.
        """
        if self.runtime in ("groq", "grok", "xai") and not self.api_key:
            self.last_error = ("no_api_key: runtime '%s' has no API key configured - set "
                               "GROQ_API_KEY (api.groq.com) or GROK_API_KEY/XAI_API_KEY "
                               "(api.x.ai) in .env" % self.runtime)
            logger.error("LLM call skipped: %s", self.last_error)
            return ""
        if not self._available and self.health_check().get("error"):
            # Only a credentials/config error blocks generation.
            self.last_error = ("health_check_failed: %s"
                               % (self.health_check().get("error") or "unknown"))
            logger.error("LLM call skipped: %s", self.last_error)
            return ""
        # Recently proven unreachable (connection refused): skip without paying
        # the retry/backoff cost again. Callers fall back deterministically.
        if self._unreachable_until and time.time() < self._unreachable_until:
            self.last_error = ("unreachable: %s not reachable (cooldown %.0fs remaining)"
                               % (self.base_url,
                                  max(0.0, self._unreachable_until - time.time())))
            return ""
        self._unreachable_until = 0.0

        payload = self._build_payload(prompt, system_prompt, max_tokens)
        if self.runtime == "ollama":
            url = f"{self.base_url.rstrip('/')}/api/generate"
        elif self.runtime in ("groq", "grok", "xai"):
            url = f"{self.base_url.rstrip('/')}/chat/completions"
        else:
            url = f"{self.base_url.rstrip('/')}/v1/chat/completions"

        last_err: Any = "unknown"
        for attempt in range(self.MAX_RETRIES):
            try:
                resp = requests.post(url, json=payload, headers=self._headers(),
                                     timeout=self.timeout)
                if resp.status_code in self.RETRYABLE_STATUS:
                    logger.warning("LLM transient HTTP %s (attempt %d/%d) - backing off",
                                   resp.status_code, attempt + 1, self.MAX_RETRIES)
                    self._sleep_for_retry(attempt, resp)
                    last_err = f"http_{resp.status_code}"
                    continue
                resp.raise_for_status()
                data = resp.json()
                if self._is_truncated(data):
                    logger.warning("LLM reply truncated by token limit "
                                   "(finish_reason=length)")
                self._available = True
                text_out = self._parse_response(data)
                if not (text_out or "").strip():
                    self.last_error = ("empty_response: %s returned no content for model %s"
                                       % (self.runtime, payload.get("model")))
                    logger.error("LLM call failed: %s", self.last_error)
                else:
                    self.last_error = ""
                return text_out
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status in (401, 403):
                    # Bad/expired/wrong-provider key. Deterministic - do not retry.
                    self._available = False
                    self._available_checked_at = time.time()
                    self.last_error = ("auth_failed(%s): %s rejected the API key at %s - %s"
                                       % (status, self.runtime, self.base_url,
                                          self._http_error_detail(e)))
                    logger.error("LLM call failed: %s", self.last_error)
                    return ""
                if status in (400, 404, 422):
                    # Retired/renamed model: re-resolve and retry once.
                    alt = self._recover_model()
                    if alt and alt != payload.get("model"):
                        payload["model"] = alt
                        try:
                            resp = requests.post(url, json=payload,
                                                 headers=self._headers(),
                                                 timeout=self.timeout)
                            resp.raise_for_status()
                            self._available = True
                            return self._parse_response(resp.json())
                        except Exception as e2:
                            logger.error("LLM retry with %r failed: %s", alt, e2)
                            last_err = str(e2)
                            continue
                if status in self.RETRYABLE_STATUS:
                    self._sleep_for_retry(attempt, getattr(e, "response", None))
                    last_err = str(e)
                    continue
                # Connection refused / DNS failure is DETERMINISTIC (the host is
                # not listening) - retrying only wastes seconds per call and
                # stalls every interview turn. Fail fast and mark unreachable.
                if self._is_unreachable_error(e):
                    logger.warning("LLM endpoint unreachable (%s) - failing fast", e)
                    self._available = False
                    self._unreachable_until = time.time() + self.UNREACHABLE_COOLDOWN
                    self.last_error = ("unreachable: %s refused the connection - %s"
                                       % (self.base_url, e))
                    return ""
                # Timeout: genuinely transient, retry a couple of times.
                if attempt < self.MAX_RETRIES - 1:
                    self._sleep_for_retry(attempt)
                    last_err = str(e)
                    continue
                logger.error("LLM generation failed: %s", e)
                last_err = str(e)
                break
        logger.error("LLM generation failed after %d attempt(s): %s",
                     self.MAX_RETRIES, last_err)
        self.last_error = "request_failed: %s (after %d attempt(s))" % (last_err,
                                                                       self.MAX_RETRIES)
        return ""

    @staticmethod
    def _http_error_detail(exc: Exception) -> str:
        """Short HTTP error description (status + body snippet) for diagnostics."""
        resp = getattr(exc, "response", None)
        if resp is None:
            return str(exc)
        body = (getattr(resp, "text", "") or "").strip().replace("\n", " ")[:200]
        return "HTTP %s %s" % (getattr(resp, "status_code", "?"), body)

    def status(self) -> Dict[str, Any]:
        """Diagnostics for this provider. Never exposes the API key itself."""
        return {
            "runtime": self.runtime,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "last_error": self.last_error,
        }

    def _is_truncated(self, resp_json: Dict[str, Any]) -> bool:
        choices = resp_json.get("choices") or []
        if choices:
            return choices[0].get("finish_reason") == "length"
        return bool(resp_json.get("done_reason") == "length")

    @staticmethod
    def _is_unreachable_error(exc: Exception) -> bool:
        """True when the failure means 'nothing is listening' (deterministic).

        ConnectionError covers ConnectionRefusedError, DNS resolution failure
        and 'NewConnectionError'. These never succeed on an immediate retry, so
        we must not sleep/retry - that is what made every turn slow.
        Timeouts (requests.Timeout) are excluded: those are genuinely
        transient and still get the backoff path.
        """
        connect_timeout = getattr(requests.exceptions, "ConnectTimeout", None)
        if connect_timeout is not None and isinstance(exc, connect_timeout):
            # The TCP connection was NEVER established (dead host, blackholed or
            # filtered port). Windows loopback to a closed port raises this
            # instead of ConnectionRefused, so it must count as unreachable -
            # otherwise every turn pays the full retry+backoff cost (~60s) before
            # falling back to deterministic questions.
            return True
        if isinstance(exc, requests.exceptions.Timeout):
            # ReadTimeout: the connection was established, the server is just
            # slow. Genuinely transient - keep the retry/backoff path.
            return False
        if isinstance(exc, requests.exceptions.ProxyError):
            return True
        if isinstance(exc, requests.exceptions.ConnectionError):
            return True
        text = str(exc).lower()
        return ("connection refused" in text or "newconnectionerror" in text
                or "name or service not known" in text
                or "temporary failure in name resolution" in text
                or "max retries exceeded" in text)

    def _sleep_for_retry(self, attempt: int, resp=None) -> None:
        """Exponential backoff, honouring Retry-After when the API sends it."""
        delay = min(2 ** attempt, 12)
        if resp is not None:
            try:
                ra = resp.headers.get("Retry-After")
                if ra:
                    delay = max(delay, min(float(ra), 25.0))
            except Exception:
                pass
        time.sleep(delay)

    def _recover_model(self) -> str:
        """Force model rediscovery after a model-level API error."""
        self._discovered_models = None
        try:
            live = self.discover_models()
        except Exception:
            live = []
        if not live:
            return self.model
        prefs = self._model_preferences.get(self.runtime, [])
        for p in prefs:
            if p in live and p != self.model:
                self.model = p
                return self.model
        if self.model not in live:
            self.model = live[0]
        return self.model

    def generate_json(self, prompt: str, system_prompt: str = "",
                      max_tokens: Optional[int] = None, **kwargs) -> Optional[Dict[str, Any]]:
        """Generate structured JSON from the LLM.

        Reasoning models can truncate the JSON mid-string when the token
        budget runs out. On a parse failure we retry once with a larger budget
        and an explicit "compact JSON" instruction rather than giving up and
        letting the caller fall back to static text.
        """
        attempts = [
            (max_tokens or self.JSON_TOKEN_BUDGET, ""),
            (max_tokens or self.JSON_TOKEN_BUDGET_RETRY,
             "\nKeep it COMPACT: at most 3 short items per list, no preamble, "
             "no explanation, close every string and brace."),
        ]
        saw_text = False
        for budget, extra in attempts:
            json_prompt = (prompt + extra +
                           "\n\nIMPORTANT: Output ONLY valid JSON, nothing else.")
            sys_prompt = system_prompt or ""
            sys_prompt = (sys_prompt + "\nOutput ONLY valid JSON. No explanations.").strip()
            result = self.generate(json_prompt, sys_prompt, budget, **kwargs)
            if not result or not result.strip():
                continue
            saw_text = True
            parsed = self._extract_json(result)
            if parsed is not None:
                return parsed
            logger.warning("LLM JSON unparseable (budget=%s); retrying with repair prompt", budget)
        if saw_text:
            # The model answered but not in the expected shape - say so, instead
            # of letting the caller silently present a fallback as LLM output.
            self.last_error = ("invalid_json: model replied but no JSON object could be "
                               "parsed (after %d attempt(s))" % len(attempts))
            logger.error("LLM JSON parsing failed: %s", self.last_error)
        return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from an LLM reply, tolerating code fences and preamble.

        Deterministic parsing only - it never rewrites model output, so a
        malformed reply still returns None and callers apply their own
        validation/repair rather than silently substituting static text.
        """
        if not text:
            return None
        cleaned = text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
        try:
            parsed = json.loads(cleaned)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse LLM JSON response: %s", e)
        # Fall back to the first balanced {...} object in the reply.
        start = cleaned.find("{")
        if start >= 0:
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(cleaned)):
                ch = cleaned[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            parsed = json.loads(cleaned[start:i + 1])
                            return parsed if isinstance(parsed, dict) else None
                        except json.JSONDecodeError:
                            return None
        return None

    def model_info(self) -> Dict[str, str]:
        return {"runtime": self.runtime, "model": self.model, "base_url": self.base_url}