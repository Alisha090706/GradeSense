"""
Generic Test Harness
---------------------
Executed (via subprocess) against ONE student submission at a time, for
ANY assignment — the test cases themselves are data (test_cases.json), not
hardcoded Python, which is what makes multi-assignment support possible.

Usage:
    python generic_test_suite.py <path_to_test_cases.json> <path_to_submission.py>

Prints a JSON blob to stdout: {"results": [ {id, category, passed, error}, ... ]}
Any uncaught import error / syntax error is caught and reported as a single
"IMPORT" level failure instead of crashing the harness.

Test case schema (each item in test_cases.json):
    {
      "id": "unique_id",
      "category": "grouping label shown in the rubric breakdown",
      "function": "name of the function under test",
      "args": [ ... positional arguments, JSON-serializable ... ],
      "expected": <JSON value>,          # OR:
      "expect_raises": "ValueError",     # exception type name, mutually exclusive with "expected"
      "points": 1
    }
"""
import sys
import json
import importlib.util


def load_module(path):
    spec = importlib.util.spec_from_file_location("submission", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(test_cases_path, submission_path):
    with open(test_cases_path) as f:
        test_cases = json.load(f)

    try:
        module = load_module(submission_path)
    except Exception as e:
        return {"results": [{"id": "IMPORT", "category": "structure", "passed": False,
                              "error": f"{type(e).__name__}: {e}"}]}

    results = []
    for case in test_cases:
        fn = getattr(module, case["function"], None)
        if fn is None:
            results.append({"id": case["id"], "category": case["category"], "passed": False,
                             "error": f"missing required function '{case['function']}'"})
            continue
        try:
            actual = fn(*case["args"])
            if "expect_raises" in case:
                results.append({"id": case["id"], "category": case["category"], "passed": False,
                                 "error": f"expected {case['expect_raises']} but got return value {actual!r}"})
            elif actual == case["expected"]:
                results.append({"id": case["id"], "category": case["category"], "passed": True, "error": None})
            else:
                results.append({"id": case["id"], "category": case["category"], "passed": False,
                                 "error": f"expected {case['expected']!r}, got {actual!r}"})
        except Exception as e:
            if "expect_raises" in case and type(e).__name__ == case["expect_raises"]:
                results.append({"id": case["id"], "category": case["category"], "passed": True, "error": None})
            else:
                results.append({"id": case["id"], "category": case["category"], "passed": False,
                                 "error": f"{type(e).__name__}: {e}"})
    return {"results": results}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1], sys.argv[2])))
