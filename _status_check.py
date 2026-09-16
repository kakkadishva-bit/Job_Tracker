"""Quick live health check: is the LLM provider and the RAG pipeline actually alive?

Answers, without guessing: which LLM provider will actually be called, whether
the key matches the provider, whether RAG embeddings loaded, how many chunks are
indexed, which retrieval backend runs, and how many hits a real query returns.
Run:  python _status_check.py
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()  # app.py does this; without it .env keys are invisible

print("=" * 90)
print("ENVIRONMENT")
print("=" * 90)
for name in ("LLM_RUNTIME", "LLM_MODEL", "LLM_BASE_URL", "LLM_TIMEOUT",
             "GROK_MODEL"):
    print("  %-14s = %r" % (name, os.environ.get(name, "")))
for name in ("GROK_API_KEY", "XAI_API_KEY", "GROQ_API_KEY"):
    val = (os.environ.get(name, "") or "").strip()
    shape = "-"
    if val:
        if val.startswith("gsk_"):
            shape = "gsk_ (Groq, api.groq.com)"
        elif val.startswith("xai-"):
            shape = "xai- (xAI Grok, api.x.ai)"
        else:
            shape = "unrecognised prefix"
    print("  %-14s present=%-5s shape=%s" % (name, bool(val), shape))

from services.llm.grok_provider import get_interview_llm, llm_config_status
print("\nLLM CONFIG STATUS")
print(json.dumps(llm_config_status(), indent=2))

provider = get_interview_llm()
print("\nSELECTED PROVIDER: %s" % type(provider).__name__)
for attr in ("model", "base_url", "runtime", "available", "last_error"):
    if hasattr(provider, attr):
        print("  %-11s = %r" % (attr, getattr(provider, attr)))

print("\nLIVE LLM CALL (one short prompt, real network)")
try:
    raw = provider.generate("Reply with exactly the JSON {\"ok\": true} and nothing else.")
    print("  raw reply : %r" % (str(raw)[:300],))
    print("  last_error: %r" % (getattr(provider, "last_error", ""),))
except Exception as exc:
    print("  EXCEPTION %s: %s" % (type(exc).__name__, exc))

print("\n" + "=" * 90)
print("RAG STATUS")
print("=" * 90)
from services.rag import get_rag, last_rag_error

rag = get_rag()
if not rag:
    print(json.dumps({"available": False, "last_error": last_rag_error()}, indent=2))
else:
    print(json.dumps(rag.get_status(), indent=2))
    for query in ("How should documents be chunked for a RAG pipeline?",
                  "How do you evaluate a retrieval augmented generation system?"):
        hits = rag.retrieve(query)
        print("\n  QUERY %r -> %d hits" % (query, len(hits)))
        for h in hits[:3]:
            print("    score=%.4f %s" % (h["score"],
                                         str(h["content"])[:110].replace("\n", " ")))
        print("    pipeline.last_error=%r" % (rag.last_error,))