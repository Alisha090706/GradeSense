"""
SQL Evaluation Agent — executes a submitted query against a hidden schema
and diffs the result set against expected rows.

Security note, stated plainly: submitted queries are validated as
SELECT-only (see `_validate_select_only` — no DDL/DML keywords, no
multiple statements) before ever touching sqlite3, since this assignment
type is "write a query to retrieve data," not "modify a database." That
check is necessary but not sufficient — there is deliberately no
wall-clock timeout on the query itself (unlike every LanguageRunner in
evaluation/, which run in a subprocess and can be killed on timeout; this
runs in-process via Python's stdlib sqlite3). A pathological recursive CTE
could still hang the request. Flagged here as an accepted MVP limitation
rather than hidden — production hardening would move this to a subprocess
with the same timeout treatment every other runner already gets.

Schema/seed data live on Assignment.constraints (teacher-authored, trusted,
run unvalidated) — e.g. {"schema_sql": "CREATE TABLE ...", "seed_sql":
"INSERT INTO ..."}. Expected results live on TestCase rows, reusing the
existing input/expected_output JSONB shape: expected_output =
{"rows": [[1, "Alice", 90], ...]}.

Deliberately reuses ExecutionOutput (agents/evaluation/schemas.py) as its
output shape — identical to what every LanguageRunner produces — so the
existing FeedbackAgent (Python-specific wording aside, its scoring logic
is language-agnostic) can score and narrate SQL results without any
changes. This agent never returns status="crash": a totally invalid query
still returns status="ok" with every test case individually failed and a
SQL-specific error message, sidestepping FeedbackAgent's crash-path
message (written with Python files in mind) entirely rather than
patching around a mismatch.
"""
import re
import sqlite3

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents.evaluation.schemas import ExecutionOutput

_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(ATTACH|DETACH|PRAGMA|DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|REPLACE|VACUUM|REINDEX)\b",
    re.IGNORECASE,
)


def validate_select_only(query: str) -> str | None:
    """Returns an error message string if the query isn't allowed, else None."""
    stripped = query.strip()
    body = stripped.rstrip(";").strip()
    if ";" in body:
        return "Only a single statement is allowed (no semicolons)."
    if not re.match(r"^\s*(SELECT|WITH)\b", body, re.IGNORECASE):
        return "Only SELECT (or WITH ... SELECT) statements are allowed."
    if _FORBIDDEN_KEYWORDS.search(body):
        return "Query contains a disallowed keyword — only reading data is permitted for this assignment type."
    return None


def _run_query(schema_sql: str, seed_sql: str, query: str) -> tuple[list[tuple], str | None]:
    """Runs schema+seed (trusted) then the submitted query on a fresh in-memory DB.
    Returns (rows, error_message)."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(schema_sql)
        if seed_sql:
            conn.executescript(seed_sql)
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        return rows, None
    except sqlite3.Error as e:
        return [], f"{type(e).__name__}: {e}"
    finally:
        conn.close()


def _rows_match(actual: list[tuple], expected: list, order_matters: bool) -> bool:
    actual_norm = [tuple(row) for row in actual]
    expected_norm = [tuple(row) for row in expected]
    if order_matters:
        return actual_norm == expected_norm
    return sorted(map(str, actual_norm)) == sorted(map(str, expected_norm))


class SqlTestCase(BaseModel):
    id: str
    category: str = "query_correctness"
    expected_rows: list[list]
    points: float = 1
    seed_sql_override: str | None = None  # optional per-test-case seed data variant


class SqlEvaluationInput(BaseModel):
    schema_sql: str
    seed_sql: str = ""
    submitted_query: str
    test_cases: list[SqlTestCase]
    order_matters: bool = False


class SqlEvaluationAgent(Agent[SqlEvaluationInput, ExecutionOutput]):
    name = "sql_evaluation_agent"

    def run(self, payload: SqlEvaluationInput) -> ExecutionOutput:
        validation_error = validate_select_only(payload.submitted_query)

        results = []
        for tc in payload.test_cases:
            if validation_error:
                results.append({"id": tc.id, "category": tc.category, "passed": False, "error": validation_error})
                continue

            seed = tc.seed_sql_override if tc.seed_sql_override is not None else payload.seed_sql
            rows, error = _run_query(payload.schema_sql, seed, payload.submitted_query)
            if error:
                results.append({"id": tc.id, "category": tc.category, "passed": False, "error": error})
                continue

            passed = _rows_match(rows, tc.expected_rows, payload.order_matters)
            results.append({
                "id": tc.id, "category": tc.category, "passed": passed,
                "error": None if passed else f"expected {tc.expected_rows}, got {[list(r) for r in rows]}",
            })

        return ExecutionOutput(status="ok", results=results, raw_error=validation_error)
