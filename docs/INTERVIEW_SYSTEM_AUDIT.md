# Interview System Audit

## Overview

The adaptive AI interview system (Step 4) is a resume-aware, JD-aware, conversation-memory-enabled, RAG-backed interview flow that behaves like a real human interviewer.

## Status: COMPLETE

## Design Principles

1. **No static question dump** - Questions are generated adaptively based on context
2. **No single-message input** - Multi-turn conversation with memory
3. **No random/repeated questions** - InterviewState tracks what has been asked
4. **Resume + JD + Conversation Memory + RAG** - All sources used for question generation
5. **Local-only interview generation** - No cloud LLM dependency for core flow

## Components

### 1. InterviewState (`services/interview/state.py`)

Tracks interview progress without relying on LLM memory.

**Key features:**
- Tracks questions asked, question types, topics covered, skills covered
- Tracks strong/weak areas, answer scores
- Adaptive difficulty: increases on good answers (>=75), decreases on poor (<50)
- Configurable modes: quick (5-10 questions), standard (15-25), deep (30-50)
- Determines when interview should continue based on mode and performance

**Key methods:**
- `record_question(question, q_type, skill)` - Record a question was asked
- `record_answer(evaluation)` - Record answer evaluation, adjust difficulty
- `should_continue()` - Determine if interview should continue
- `finalize()` - End interview, compute overall score

### 2. QuestionGenerator (`services/interview/question_generator.py`)

Generates adaptive interview questions based on context.

**Question selection priority:**
1. Resume claims (strong skills from resume)
2. JD required skills (from job description)
3. JD preferred skills (from job description)
4. RAG results (from knowledge base)
5. Topic continuation (follow-up on current topic)
6. Fallback (generic questions)

**Key methods:**
- `get_first_question(state, resume_context, job_context)` - Get opening question
- `get_next_question(state, resume_context, job_context, conversation, rag_results)` - Get next adaptive question

### 3. InterviewContextBuilder (`services/interview/context_builder.py`)

Builds compact LLM context from resume, JD, RAG, and conversation history.

**Context sections:**
- Resume context (profile, skills, experience, projects)
- Job context (title, required skills, description)
- Interview state (current topic, skill, difficulty, turn)
- Recent conversation (last 10 turns)
- RAG context (retrieved knowledge chunks)

### 4. AnswerEvaluator (`services/interview/answer_evaluator.py`)

Evaluates candidate answers using structured scoring rubric.

**Scoring dimensions (0-100):**
- Correctness - Technical accuracy
- Relevance - How relevant to the question
- Depth - Depth of explanation
- Clarity - Structure and clarity of response
- Practical understanding - Concrete examples and implementation knowledge
- Problem solving - Problem-solving approach

**Signal detection:**
- Strong signals: "specifically", "example", "trade-off", "optimized", "production"
- Weak signals: "um", "uh", "like", "i think", "maybe"
- Technical indicators: domain-specific terminology
- Examples: "for example", "such as", "e.g."
- Trade-offs: "trade-off", "versus", "vs"

**Output:**
- Overall score (composite of dimensions)
- Strengths list
- Weaknesses list
- Missing topics
- Follow-up recommendation

### 5. LocalLLMProvider (`services/llm/local_llm_provider.py`)

Unified interface to local LLM runtimes.

**Supported runtimes:**
- Ollama (default: http://localhost:11434)
- llama.cpp server (http://localhost:8080)
- LM Studio (http://localhost:1234)
- Jan (http://localhost:1313)

**Key features:**
- Runtime-specific payload building
- Runtime-specific response parsing
- Health check
- JSON generation mode
- No cloud dependency

### 6. RAG Pipeline (`services/rag/`)

Retrieval-Augmented Generation pipeline for knowledge-backed interviews.

**Components:**
- `pipeline.py` - Document, DocumentLoader, Chunker
- `embeddings.py` - EmbeddingGenerator with cache
- `retriever.py` - FAISS-based retriever with brute-force fallback
- `rag_pipeline.py` - End-to-end pipeline
- `rag_store.py` - Persistent storage

**Features:**
- Lazy loading of knowledge base
- File-based embedding caching
- FAISS or brute-force similarity search
- Graceful degradation without sentence-transformers

## API Endpoints

### POST /api/interview-prep/start

Start a new adaptive interview session.

**Request:**
```json
{
  "role": "Python Developer",
  "company": "Tech Corp",
  "interview_mode": "standard",
  "experience_level": "mid",
  "resume_context": {},
  "job_context": {},
  "required_skills": ["Python", "FastAPI"],
  "preferred_skills": ["Docker", "AWS"]
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "role": "Python Developer",
  "question": {"question": "...", "type": "behavioral", "skill": "general", "source": "introduction"},
  "turn": 0,
  "status": "active"
}
```

### POST /api/interview-prep/answer

Submit an answer and get the next adaptive question.

**Request:**
```json
{"session_id": "uuid", "answer": "My experience with Python includes..."}
```

**Response:**
```json
{
  "session_id": "uuid",
  "evaluation": {"overall_score": 75, "correctness": 80, "relevance": 90},
  "next_question": {"question": "...", "type": "technical", "skill": "python", "source": "required_jd"},
  "turn": 1,
  "status": "active",
  "should_continue": true,
  "overall_score": 75.0
}
```

### POST /api/interview-prep/end

End the interview session and get summary.

**Response:**
```json
{
  "status": "completed",
  "summary": {
    "target_role": "Python Developer",
    "questions_asked": 15,
    "overall_score": 78.5,
    "skills_covered": ["python", "fastapi", "docker"],
    "required_skills_tested": ["Python", "FastAPI"],
    "weak_areas": ["kubernetes"],
    "strong_areas": ["python", "fastapi"]
  }
}
```

### POST /api/interview-prep (backward-compatible)

Returns static questions for a role (original endpoint).

## Testing

- 26 resume extraction tests pass (Step 2)
- 10 tests skipped (optional dependencies: pdfplumber, python-docx)
- 1 test deselected (capabilities_report requires pdfplumber)

## Dependencies

**Required:** Flask, flask-login, numpy

**Optional (graceful degradation):**
- sentence-transformers (embeddings, falls back to zero vectors)
- faiss-cpu/faiss-gpu (similarity search, falls back to brute-force)
- requests (LLM provider)
- pdfplumber, python-docx (resume parsing)

## Future Enhancements

- Add more question templates for additional skills
- Integrate with actual LLM for dynamic question generation
- Add support for system design questions
- Add support for coding challenges
- Persist interview sessions to database
- Add interview history and analytics dashboard