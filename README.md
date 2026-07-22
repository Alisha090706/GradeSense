# GradeSense

GradeSense is an AI-assisted grading and tutoring platform for programming
courses. Teachers create assignments — programming exercises (Python, Java,
C++, JavaScript), SQL queries, multiple-choice quizzes, or free-text theory
questions — and students submit work that is graded automatically, with
AI-generated feedback, plagiarism detection, and a tutor chatbot that helps
students understand *their own* results without ever handing them the
answer.

The system is built as a set of small, single-purpose **AI agents**
orchestrated behind a typed pipeline, rather than one large prompt doing
everything. That architecture is the core of what makes GradeSense
interesting, so this README leads with it.

---

## Why agentic, not "one big LLM call"

A single LLM prompt asked to "grade this code and give feedback" is fast to
build and impossible to trust: it can hallucinate a test result, miss an
edge case, or simply be wrong about whether code compiles. GradeSense
instead splits grading into a **pipeline of narrow agents**, each with one
job, typed inputs/outputs, and — critically — a clear boundary between
*what an LLM proposes* and *what gets independently verified*.

```
Submission
   │
   ▼
Orchestrator  ──▶  per-assignment-type pipeline (a small decision table,
   │                not one fixed sequence — each step declares its own
   │                skip condition, e.g. "skip similarity for a 3-line answer")
   ▼
Evaluation Agent ──▶ language-specific runner (Python / Java / C++ / JS)
   │                 or SQL / MCQ / Theory evaluator
   ▼
Similarity Agent(s) ──▶ AST + token-shingling + embedding-cosine plagiarism checks
   ▼
Feedback Agent ──▶ turns raw pass/fail + rubric into human-readable feedback
   ▼
Rubric / Analytics / Class-Insight Agents ──▶ scoring criteria & class-wide patterns
```

Every agent implements the same interface (`Agent[InputT, OutputT]`) —
plain pydantic models in, plain pydantic models out, no hidden DB or
network access inside the agent itself. That makes each one independently
testable and swappable, and makes the orchestrator's job purely "call the
right agents in the right order for this assignment type."

### LLM-backed agents, with a real offline mode

Several agents call an LLM (Google Gemini or Groq, provider-agnostic behind
one `llm_client`); others are pure deterministic computation. The ones that
use an LLM are designed so the platform never *silently* depends on one:

| Agent | Uses an LLM for | Falls back to, if no API key is configured |
|---|---|---|
| **Assignment Setup Agent** | Proposing test cases from a reference solution | Nothing — this one is always execution-verified, see below |
| **Rubric Agent** | Customizing grading-criteria weights per assignment | A sensible type-specific default rubric |
| **Feedback Agent** | Turning results into readable, encouraging feedback | A deterministic template built from the same scores |
| **Theory Evaluation Agent** | Grading free-text answers against a rubric | Honestly marks the submission "needs manual review" — there's no safe heuristic substitute for grading prose, so it doesn't pretend to have one |
| **Class Insight / Analytics Agents** | Summarizing shared misconceptions across a class | Raw aggregate statistics, no narrative |
| **Tutor Agent** | Holding a conversational Q&A about a student's own submission | Deterministic answers pulled straight from that submission's real test results (e.g. "test case 4 failed because...") |

This means GradeSense is fully demoable and gradeable with **zero API
keys** — LLM features add polish and depth, they aren't load-bearing for
core grading to function.

### Never trust the LLM's answer — verify by execution

The one place an LLM's output is never taken at face value: **test-case
generation**. When a teacher pastes a reference solution, the Assignment
Setup Agent asks an LLM to *propose* test cases (typical inputs, edge
cases, cases that should raise exceptions) — then those proposals are
thrown away and regenerated for real:

- The reference solution is actually **compiled and executed** (Python via
  a sandboxed subprocess; Java via a full `javac` → JVM → method-invocation
  pipeline) against each proposed input.
- Whatever the code *actually* returns — or *actually* throws — replaces
  the LLM's guess before anything is saved.
- Reference solutions are also statically checked and rejected if they
  contain unsafe top-level code (a stray `input()` call, for example)
  before execution is even attempted, and every execution runs under a
  wall-clock timeout and resource limits so a bad submission can never
  hang the grading pipeline.

The same principle extends to student submissions: every language runner
(Python, Java, C++, JavaScript) executes real code in an isolated
subprocess with CPU/memory/output limits, diffs the actual output against
the verified expected value, and reports pass/fail per test case — not an
LLM's opinion about whether the code "looks correct."

### Retrieval-augmented tutoring, with a hard safety boundary

Teachers can upload course documents (PDF, Markdown, plain text). An
ingestion pipeline extracts text, chunks it, embeds it, and stores it in a
per-course vector store (ChromaDB). The Tutor Agent retrieves relevant
chunks to ground its answers in the actual course material — a small RAG
system, not a general-purpose chatbot.

The Tutor has one rule enforced both in its system prompt *and*
structurally in code: it can explain, hint, and point to a student's own
failing test cases, but it can never reveal a complete solution or expected
test values it wasn't explicitly given access to. The offline (no-LLM)
fallback path physically cannot leak a solution, because it only ever
echoes back facts already visible in the student's own execution results.

### Memory, without over-engineering a memory store

Rather than bolting on a vector-based "memory" system, GradeSense keeps
memory as simple as the data already implies:
- **Short-term** — the recent conversation thread, fetched directly from
  stored tutor messages.
- **Long-term** — recurring-mistake detection computed across a student's
  past submissions, so the tutor can notice patterns ("you've hit an
  off-by-one error in three separate assignments") instead of treating
  every conversation as if it started from zero.

### Plagiarism detection, three ways

One technique alone misses too much, so similarity checking runs three
independent methods and reports each separately rather than collapsing
them into one opaque score:

1. **AST comparison** — strips identifiers/literals, catches
   logically-identical code with every variable renamed.
2. **Token shingling** — raw-text comparison, catches literal copy-paste
   that AST comparison's structural focus can miss.
3. **Embedding cosine similarity** — semantic comparison via
   sentence-transformers, catches paraphrased/restructured copies neither
   of the above would flag.

---

## What the platform actually does, end to end

**For teachers:** create courses and assignments across four types
(Programming, SQL, MCQ, Theory/free-text), get AI-assisted or manual
rubric authoring, generate and verify test cases from a reference
solution, upload course material for the tutor to draw on, review
plagiarism-flagged submission pairs, and see class-wide and per-assignment
analytics (score distributions, most-failed test cases, common
misconceptions).

**For students:** submit work in the language of their choice where
applicable, get an instant execution-verified grade with a category-level
breakdown (not just a single number), receive readable AI-generated
feedback, and chat with a tutor that's grounded in their own results and
the course's uploaded material — never a shortcut to the answer.

**Assignment types supported:**
- **Programming** — Python, Java, C++, JavaScript, each with a real
  sandboxed compile/execute pipeline.
- **SQL** — submitted queries run against a hidden schema (read-only,
  validated `SELECT`-only) and diffed against expected result sets.
- **MCQ** — multiple questions per assignment, single- or multi-select,
  graded by exact key match with a per-question breakdown.
- **Theory** — free-text answers graded against a rubric by an LLM, with
  an honest "needs manual review" state when no LLM is configured.

**Platform mechanics:** JWT authentication with role-based access
(student / teacher / admin), a teacher-verification approval workflow so
only vetted instructors can create courses, rate limiting on
authentication endpoints, and structured JSON logging.

---

## Tech stack

- **Backend:** FastAPI (async), SQLAlchemy + Alembic, PostgreSQL
- **Agents:** plain Python + Pydantic, provider-agnostic LLM client
  (Google Gemini / Groq), sentence-transformers for embeddings, ChromaDB
  for vector storage
- **Execution sandbox:** subprocess isolation with CPU/memory/output
  limits per language runner (Python, Java via JDK, C++ via g++,
  JavaScript via Node)
- **Frontend:** React + Vite, Tailwind
- **Testing:** pytest, with the Java/C++ runner tests skipping cleanly
  (not failing) when the corresponding compiler isn't on `PATH`

## Project structure

```
backend/
  app/
    agents/            # every agent described above, one file per agent
      evaluation/       # per-language execution runners (Python/Java/C++/JS)
    api/v1/             # FastAPI routes
    services/           # DB-aware orchestration between routes and agents
    db/models/          # SQLAlchemy models
    core/               # config, security, rate limiting, logging
  migrations/           # Alembic
  scripts/              # seed data, admin bootstrap
  tests/                # pytest suite
frontend/
  src/
    pages/              # student / teacher / admin views
    api/                # typed fetch wrappers per resource
    components/         # shared UI
```

## Running it locally

### Prerequisites
- Python 3.12+, Node.js 18+, PostgreSQL 14+
- A JDK on `PATH` if you want Java-language assignments/submissions to work
  (everything else runs without one)

### Backend

```bash
psql -c "CREATE USER gradesense WITH PASSWORD 'gradesense' SUPERUSER;"
psql -c "CREATE DATABASE gradesense OWNER gradesense;"

cd backend
pip install -r requirements.txt

cat > .env <<'EOF'
DATABASE_URL=postgresql+asyncpg://gradesense:gradesense@localhost:5432/gradesense
DATABASE_URL_SYNC=postgresql+psycopg2://gradesense:gradesense@localhost:5432/gradesense
JWT_SECRET_KEY=some-random-secret
DEBUG=true

# Optional: auto-creates this admin account at startup (dev only) so there's
# a way to approve teacher accounts without a separate manual script.
DEFAULT_ADMIN_EMAIL=admin@gradesense.io
DEFAULT_ADMIN_PASSWORD=AdminPass123!

# Optional: enables the LLM-backed agents' full behavior (see table above).
# Everything runs without these — just in offline-fallback mode.
GEMINI_API_KEY=
GROQ_API_KEY=
EOF

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Subjects and assignment templates seed automatically on startup. API docs
at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
echo "VITE_API_BASE=http://localhost:8000/api/v1" > .env
npm run dev
```

Opens at `http://localhost:5173`.

### Tests

```bash
cd backend
pytest -v
```

Language-runner tests for compilers not present on the machine (e.g. no
JDK) skip cleanly rather than failing.
