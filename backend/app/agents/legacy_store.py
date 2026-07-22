"""
Legacy file-based assignment store — direct port of the original prototype's
assignment_store.py, kept as-is for Phase 0/Orchestrator demo purposes only.

This is intentionally NOT the long-term persistence layer: Phase 2 replaces
this with a real repository backed by the Assignment/TestCase/Submission
DB models in db/models/. It's kept here, unmodified, so the ported agents
have real demo data (the bundled `second-largest-pair-sum` assignment) to
run against before the DB-backed CRUD API exists — deleting this file is
a to-do for Phase 2, not before.
"""
import json
import os
import re
import datetime

_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
ASSIGNMENTS_DIR = os.path.join(_AGENTS_DIR, "legacy_data")

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title):
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "assignment"


def _paths(assignment_id):
    root = os.path.join(ASSIGNMENTS_DIR, assignment_id)
    return {
        "root": root,
        "meta": os.path.join(root, "meta.json"),
        "test_cases": os.path.join(root, "test_cases.json"),
        "reference_solution": os.path.join(root, "reference_solution.py"),
        "submissions": os.path.join(root, "submissions"),
        "output": os.path.join(root, "output"),
    }


def list_assignments():
    if not os.path.isdir(ASSIGNMENTS_DIR):
        return []
    out = []
    for assignment_id in sorted(os.listdir(ASSIGNMENTS_DIR)):
        paths = _paths(assignment_id)
        if not os.path.exists(paths["meta"]):
            continue
        meta = load_meta(assignment_id)
        test_cases = load_test_cases(assignment_id)
        n_submissions = 0
        if os.path.isdir(paths["submissions"]):
            n_submissions = len([f for f in os.listdir(paths["submissions"]) if f.endswith(".py")])
        out.append({
            "id": assignment_id,
            "title": meta.get("title", assignment_id),
            "description": meta.get("description", ""),
            "n_functions": len(meta.get("functions", [])),
            "n_test_cases": len(test_cases),
            "n_submissions": n_submissions,
            "total_points": sum(tc.get("points", 1) for tc in test_cases),
        })
    return out


def load_meta(assignment_id):
    with open(_paths(assignment_id)["meta"]) as f:
        return json.load(f)


def load_test_cases(assignment_id):
    path = _paths(assignment_id)["test_cases"]
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return json.load(f)


def get_paths(assignment_id):
    return _paths(assignment_id)


def submission_path(assignment_id, student_id):
    return os.path.join(_paths(assignment_id)["submissions"], f"{student_id}_submission.py")
