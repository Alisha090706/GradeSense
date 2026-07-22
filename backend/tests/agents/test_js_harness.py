"""
agents/evaluation/harnesses/js_harness.js — mirrors the real node
verification session from Phase 5: pass/fail detection, exceptions
matched via expect_raises, and a submission with a real syntax error
correctly reported through the IMPORT sentinel rather than crashing the
harness itself.

Requires node on PATH — skipped, not failed, if it isn't.
"""
import json
import os
import shutil
import subprocess
import tempfile

import pytest

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not available on this system")

HARNESS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "app", "agents", "evaluation", "harnesses", "js_harness.js",
)


def _run(submission_js, test_cases):
    with tempfile.TemporaryDirectory() as tmp:
        sub_path = os.path.join(tmp, "submission.js")
        tc_path = os.path.join(tmp, "test_cases.json")
        with open(sub_path, "w") as f:
            f.write(submission_js)
        with open(tc_path, "w") as f:
            json.dump(test_cases, f)
        proc = subprocess.run(["node", HARNESS_PATH, sub_path, tc_path], capture_output=True, text=True, timeout=5)
        return json.loads(proc.stdout)["results"]


class TestJsHarness:
    def test_pass_and_fail_are_both_detected(self):
        submission = "function add(a,b){return a+b;}\nmodule.exports={add};"
        results = _run(submission, [
            {"id": "t1", "category": "add", "function": "add", "args": [2, 3], "expected": 5, "points": 1},
            {"id": "t2", "category": "add", "function": "add", "args": [2, 2], "expected": 5, "points": 1},
        ])
        by_id = {r["id"]: r for r in results}
        assert by_id["t1"]["passed"] is True
        assert by_id["t2"]["passed"] is False

    def test_expect_raises_matches_a_thrown_exception(self):
        submission = (
            "function divide(a,b){ if(b===0) throw new RangeError('div by zero'); return a/b; }"
            "\nmodule.exports={divide};"
        )
        results = _run(submission, [
            {"id": "t1", "category": "divide", "function": "divide", "args": [4, 0],
             "expect_raises": "RangeError", "points": 1},
        ])
        assert results[0]["passed"] is True

    def test_syntax_error_is_reported_not_crashed(self):
        broken_submission = "function broken( { return 1 }\nmodule.exports={broken};"
        results = _run(broken_submission, [
            {"id": "t1", "category": "x", "function": "broken", "args": [], "expected": 1, "points": 1},
        ])
        assert results[0]["id"] == "IMPORT"
        assert results[0]["passed"] is False
