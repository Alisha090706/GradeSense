"""
agents/evaluation/java_reference_runner.py — real javac/java compile-and-
run session verifying LLM-proposed test cases against an actual Java
reference solution (the Java counterpart of AssignmentSetupAgent's Python
verification). Skipped, not failed, without a JDK — same convention as
test_java_runner.py / test_cpp_runner_codegen.py.
"""
import shutil

import pytest

from app.agents.evaluation.java_reference_runner import verify_java_test_cases

pytestmark = pytest.mark.skipif(shutil.which("javac") is None, reason="javac not available on this system")

REFERENCE_JAVA = """
public class Solution {
    public int[] sortArray(int[] arr) {
        int[] copy = arr.clone();
        java.util.Arrays.sort(copy);
        return copy;
    }
    public boolean isEven(int n) {
        if (n < 0) throw new IllegalArgumentException("negative");
        return n % 2 == 0;
    }
    public String greet(String name) { return "Hello, " + name; }
}
"""


class TestVerifyJavaTestCases:
    def test_overwrites_wrong_llm_guessed_expected_value(self):
        # The LLM's guessed "expected" is deliberately wrong here — verification must
        # replace it with the real return value, not just validate the guess.
        proposed = [{"id": "t1", "function": "sortArray", "args": [[3, 1, 2]], "expected": [9, 9, 9]}]
        verified = verify_java_test_cases(proposed, REFERENCE_JAVA)
        assert len(verified) == 1
        assert verified[0]["expected"] == [1, 2, 3]

    def test_captures_real_exception_type(self):
        proposed = [{"id": "t1", "function": "isEven", "args": [-1], "expect_raises": "RuntimeException"}]
        verified = verify_java_test_cases(proposed, REFERENCE_JAVA)
        assert len(verified) == 1
        assert verified[0]["expect_raises"] == "IllegalArgumentException"

    def test_drops_expect_raises_case_that_does_not_raise(self):
        proposed = [{"id": "t1", "function": "isEven", "args": [4], "expect_raises": "RuntimeException"}]
        verified = verify_java_test_cases(proposed, REFERENCE_JAVA)
        assert verified == []

    def test_string_return_round_trips_through_json_capture(self):
        proposed = [{"id": "t1", "function": "greet", "args": ["World"], "expected": "wrong"}]
        verified = verify_java_test_cases(proposed, REFERENCE_JAVA)
        assert verified[0]["expected"] == "Hello, World"

    def test_reference_compile_error_raises_value_error(self):
        with pytest.raises(ValueError, match="compile"):
            verify_java_test_cases(
                [{"id": "t1", "function": "x", "args": [], "expected": 1}],
                "public class Solution { this is not java }",
            )
