"""
agents/evaluation/cpp_runner.py's codegen — mirrors the real g++ compile-
and-run session from Phase 5: 6 test cases spanning int/array/bool/string/
exception types, including a deliberately-wrong case (must fail) and a
missing-function case (must be a compile error, not a runtime failure —
see cpp_runner.py's module docstring for why that's expected behavior for
compiled languages, not a bug).

Requires g++ on PATH — skipped, not failed, if it isn't (same principle
as pytest.importorskip for a missing package, applied to a missing binary).
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from app.agents.evaluation.cpp_runner import _generate_main_cpp, _parse_results

pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not available on this system")

SOLUTION_CPP = """
#include <vector>
#include <string>
#include <stdexcept>
int add(int a, int b) { return a + b; }
std::vector<int> reverseArray(std::vector<int> arr) {
    std::vector<int> out(arr.size());
    for (size_t i = 0; i < arr.size(); i++) out[i] = arr[arr.size()-1-i];
    return out;
}
bool isEven(int n) { return n % 2 == 0; }
double safeDivide(int a, int b) {
    if (b == 0) throw std::invalid_argument("division by zero");
    return (double)a / b;
}
std::string greet(std::string name) { return "hello " + name; }
"""

TEST_CASES = [
    {"id": "t1", "category": "add", "function": "add", "args": [2, 3], "expected": 5, "points": 1},
    {"id": "t2", "category": "add", "function": "add", "args": [2, 2], "expected": 5, "points": 1},  # deliberately wrong
    {"id": "t3", "category": "reverse", "function": "reverseArray", "args": [[1, 2, 3]], "expected": [3, 2, 1], "points": 1},
    {"id": "t4", "category": "even", "function": "isEven", "args": [4], "expected": True, "points": 1},
    {"id": "t5", "category": "safe_div", "function": "safeDivide", "args": [4, 0], "expect_raises": "invalid_argument", "points": 1},
    {"id": "t6", "category": "greet", "function": "greet", "args": ["world"], "expected": "hello world", "points": 1},
]


def _compile_and_run(test_cases, solution_cpp):
    main_cpp = _generate_main_cpp(test_cases)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "solution.cpp").write_text(solution_cpp)
        (tmp_path / "main.cpp").write_text(main_cpp)
        binary = tmp_path / "bin"
        compile_proc = subprocess.run(
            ["g++", "-std=c++17", "-O1", str(tmp_path / "main.cpp"), "-o", str(binary)],
            capture_output=True, text=True, timeout=30,
        )
        if compile_proc.returncode != 0:
            return None, compile_proc.stderr
        run_proc = subprocess.run([str(binary)], capture_output=True, text=True, timeout=5)
        return run_proc.stdout, None


class TestCppCodegenRealCompilation:
    def test_six_type_spanning_cases_all_resolve_correctly(self):
        stdout, compile_error = _compile_and_run(TEST_CASES, SOLUTION_CPP)
        assert compile_error is None, compile_error
        results = {r["id"]: r for r in _parse_results(stdout, TEST_CASES)}

        assert results["t1"]["passed"] is True
        assert results["t2"]["passed"] is False  # the deliberately-wrong case must actually fail
        assert results["t3"]["passed"] is True
        assert results["t4"]["passed"] is True
        assert results["t5"]["passed"] is True  # exception correctly caught and matched
        assert results["t6"]["passed"] is True  # string return type

    def test_missing_function_is_a_compile_error_not_a_runtime_failure(self):
        # Documented, expected behavior for compiled languages — see
        # cpp_runner.py's module docstring: a missing function can't be a
        # per-test-case runtime failure the way Python/JS report it, because
        # the whole translation unit fails to compile first.
        broken_solution = "int subtract(int a, int b) { return a - b; }"  # no 'add' defined
        stdout, compile_error = _compile_and_run([TEST_CASES[0]], broken_solution)
        assert stdout is None
        assert compile_error is not None
        assert "add" in compile_error
