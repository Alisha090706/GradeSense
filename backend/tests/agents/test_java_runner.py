"""
agents/evaluation/java_runner.py — a real javac-compile-and-run session,
same principle as test_cpp_runner_codegen.py's g++ session: skipped (not
failed) if no JDK is present, but genuinely compiled and executed here
rather than only asserting on generated source text.

Two of these cases are regression tests for real bugs found and fixed
while wiring up this project's Java pipeline, not hypothetical ones:

1. test_array_argument_and_return (plus bool/string cases) — the JVM
   used to crash at startup ("Could not reserve enough space for the
   object heap") under this sandbox's RLIMIT_AS, for *every* Java
   submission regardless of what it did — see limits.py's
   apply_resource_limits docstring. If this whole file fails with a
   "crash" status instead of exercising real pass/fail logic, that
   regression is back.
2. test_void_method_with_expect_raises — void-returning methods used to
   be a Java compile error in the expect_raises code path specifically
   (`Object actual = <void call>` doesn't compile), breaking the whole
   submission (all test cases) rather than just failing gracefully.
"""
import shutil

import pytest

from app.agents.evaluation.java_runner import JavaRunner

pytestmark = pytest.mark.skipif(shutil.which("javac") is None, reason="javac not available on this system")

SOLUTION_JAVA = """
public class Solution {
    public int add(int a, int b) { return a + b; }
    public int[] sortArray(int[] arr) {
        int[] copy = arr.clone();
        java.util.Arrays.sort(copy);
        return copy;
    }
    public boolean isEven(int n) { return n % 2 == 0; }
    public String greet(String name) { return "Hello, " + name; }
    public void validate(int n) {
        if (n < 0) throw new IllegalArgumentException("must be non-negative");
    }
    public void noop() { }
}
"""


class TestJavaRunner:
    def setup_method(self):
        self.runner = JavaRunner()

    def test_array_argument_and_return(self):
        result = self.runner.run(SOLUTION_JAVA, [
            {"id": "t1", "function": "sortArray", "args": [[3, 1, 2]], "expected": [1, 2, 3], "category": "sort"},
        ], timeout_seconds=10)
        assert result.status == "ok", result.raw_error
        assert result.results[0]["passed"] is True

    def test_scalar_types_bool_string_int(self):
        result = self.runner.run(SOLUTION_JAVA, [
            {"id": "t1", "function": "add", "args": [2, 3], "expected": 5, "category": "add"},
            {"id": "t2", "function": "isEven", "args": [4], "expected": True, "category": "bool"},
            {"id": "t3", "function": "greet", "args": ["World"], "expected": "Hello, World", "category": "str"},
        ], timeout_seconds=10)
        assert result.status == "ok", result.raw_error
        assert all(r["passed"] for r in result.results)

    def test_expect_raises_matches_thrown_exception(self):
        result = self.runner.run(SOLUTION_JAVA, [
            {"id": "t1", "function": "validate", "args": [-1], "expect_raises": "IllegalArgumentException", "category": "exc"},
        ], timeout_seconds=10)
        assert result.status == "ok", result.raw_error
        assert result.results[0]["passed"] is True

    def test_void_method_with_expect_raises_that_does_not_raise(self):
        # Regression test: this used to be a compile error (void assigned to Object)
        # for the whole submission, not just a failed test case.
        result = self.runner.run(SOLUTION_JAVA, [
            {"id": "t1", "function": "noop", "args": [], "expect_raises": "RuntimeException", "category": "exc"},
        ], timeout_seconds=10)
        assert result.status == "ok", result.raw_error
        assert result.results[0]["passed"] is False

    def test_wrong_expected_value_fails_not_crashes(self):
        result = self.runner.run(SOLUTION_JAVA, [
            {"id": "t1", "function": "add", "args": [2, 2], "expected": 5, "category": "add"},
        ], timeout_seconds=10)
        assert result.status == "ok", result.raw_error
        assert result.results[0]["passed"] is False

    def test_infinite_loop_times_out(self):
        source = "public class Solution { public int spin() { while (true) {} } }"
        result = self.runner.run(source, [
            {"id": "t1", "function": "spin", "args": [], "expected": 1, "category": "timeout"},
        ], timeout_seconds=2)
        assert result.status == "timeout"

    def test_compile_error_is_reported_not_crashed_silently(self):
        result = self.runner.run("public class Solution { this is not java }", [
            {"id": "t1", "function": "add", "args": [1, 1], "expected": 2, "category": "add"},
        ], timeout_seconds=10)
        assert result.status == "crash"
        assert result.raw_error
