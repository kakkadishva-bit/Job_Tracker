# Interview System Implementation

## Status: COMPLETE

## Files Created/Updated

| File | Status | Description |
|------|--------|-------------|
| `services/interview/__init__.py` | updated | Exports InterviewState, QuestionGenerator, InterviewContextBuilder, AnswerEvaluator |
| `services/interview/state.py` | created | InterviewState class tracking progress without relying on LLM memory |
| `services/interview/question_generator.py` | created | Adaptive question generation with JD-aware, resume-aware, RAG-backed logic |
| `services/interview/context_builder.py` | created | Builds compact interview context from resume, JD, RAG, and conversation history |
| `services/interview/answer_evaluator.py` | created | Structured scoring rubric for candidate answers |
| `services/llm/local_llm_provider.py` | created | Unified interface to local LLM runtimes (Ollama, llama.cpp, LM Studio) |
| `services/llm/__init__.py` | created | Exports LocalLLMProvider |
| `services/rag/pipeline.py` | fixed | Document, DocumentLoader, Chunker classes (was broken circular import) |
| `services/rag/__init__.py` | fixed | Proper exports with try/except for optional dependencies |
| `services/rag/rag_pipeline.py` | fixed | Correct FAISSRetriever API usage |
| `services/rag/rag_store.py` | fixed | Updated to use correct FAISSRetriever API |
| `services/rag/embeddings.py` | fixed | Fixed cache_dir attribute name |
| `services/rag/retriever.py` | fixed | Uses EmbeddingGenerator correctly |
| `app.py` | updated | Added adaptive interview endpoints |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/interview-prep/start` | POST | Start a new adaptive interview session |
| `/api/interview-prep/answer` | POST | Submit answer, get evaluation and next question |
| `/api/interview-prep/end` | POST | End interview, get summary |
| `/api/interview-prep` | POST | Backward-compatible static questions endpoint |

## Architecture

```
InterviewState (state.py)
    - Tracks: questions asked, skills covered, difficulty, scores
    - Adaptive: adjusts difficulty based on answer quality
    - Determines: should_continue() based on mode and performance

QuestionGenerator (question_generator.py)
    - Priority: resume claims > JD required > JD preferred > RAG > topic continuation
    - Uses: InterviewState for tracking, InterviewContextBuilder for context
    - Fallback: template-based questions when no context available

InterviewContextBuilder (context_builder.py)
    - Builds: resume section, JD section, state section, conversation section
    - Integrates: RAG retrieval when available
    - Limits: MAX_RECENT_TURNS = 10

AnswerEvaluator (answer_evaluator.py)
    - Scores: correctness, relevance, depth, clarity, practical_understanding, problem_solving
    - Signals: strong/weak keywords, technical terms, examples, trade-offs
    - Output: structured feedback with strengths, weaknesses, missing_topics

RAGPipeline (rag_pipeline.py)
    - Loads: knowledge documents from data/interview_knowledge/
    - Chunks: paragraphs with overlap
    - Embeds: with caching (sentence-transformers or zero-vector fallback)
    - Retrieves: FAISS or brute-force similarity
```