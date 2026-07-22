# GradeSense v2 — Agentic AI Educational Assessment Platform
## Architecture, Gap Analysis, and Development Roadmap

---

## 0. Where you're actually starting from

Your zip isn't a blank repo — it's a working prototype, and it's worth being honest about what it already proves vs. what the new spec asks for, so we don't throw away good work.

**What exists today (`app.py` + `src/`, Flask + JSON files):**

| Module | Lines | Maps to target agent | Current scope |
|---|---|---|---|
| `assignment_setup_agent.py` | 128 | Assignment Agent + Test Generation Agent (merged) | AI-suggests test cases from a description, verified against a reference solution before saving |
| `ingestion_agent.py` | 46 | part of Evaluation Agent | Discovers/validates submitted `.py` files |
| `execution_agent.py` | 56 | Evaluation Agent (programming path) | Subprocess isolation, timeout, wall-clock timing — Python only |
| `feedback_agent.py` | 107 | Feedback Agent | Per-student scoring + TA-voice feedback, LLM with offline fallback |
| `class_insight_agent.py` | 134 | Analytics Agent (partial) | Cross-batch misconception clustering |
| `similarity_agent.py` | 117 | Similarity Agent (partial) | AST-based structural similarity, adaptive threshold — no token or embedding similarity yet |
| `orchestrator.py` | 139 | Orchestrator Agent (seed) | Currently **sequential** — runs stages in fixed order, doesn't yet decide/skip/branch |
| `llm_client.py` | 48 | shared LLM utility | Groq wrapper w/ offline fallback — spec wants Gemini |
| `assignment_store.py` | 142 | DB layer | Plain JSON on disk, one assignment = one folder |

**Real, resume-relevant things already true about this codebase:** the agents are UI-agnostic (validated by having survived a Streamlit→Flask rewrite untouched), the rubric-as-test-suite design avoids drift, the similarity threshold is adaptive rather than hardcoded, and AI-generated test cases are verified by execution rather than trusted blindly. Keep all of that — it's good engineering and you should say so in interviews.

**What's genuinely missing relative to the new vision**, roughly in order of how disruptive the change is:

1. **No web framework/DB migration path** — Flask→FastAPI and JSON→PostgreSQL are both full rewrites of the persistence and API layer (not agent logic).
2. **No auth at all** — student "login" is a typed ID; there's no JWT, no roles, no teacher verification.
3. **One assignment type, one language** — everything assumes Python + function-signature programming problems. SQL/Theory/MCQ/Case-Study/Design and Java/C++/JS aren't touched anywhere in the pipeline.
4. **Orchestrator is sequential, not decision-making** — it always runs every stage in the same order; there's no branching on assignment type, no skip logic, no failure handling policy.
5. **No RAG, no vector DB, no Tutor Agent, no Memory Agent** — ChromaDB, embeddings, and conversational tutoring don't exist yet.
6. **Similarity is AST-only** — no token-level and no embedding-based similarity, so "multiple techniques" isn't met yet.
7. **No React frontend** — server-rendered Jinja templates today.

None of this means starting over. It means: **keep `src/` as the agent core, replace the two outer layers (persistence + web) first, then widen the agents' scope.** That ordering is what the roadmap below follows.

---

## 1. A few pushbacks / suggested amendments to the spec

Before locking the architecture, three places where I'd adjust what you wrote, because they affect a lot of downstream decisions:

**On Gemini vs. Groq.** Your spec says "Gemini API (or another free API if necessary)" — good, because Gemini's free tier has fairly low daily request caps, and this project calls an LLM from *at least* five agents (Assignment, Rubric, Evaluation-for-theory, Feedback, Tutor) plus RAG answer synthesis. I'd recommend abstracting the LLM behind one client interface (your existing `llm_client.py` already does this) with a swappable provider, and defaulting dev/demo mode to whichever provider gives you the most headroom for repeated testing — you can mention "provider-agnostic LLM client" as a design decision either way. Don't hardcode a single provider's SDK into agent logic.

**On "no Docker" + code execution security.** This is the single riskiest part of the spec. Without containers, true isolation of arbitrary student code (especially Java/C++, which compile to native execution) is hard to guarantee. What's realistic locally:
- Python: `subprocess.run(..., timeout=..., env=restricted_env)` + `resource.setrlimit` (CPU time, memory, file size, process count) on Linux/Mac, restricted `sys.path`/import allowlist via AST pre-scan to block `os`, `subprocess`, `socket`, `shutil`, etc. before execution.
- Java/C++: compile in a temp dir, run compiled artifact with the same `resource` limits + timeout, no network namespace available without containers so note this as a documented limitation, not a solved problem.
- I'd explicitly write a short "Security model & limitations" section in your README (you already do this well in the current one) — interviewers respect an honest threat model far more than a false claim of full sandboxing. This is also a great interview talking point on its own.

**On the Orchestrator "deciding" things.** To make this genuinely agentic rather than a dressed-up if/else, I'd model it as an explicit **state machine with a decision table**, not free-form LLM planning (LLM-planned orchestration is flakier and harder to demo reliably). Concretely: the Orchestrator holds a registry of agents with declared input/output contracts and preconditions; it walks a per-assignment-type **pipeline graph** (a small DAG defined per assignment type — Programming/SQL/Theory/MCQ each get their own graph), and it *does* make real decisions — e.g. skip the Similarity Agent if fewer than 2 submissions exist, skip the Tutor's RAG lookup if no documents were ingested for the course, retry the Execution Agent once on a transient compile-toolchain error before failing the submission, route Theory answers to LLM-rubric evaluation but MCQ straight to deterministic grading. That's honestly *more* impressive in an interview than an opaque "the LLM decided" black box, because you can explain and defend every branch.

---

## 2. Target Architecture

### 2.1 Tech stack (confirmed, with the one addition of a task queue)

| Layer | Choice | Notes |
|---|---|---|
| Backend | Python 3.11+, FastAPI | async-first, pydantic v2 for schema validation across every agent I/O boundary |
| Frontend | React + TailwindCSS | Vite, not CRA |
| DB | PostgreSQL | via SQLAlchemy 2.0 (async) + Alembic migrations |
| Auth | JWT (access + refresh) | `python-jose` or `pyjwt`, passlib for hashing |
| LLM | Gemini API, swappable | behind a `LLMClient` protocol, offline deterministic fallback preserved (this is one of the best parts of the current design — don't lose it) |
| Vector DB | ChromaDB | local persistent client, one collection per course |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | used for both RAG retrieval and Similarity Agent's embedding-based check |
| Background jobs | `arq` (Redis-backed) or FastAPI `BackgroundTasks` for v1 | grading a batch of submissions is exactly the kind of job that shouldn't block a request; start with `BackgroundTasks` to avoid adding Redis as a hard dependency, upgrade to `arq` in a later phase if queueing needs grow — flag this as a deliberate v1 simplification |
| Code execution | `subprocess` + `resource` limits, no Docker | documented limitation, see §1 |

### 2.2 Agent roster and contracts

Every agent gets a **pydantic input model, pydantic output model, and a single `run()` entrypoint** — this uniformity is what lets the Orchestrator treat them polymorphically instead of hardcoding per-agent calling conventions.

| Agent | Input | Output | Notes |
|---|---|---|---|
| **Orchestrator** | event (submission created / assignment created / question asked) | pipeline execution log | owns the decision table, described in §1 |
| **Assignment Agent** | teacher prompt + template + subject | title, description, difficulty, constraints, examples | evolved from `assignment_setup_agent.py` |
| **Test Generation Agent** | assignment description + reference solution (if programming) | public/hidden/edge test cases | split out of `assignment_setup_agent.py`; for non-programming types this generates MCQ distractors / SQL seed data instead |
| **Rubric Agent** | assignment type + subject | weighted criteria (correctness, efficiency, edge cases, readability, naming, docs) | new — currently the rubric is implicit in `test_cases.json` point values; formalize into its own table + agent so non-programming types (Theory, Design) have rubrics too |
| **Evaluation Agent** | submission + assignment type | raw execution/grading result | **type-routing dispatcher**: Programming → compile/run/compare (extends `execution_agent.py` to Java/C++/JS via a `LanguageRunner` interface), SQL → run against hidden schema + diff result sets, Theory/Design → LLM rubric scoring, MCQ → deterministic key match |
| **Feedback Agent** | raw result + rubric | strengths, weaknesses, failed cases, complexity notes, style suggestions, progressive hints, resources | extends `feedback_agent.py`; add explicit "never reveal full solution" constraint in prompt + a hint-ladder (hint 1 → 2 → 3, increasingly specific) |
| **Similarity Agent** | all submissions for an assignment | pairwise similarity report | extends `similarity_agent.py` with token similarity (difflib/shingling) and embedding cosine similarity alongside existing AST check; report which technique(s) flagged each pair |
| **Analytics Agent** | course/assignment scope | avg score, topic-wise performance, most-failed testcase, common mistakes, plagiarism stats | extends `class_insight_agent.py`, generalized beyond one assignment to course-level and topic-level aggregation |
| **Tutor Agent** | student question + submission/error context | answer (never full solution) | new — routes through Memory Agent for context, Retrieval Agent for RAG when relevant |
| **Retrieval Agent** | uploaded course documents | chunked + embedded documents in ChromaDB | new — ingestion pipeline: extract text → chunk (~500 tokens, overlap) → embed → upsert with metadata (course_id, source_file, page) |
| **Memory Agent** | agent/session id | short-term (current conversation, current submission) + long-term (recurring mistakes, past submissions, teacher preferences) | short-term = in-process/session cache; long-term = Postgres tables queried by other agents, not a separate store |

### 2.3 Orchestration flow (example: a programming submission)

```
Submission created
      │
      ▼
Orchestrator: look up assignment_type → load pipeline graph "programming"
      │
      ▼
Ingestion Agent  ──fail──▶ short-circuit: return "invalid submission" (skip everything else)
      │ ok
      ▼
Evaluation Agent (compile → run hidden+public tests → collect raw results)
      │
      ├──▶ Similarity Agent   (only if ≥2 submissions exist for this assignment)
      │
      ▼
Feedback Agent (raw results + Rubric) ──▶ Memory Agent (record recurring mistake if pattern seen before)
      │
      ▼
Analytics Agent (async, batched — doesn't block the student's response)
```

Theory/MCQ/SQL pipelines are the same shape with a different Evaluation Agent branch and, for MCQ, the Similarity Agent step is usually skipped (short-answer plagiarism on multiple choice isn't meaningful) — the Orchestrator's decision table is exactly where that gets encoded and is easy to demo/explain in an interview ("here's the pipeline graph for each assignment type, here's the actual code that picks between them").

### 2.4 Database schema (entities and relationships)

Normalized to 3NF. I'm giving you the entity/relationship shape here; I'll generate the actual SQLAlchemy models + Alembic migration when we implement the DB-layer phase, since that's a lot of boilerplate better done as real code than prose.

- **users** (id, email, hashed_password, role[student|teacher|admin], is_verified, created_at) — single table for auth, role-differentiated
- **students** (user_id FK→users, student_number) — 1:1 extension of users
- **teachers** (user_id FK→users, institution, verification_status[pending|approved|rejected]) — 1:1 extension of users
- **verification_requests** (id, teacher_id FK, submitted_email_domain, status, reviewed_by FK→users, reviewed_at)
- **courses** (id, name, subject_id FK, teacher_id FK→teachers)
- **subjects** (id, name) — DSA, OS, CN, DBMS, OOP, SE
- **assignments** (id, course_id FK, template_id FK, type[programming|sql|theory|mcq|case_study|design], title, description, difficulty, constraints_json)
- **assignment_templates** (id, name, assignment_type, default_fields_json)
- **rubrics** (id, assignment_id FK, criteria_json[{name, weight}])
- **test_cases** (id, assignment_id FK, kind[public|hidden|edge], input, expected_output, points)
- **submissions** (id, assignment_id FK, student_id FK, language, content, submitted_at)
- **execution_results** (id, submission_id FK, status, raw_output_json, runtime_ms)
- **feedback** (id, submission_id FK, score, breakdown_json, strengths, weaknesses, hints_json)
- **similarity_reports** (id, assignment_id FK, pair_a FK→submissions, pair_b FK→submissions, technique, score)
- **analytics_snapshots** (id, scope[assignment|course], scope_id, metrics_json, generated_at)
- **documents** (id, course_id FK, filename, uploaded_by FK→teachers) — source for Retrieval Agent; actual vectors live in ChromaDB, keyed by this table's id
- **conversations** / **tutor_messages** (id, student_id FK, submission_id FK nullable, role[user|tutor], content, created_at) — Memory Agent's long-term store
- **sessions** (id, user_id FK, refresh_token_hash, expires_at)

Key relationships: `users 1—1 students/teachers`, `teachers 1—N courses`, `courses 1—N assignments`, `assignments 1—N test_cases/1—1 rubric`, `students 1—N submissions`, `submissions 1—1 execution_results, 1—1 feedback`, `assignments 1—N similarity_reports`.

### 2.5 Auth & teacher verification

- JWT access (short-lived, ~15 min) + refresh (longer, stored hashed in `sessions`) tokens.
- Role-based dependency injection in FastAPI (`Depends(require_role("teacher"))`) rather than checking `request.user.role` ad hoc in every route.
- Teacher signup flow: register → email verification (token link) → if email domain matches an allowlist of institutional patterns (`.edu`, `.ac.in`, configurable list) auto-flag as "likely legitimate" but **still require admin approval** for the first version (simpler, no risk of false-accepting a spoofed domain) → admin approves/rejects from the Admin Dashboard → teacher gains access.

### 2.6 Folder structure

```
gradesense/
  backend/
    app/
      main.py                    FastAPI app factory
      core/
        config.py                 settings (pydantic-settings, .env)
        security.py                JWT, password hashing
        deps.py                    shared FastAPI dependencies (get_db, require_role)
      db/
        base.py                    SQLAlchemy declarative base
        session.py                  async session factory
        models/                     one file per entity group
        migrations/                  Alembic
      schemas/                     pydantic request/response models, one file per resource
      api/
        v1/
          auth.py, users.py, courses.py, assignments.py,
          submissions.py, feedback.py, analytics.py,
          tutor.py, documents.py, admin.py
      agents/
        base.py                    Agent protocol (run(), input/output pydantic models)
        orchestrator.py
        assignment_agent.py
        test_generation_agent.py
        rubric_agent.py
        evaluation/
          base_runner.py            LanguageRunner protocol
          python_runner.py, java_runner.py, cpp_runner.py, js_runner.py
          sql_runner.py, theory_evaluator.py, mcq_evaluator.py
        feedback_agent.py
        similarity_agent.py
        analytics_agent.py
        tutor_agent.py
        retrieval_agent.py
        memory_agent.py
        llm_client.py                provider-agnostic wrapper
      services/                    orchestration-adjacent business logic that isn't itself an "agent" (e.g. grading batch scheduling)
      execution_sandbox/            subprocess isolation, resource limits, import allowlists — one module, used by all LanguageRunners
    requirements.txt
    alembic.ini
    .env.example
  frontend/
    src/
      pages/                       Landing, Login, StudentDashboard, TeacherDashboard, AdminDashboard, AssignmentView, TutorChat
      components/
      api/                          typed fetch wrappers per backend resource
      hooks/
      context/                      auth context
    tailwind.config.js
    vite.config.js
  vector_store/                    ChromaDB persistent directory (gitignored)
  docs/
    ARCHITECTURE.md (this file)
    ROADMAP.md
  README.md
```

---

## 3. Development Roadmap (incremental, each phase runnable and demoable on its own)

Following your instruction not to build everything at once — each phase below is a shippable checkpoint, and later phases build cleanly on earlier ones without rewriting them.

| Phase | Deliverable | Builds on |
|---|---|---|
| **0** | FastAPI + Postgres + Alembic skeleton; port existing `src/` agents in as `agents/` modules **unchanged in logic**, just wrapped with pydantic I/O models | existing `src/` |
| **1** | Auth: JWT, roles, teacher registration + email verification + admin approval flow | 0 |
| **2** | Courses/Subjects/Assignment CRUD + Assignment Templates (Programming template only, to match current scope) | 1 |
| **3** | Rubric Agent formalized as its own table/agent (currently implicit in test case points) | 2 |
| **4** | Orchestrator v2: decision-table pipeline graph, still single assignment-type ("programming") to prove the pattern before widening | 2, 3 |
| **5** | Evaluation Agent generalized: `LanguageRunner` interface, add Java/C++/JS runners alongside Python | 4 |
| **6** | Assignment types widened: SQL, MCQ, Theory evaluation branches + their templates | 4, 5 |
| **7** | Similarity Agent: add token + embedding similarity alongside existing AST check | 0 |
| **8** | Analytics Agent generalized to course-level; Teacher/Admin analytics API endpoints | 6 |
| **9** | Retrieval Agent: document upload + chunk/embed/ingest into ChromaDB | 2 |
| **10** | Tutor Agent + Memory Agent (short-term + long-term), wired through Retrieval Agent for RAG | 9 |
| **11** | React frontend: auth pages + Student Dashboard + submission flow (parity with current Flask student portal first) | 1–6 |
| **12** | React: Teacher Dashboard (analytics, similarity review, feedback review) + Admin Dashboard (verification queue) | 8, 11 |
| **13** | React: Tutor chat UI | 10, 11 |
| **14** | Hardening pass: execution sandbox resource limits, rate limiting, structured logging, test suite (pytest) across agents and API | all |

I'd suggest we do Phase 0 next — it's the highest-leverage step (proves the whole new stack boots and talks to Postgres while reusing everything you've already built) and it's honest, visible progress you could screenshot for a resume/portfolio update immediately.
