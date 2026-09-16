# JobAgent - Architecture Plan (Hardware-Constrained)

> **Status:** Architecture plan (design only - no implementation yet)
> **Last updated:** 2026-09-10

## 1. Why This Plan Exists

The development machine has **limited resources**. Running large
LLMs continuously for every operation causes high CPU/GPU usage, heat,
and slow, janky performance.

**Hardware (development machine):**
- CPU: Intel Core i7-6820HQ @ 2.70 GHz (4 cores / 8 threads)
- RAM: 32 GB
- GPU: NVIDIA Quadro M2000M (4 GB) + Intel HD 530 (1 GB)
- OS: Windows

**Design rule:** JobAgent must **not** be built around an LLM for every
operation. The LLM is used only where it is genuinely necessary, and
small, quantized, CPU-friendly models replace it everywhere else.

## 2. Core Design Principle

| Operation | Must NOT do | Must do |
|---|---|---|
| Every page load | call an LLM | serve cached / static data |
| Every job match | call an LLM | embedding vectors + deterministic scoring |
| Every skill comparison | call an LLM | rules + taxonomy matching |
| Every database operation | call an LLM | plain ORM queries |
| Resume parsing | call an LLM | local document parser |
| Resume entity extraction | call an LLM for entities | local NER model |
| Skill extraction | call an LLM | NLP + skill taxonomy + rules/ML |
| ATS scoring | call an LLM | deterministic explainable scoring engine |
| Skill-gap analysis | call an LLM | rules + matching engine |
| Market-demand analysis | call an LLM | statistics from real job data |
| Recommendations | call an LLM every time | rules + ML with caching |
| Interview questions | rely on cloud LLM | local small/quantized LLM |
| Interview evaluation | full LLM evaluation | lightweight scoring + local LLM only where necessary |

## 3. Specialized Lightweight Component Stack

Each concern gets its own specialized, lightweight implementation.
No component depends on any other component's LLM.

| # | Function | Implementation | Runtime |
|---|----------|----------------|---------|
| 1 | Resume PDF/DOCX extraction | **Local document parser** - `pdfplumber` + `python-docx` + `PyPDF2` (already in requirements.txt) | Pure Python, CPU |
| 2 | Resume entity extraction | **Resume NER model** - spaCy (small CPU model) or GLiNER (tiny/quantized); fallback to regex for email/phone/LinkedIn/GitHub | Local model, CPU |
| 3 | Skill extraction & normalization | **NLP + skill taxonomy + rules/ML** - existing `SKILLS_DATABASE` regex matcher extended with synonym/alias normalization table; optional TF-IDF classifier | Pure Python, CPU |
| 4 | Resume <-> Job matching | **Sentence Transformer embeddings + deterministic scoring** - `all-MiniLM-L6-v2` (or ONNX-quantized MiniLM) using `sentence-transformers`; cosine similarity + weighted keyword bonus; embeddings cached in DB | Local model, CPU |
| 5 | ATS scoring | **Deterministic explainable scoring engine** - the existing weighted 10-category engine (no changes needed to the math) | Pure Python, CPU |
| 6 | Skill-gap analysis | **Rules + matching engine** - existing `LEARNING_RESOURCES` + set matching, extended with taxonomy-based normalization | Pure Python, CPU |
| 7 | Market-demand analysis | **Statistics calculated from real job data** - count/aggregate live listings from Adzuna/JSearch scrapes; salary stats (median, percentiles) from collected jobs; **no generative AI** | Pure Python, CPU |
| 8 | Recommendations | **Rules + ML where useful** - collaborative rules (matched skills/roles), stored embedding similarity precomputed in batches; results cached by user profile | Local model (batch) + rules |
| 9 | Interview question generation | **Local small/quantized LLM** - e.g. Qwen2.5-Instruct 1.5B/3B or Llama 3.2 1B/3B in Q4_K_M/Q8_0, via `LocalLLMProvider`; existing curated `INTERVIEW_QUESTIONS_DB` remains the offline primary source | Local LLM, CPU |
| 10 | Interview evaluation | **Lightweight scoring + local LLM only where necessary** - rubric-based keyword/coverage scoring first; only open-ended analysis calls the local LLM; results cached | Rules first, local LLM sparingly |
### Where LLM inference is ALLOWED
- Interview question generation (small quantized local LLM).
- Interview evaluation, only for open-ended free-text analysis, after
  rubric scoring, and only when a cached answer does not exist.
- Optional low-frequency "explain my result" generation.

### Where LLM inference is FORBIDDEN
- Page loads, job matching, skill comparisons, database operations,
  ATS scores, skill-gap computation, market-demand stats,
  recommendations, resume parsing.

## 4. Local LLM Runtime Abstraction

**Do not hard-code Ollama into the application.**

Backend code must go through an abstraction so the runtime can be
swapped. Supported backends:

- Ollama
- llama.cpp (llama-server, OpenAI-compatible endpoint)
- LM Studio (OpenAI-compatible endpoint)
- Jan (OpenAI-compatible endpoint)
- Any other OpenAI-compatible local endpoint

### Proposed interface (design only)

```python
# services/llm/provider.py  (planned)
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ChatResult:
    text: str
    model: str
    provider: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cached: bool = False

class LocalLLMProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], **kwargs) -> ChatResult: ...
    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> ChatResult: ...
    # optional for embedding-capable runtimes
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    def health(self) -> bool: ...
    @abstractmethod
    def model_info(self) -> dict: ...
    @abstractmethod
    def metrics(self) -> dict: ...   # tokens/sec, latency, last call time

# factory (planned) in services/llm/factory.py
# def get_provider(name: str | None = None) -> LocalLLMProvider:
#     """name in {ollama, llama_cpp, lm_studio, jan, openai_compatible}.
#     Default from settings.LOCAL_LLM_PROVIDER. Caches the singleton."""
```

All runtime-specific code lives behind this interface. Flask routes,
the ATS engine, matchers and scrapers import only the interface -
never a provider SDK directly.

### Separable inference server (future)
The provider interface is HTTP-shaped so inference can move to a
separate server: point `LOCAL_LLM_BASE_URL` at any host serving an
OpenAI-compatible or Ollama endpoint. For many simultaneous users, run
web/worker boxes that proxy to a dedicated LLM node - no JobAgent code
changes required.
## 5. Configuration (planned)

Environment variables / `config.py` additions:

| Setting | Example | Purpose |
|---|---|---|
| `LOCAL_LLM_PROVIDER` | `ollama` / `llama_cpp` / `lm_studio` / `jan` / `openai_compatible` | Runtime selection |
| `LOCAL_LLM_BASE_URL` | `http://127.0.0.1:11434` | Server endpoint |
| `LOCAL_LLM_MODEL` | `qwen2.5:3b-q8_0` | Model tag / path |
| `LOCAL_LLM_QUANT` | `Q8_0` / `Q4_K_M` | Quantization level |
| `LOCAL_LLM_MAX_TOKENS` | `512` | Output cap |
| `LOCAL_LLM_TIMEOUT` | `30` | Request timeout (s) |
| `LOCAL_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `LOCAL_EMBEDDING_DEVICE` | `cpu` | Inference device |
| `CACHE_RESUME_ANALYSIS_DB` | `true` | DB caching on/off |
| `CACHE_JOB_ANALYSIS_DB` | `true` | DB caching on/off |

## 6. Caching Strategy (avoid repeated inference)

Three layers, in order of first lookup:

1. **In-memory cache** (`cachetools.TTLCache`) - hot results,
   per-process, e.g. embeddings for the same resume text within a
   session.
2. **Database cache tables** (SQLAlchemy models, planned in
   `models/analysis_cache.py`):

```python
class ResumeAnalysisCache(db.Model):  # one row per (resume_text_hash, target_role)
    id, resume_text_hash (indexed), target_role, ats_score,
    entities_json, skills_json, embeddings_json, provider,
    model, created_at, expires_at

class JobAnalysisCache(db.Model):     # one row per job_url/job_hash
    id, job_url_hash (indexed), job_embeddings_json,
    requirements_json, matched_roles_json, model_used,
    created_at, expires_at

class EmbeddingCache(db.Model):       # text -> vector reused across features
    id, text_hash (unique, indexed), model_name, vector_json, created_at
```

3. **Precomputed batch results** - nightly/batch jobs pre-embed the job
   corpus and pre-score popular role/resume pairs; the web layer reads
   prepared rows instead of running inference.

Rules:
- Never run the same inference twice for identical input; always key on
  a content hash (`sha256` of normalized text).
- TTL defaults: resume analysis 24 h, job analysis 7 d, embeddings
  unlimited until model version changes.
- A model-version column must invalidate caches when the model changes.

## 7. Batch & Asynchronous Processing

- **Batch processing:** resume NER, skill extraction and embedding
  runs operate over queues of documents in batches (e.g. re-analyze new
  jobs nightly, re-embed corpus weekly), not per request.
- **Asynchronous where appropriate:** Flask routes return quickly and
  delegate heavy work:
  - Long resume analysis -> `asyncio`/background worker sends a
    "processing" status and the client polls / is notified when ready.
  - Market-demand stats -> computed from the cached job corpus,
    refreshed by a scheduled batch, never computed inside a request
    with fresh model calls.
- **Worker options (planned):** stdlib `asyncio` + a small in-process
  task queue for dev; `RQ`/`Celery` allowed, but not required on the
  constrained machine - prefer serial batch scripts run at off-peak
  times.
## 8. Benchmarking Protocol (choose runtime AFTER measuring)

**Do not choose a replacement runtime yet.** Benchmark on the actual
development machine, then decide. Results recorded per run in
`docs/BENCHMARKS.md`.

Metrics to capture per candidate runtime:

| Metric | Tool | Stop condition |
|---|---|---|
| Tokens/sec (generation) | runtime stdout + `metrics()` | - |
| First-token latency (ms) | stopwatch | - |
| Peak RAM (MB) | Task Manager / `psutil` | keep < ~8 GB headroom |
| CPU % during inference | Task Manager | keep sustained < 60% |
| GPU usage / VRAM (MB) | `nvidia-smi` | keep < 3 GB on Quadro M2000M |
| Package / device temp (deg C) | OpenHardwareMonitor / sensors | keep < 85 deg C |

Candidates to include in the benchmark matrix:

| Runtime | Endpoint style | Notes |
|---|---|---|
| Ollama | native + OpenAI-compat | easiest dev loop |
| llama.cpp `llama-server` | OpenAI-compatible | most CPU-efficient GGUF runner |
| LM Studio | OpenAI-compatible | GUI-friendly local server |
| Jan | OpenAI-compatible | desktop app alternative |

Candidate small models to benchmark (quantized GGUF or Ollama tags):

| Model | Size | Quant | Why |
|---|---|---|---|
| Qwen2.5-Instruct 1.5B | ~1.5B | Q8_0 | smallest adequate text gen |
| Qwen2.5-Instruct 3B | 3B | Q4_K_M/Q8_0 | better quality, still CPU-safe |
| Llama 3.2 1B | 1B | Q8_0 | tiny, fast |
| Llama 3.2 3B | 3B | Q4_K_M | balanced |
| Phi-3-mini | 3.8B | Q4_K_M | good instruction following |

Embedding model candidates: `all-MiniLM-L6-v2` (~22 MB, CPU-fast),
ONNX-quantized MiniLM-L12 (4-bit).

Decision thresholds before adoption:
1. Interview question generation for one role answers in < 5 s on CPU.
2. Peak RAM < 8 GB for model server + app combined.
3. Sustained CPU < 60% during a 10-consecutive-requests test.
4. Temp stays < 85 deg C under load, < 70 deg C idle.
5. If no runtime meets thresholds, fall back to curated local content
   (`INTERVIEW_QUESTIONS_DB`) 100% of the time - no local LLM.

## 9. Migration Path (replaceable later)

1. Ship dependency-free features first: parsers, NER, matching,
   scoring, skill-gap, market stats, recommendations - all offline.
2. Add `LocalLLMProvider` + factory + benchmark; choose runtime; set
   `LOCAL_LLM_PROVIDER` config.
3. Interview generation + evaluation read only the provider interface;
   never use provider-specific imports outside `services/llm/`.
4. Later, on bigger hardware or a dedicated inference server: change
   `LOCAL_LLM_BASE_URL` only - no other code changes.

## 10. Architecture Diagram

```
Browser (JS SPA) --> Flask REST API (app.py)
                        |
        +---------------+----------------------------+
        |               |                             |
   Resume parse    Analysis engines               Auth / Chat
 (pdfplumber /     |  ATS scoring                (SQLAlchemy)
  python-docx /    |  skill-gap rules                  |
  PyPDF2)          |  market stats                     v
        |          |  recommendations        PostgreSQL /
        v          v                        SQLite (dev)
 Local NER     DB Cache tables
 (spaCy/       resume_analysis_cache,
  GLiNER)      job_analysis_cache,
        |      embedding_cache
 Embeddings
 (MiniLM-L6)    |
        |       v
 Matcher: cosine similarity + deterministic scoring
        |
        v
 LocalLLMProvider (interface)
   |-- Ollama              |-- llama.cpp (llama-server)
   |-- LM Studio / Jan     |-- any OpenAI-compatible endpoint
```

## 11. Acceptance Criteria

- [ ] No LLM call on page load, job match, skill comparison, or DB op.
- [ ] 100% offline functionality except optional live job data feeds.
- [ ] All model inference goes through `LocalLLMProvider`.
- [ ] Quantized / CPU-only models by default on the dev machine.
- [ ] Resume entities, skills, embeddings and job analysis cached in DB.
- [ ] Same input never runs inference twice (hash-keyed caches).
- [ ] Batch/async jobs handle NER, embeddings, market stats.
- [ ] Runtime configurable: `LOCAL_LLM_PROVIDER` + `LOCAL_LLM_BASE_URL`.
- [ ] Benchmark report decides runtime; nothing hard-coded.