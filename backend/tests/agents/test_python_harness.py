"""agents/evaluation/harnesses/python_harness.py — the original prototype's
grading harness, unchanged in logic since Phase 0. Genuinely run here
(pure Python + subprocess, no pydantic dependency)."""
import json
import os
import subprocess
import sys
import tempfile

HARNESS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "app", "agents", "evaluation", "harnesses", "python_harness.py",
)


def _run(submission_code, test_cases):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as sub_f:
        sub_f.write(submission_code)
        sub_path = sub_f.name
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tc_f:
        json.dump(test_cases, tc_f)
        tc_path = tc_f.name
    try:
        proc = subprocess.run(
            [sys.executable, HARNESS_PATH, tc_path, sub_path], capture_output=True, text=True, timeout=5,
        )
        return json.loads(proc.stdout)["results"]
    finally:
        os.unlink(sub_path)
        os.unlink(tc_path)


class TestPythonHarness:
    def test_pass_and_fail_are_both_detected(self):
        submission = "def add(a, b):\n    return a + b\n"
        results = _run(submission, [
            {"id": "t1", "category": "add", "function": "add", "args": [2, 3], "expected": 5, "points": 1},
            {"id": "t2", "category": "add", "function": "add", "args": [2, 2], "expected": 5, "points": 1},
        ])
        by_id = {r["id"]: r for r in results}
        assert by_id["t1"]["passed"] is True
        assert by_id["t2"]["passed"] is False

    def test_list_return_values_compare_correctly(self):
        submission = "def reverse_array(arr):\n    return arr[::-1]\n"
        results = _run(submission, [
            {"id": "t1", "category": "reverse", "function": "reverse_array", "args": [[1, 2, 3]],
             "expected": [3, 2, 1], "points": 1},
        ])
        assert results[0]["passed"] is True

    def test_expect_raises_matches_a_raised_exception(self):
        submission = "def safe_divide(a, b):\n    if b == 0:\n        raise ValueError('no')\n    return a / b\n"
        results = _run(submission, [
            {"id": "t1", "category": "divide", "function": "safe_divide", "args": [4, 0],
             "expect_raises": "ValueError", "points": 1},
        ])
        assert results[0]["passed"] is True
