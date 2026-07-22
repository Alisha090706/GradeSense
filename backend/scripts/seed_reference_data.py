"""
Seeds platform-wide reference data that no API route creates: the standard
Subjects list, and the Programming/SQL/MCQ/Theory assignment templates
(each with its default rubric and/or constraints schema, per the
architecture doc's Assignment Templates section). Idempotent — safe to
run more than once.

Usage:
    cd backend
    python -m scripts.seed_reference_data
"""
import asyncio

from sqlalchemy import select

from app.db.models.academic import Subject
from app.db.models.assignment import AssignmentTemplate, AssignmentType
from app.db.session import AsyncSessionLocal

SUBJECTS = [
    "Data Structures", "Algorithms", "Operating Systems", "Computer Networks",
    "DBMS", "OOP", "Software Engineering",
]

# Programming template from Phase 2, plus SQL/MCQ/Theory added in Phase 6 alongside
# the evaluation branches that now actually grade them (orchestrator_v2.py). Each
# template's default_fields documents what Assignment.constraints needs for that
# type, since constraints is a free-form JSONB field with no schema of its own.
TEMPLATES = [
    {
        "name": "Programming Assignment",
        "assignment_type": AssignmentType.programming,
        "default_fields": {
            "required_fields": ["title", "description", "functions", "reference_solution"],
            "evaluation_strategy": "execute_python_tests",
            "default_rubric": [
                {"name": "correctness", "weight": 0.5},
                {"name": "efficiency", "weight": 0.15},
                {"name": "edge_cases", "weight": 0.15},
                {"name": "readability", "weight": 0.1},
                {"name": "naming", "weight": 0.05},
                {"name": "documentation", "weight": 0.05},
            ],
        },
    },
    {
        "name": "SQL Assignment",
        "assignment_type": AssignmentType.sql,
        "default_fields": {
            "required_fields": ["title", "description"],
            "evaluation_strategy": "execute_against_hidden_db",
            "constraints_schema": {
                "schema_sql": "CREATE TABLE statements defining the hidden schema (required)",
                "seed_sql": "INSERT statements seeding test data (optional)",
                "order_matters": "bool, whether row order in results is graded (default false)",
            },
            "test_case_schema": {
                "expected_output": {"rows": "list of expected result rows, e.g. [[1, \"Alice\"], ...]"},
            },
        },
    },
    {
        "name": "MCQ Assignment",
        "assignment_type": AssignmentType.mcq,
        "default_fields": {
            "required_fields": ["title", "description"],
            "evaluation_strategy": "deterministic_key_match_per_question",
            "constraints_schema": {
                "questions": [
                    {
                        "id": "unique per-question id, e.g. q1",
                        "text": "question text",
                        "options": {"A": "option text", "B": "option text", "...": "..."},
                        "correct_options": "list of correct option keys, e.g. [\"B\"] "
                                            "or [\"A\", \"C\"] for multi-select",
                        "points": "number, defaults to 1",
                    },
                ],
            },
            "submission_content_schema": {
                "description": "JSON object mapping each question id to the list of "
                                "option keys the student selected",
                "example": {"q1": ["B"], "q2": ["A", "C"]},
            },
        },
    },
    {
        "name": "Theory Assignment",
        "assignment_type": AssignmentType.theory,
        "default_fields": {
            "required_fields": ["title", "description"],
            "evaluation_strategy": "llm_rubric_scoring",
            "default_rubric": [
                {"name": "conceptual_accuracy", "weight": 0.5},
                {"name": "depth_of_explanation", "weight": 0.25},
                {"name": "clarity", "weight": 0.15},
                {"name": "use_of_examples", "weight": 0.1},
            ],
        },
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as db:
        for name in SUBJECTS:
            existing = (await db.execute(select(Subject).where(Subject.name == name))).scalar_one_or_none()
            if existing is None:
                db.add(Subject(name=name))
                print(f"+ subject: {name}")

        for t in TEMPLATES:
            existing = (
                await db.execute(select(AssignmentTemplate).where(AssignmentTemplate.name == t["name"]))
            ).scalar_one_or_none()
            if existing is None:
                db.add(AssignmentTemplate(**t))
                print(f"+ template: {t['name']}")
            elif existing.default_fields != t["default_fields"]:
                # Keep already-seeded templates in sync with code changes (e.g. the MCQ
                # schema moving from a single correct_option to multiple questions) —
                # without this, a DB seeded before such a change silently keeps serving
                # stale schema documentation to the frontend/teachers forever.
                existing.default_fields = t["default_fields"]
                print(f"~ updated template: {t['name']}")

        await db.commit()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
