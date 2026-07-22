"""
Reference-Solution Verification Harness (Python)
--------------------------------------------------
Executed via subprocess — same isolation pattern as python_harness.py, but
for a *teacher's reference solution* during AI test-case generation
(assignment_setup_agent.py) rather than a student submission.

Why this exists as a subprocess at all, instead of importlib.import_module
in-process (the old approach): a reference solution is arbitrary code the
teacher pasted in. If it contains a top-level `input()` call, executing it
in-process blocks that thread forever waiting on stdin — and since the old
code called this synchronously from an async FastAPI route with no
timeout, that hung the entire request (and, because it blocked the event
loop, every other request too), matching the exact "POST
/generate-test-cases stays pending forever" bug this harness fixes. Running
in a subprocess with stdin redirected from /dev/null and a wall-clock
timeout means the worst case is now "this one subprocess gets killed after
N seconds and the caller gets a clear error" — never an indefinite hang.

This harness does NOT compare against the LLM-proposed expected value —
it *replaces* it with whatever the reference solution actually returns
(or the exception it actually raises), exactly like the old in-process
_verify_and_fix did. Verification (never trusting the LLM's guess at the
expected value) still happens; it just happens safely now.

Usage:
    python python_reference_harness.py <proposed_test_cases.json> <reference_solution.py>

Prints a JSON blob to stdout: {"verified": [ {...test case with expected/
expect_raises now set from real execution...}, ... ]}. Test cases that
can't be verified (missing function, wrong arity, unexpected error, an
expect_raises case that didn't actually raise) are silently dropped, same
as the original agent's contract — the route already handles "none of the
proposed test cases could be verified" as its own 400.
"""
import sys
import json
import importlib.util


def load_module(path):
    spec = importlib.util.spec_from_file_location("reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(test_cases_path, reference_path):
    with open(test_cases_path) as f:
        test_cases = json.load(f)

    try:
        module = load_module(reference_path)
    except Exception as e:
        return {"verified": [], "load_error": f"{type(e).__name__}: {e}"}

    verified = []
    for tc in test_cases:
        fn = getattr(module, tc.get("function", ""), None)
        if fn is None:
            continue
        args = tc.get("args", [])
        try:
            if "expect_raises" in tc:
                try:
                    fn(*args)
                    continue  # didn't actually raise — can't verify this case
                except Exception as e:
                    tc["expect_raises"] = type(e).__name__
            else:
                tc["expected"] = fn(*args)
            tc.setdefault("points", 1)
            tc.setdefault("category", tc.get("function", "general"))
            verified.append(tc)
        except Exception:
            continue
    return {"verified": verified}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2])))
