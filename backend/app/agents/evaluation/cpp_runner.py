"""
C++ runner — codegen-based (see agents/evaluation/codegen.py's module
docstring for why): the student's file is compiled together with a
generated main.cpp that hardcodes each test case as a literal call, using
`auto` + an overloaded `reprValue()` so the generated code never needs to
know a function's return type ahead of time — overload resolution picks
the right formatter at compile time.

Known limitation, real and not hidden: because all test cases compile into
ONE translation unit, a missing or misnamed function is a COMPILE ERROR,
not a per-test-case runtime failure — the whole submission fails to
compile and every test case reports the same "could not compile" message,
unlike Python/JS where each test independently reports which function was
missing. This is an inherent property of static compilation, not a bug.

Also: expect_raises is checked coarsely — any thrown std::exception
satisfies it, since C++ has no clean unmangled runtime type name the way
Python/JS exceptions do. Specific exception *category* checking (e.g.
requiring out_of_range vs invalid_argument) isn't enforced.
"""
import os
import shutil
import subprocess
import tempfile
import time

from app.agents.evaluation.base_runner import LanguageRunner
from app.agents.evaluation.codegen import UnsupportedTypeError, canonical_repr, cpp_literal
from app.agents.evaluation.schemas import ExecutionOutput

_HARNESS_PREAMBLE = """#include <iostream>
#include <sstream>
#include <string>
#include <vector>
#include <cmath>
#include <stdexcept>

std::string reprValue(int v) { return std::to_string(v); }
std::string reprValue(bool v) { return v ? "true" : "false"; }
std::string reprValue(const std::string& v) { return v; }
std::string reprValue(double v) {
    std::ostringstream oss;
    if (v == (long long)v && std::abs(v) < 1e15) {
        oss << (long long)v << ".0";
    } else {
        oss.precision(15);
        oss << v;
    }
    return oss.str();
}
template<typename T>
std::string reprValue(const std::vector<T>& v) {
    std::string out = "[";
    for (size_t i = 0; i < v.size(); i++) {
        if (i) out += ", ";
        out += reprValue(v[i]);
    }
    out += "]";
    return out;
}
"""


def _escape_cpp_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _generate_test_block(tc: dict) -> str:
    args_src = ", ".join(cpp_literal(a) for a in tc.get("args", []))
    call = f'{tc["function"]}({args_src})'
    test_id = _escape_cpp_string(tc["id"])

    if "expect_raises" in tc:
        return f"""    try {{
        auto actual = {call};
        std::cout << "RESULT|{test_id}|FAIL|expected an exception but got a return value: " << reprValue(actual) << std::endl;
    }} catch (const std::exception& e) {{
        std::cout << "RESULT|{test_id}|PASS|" << std::endl;
    }}
"""
    expected_str = _escape_cpp_string(canonical_repr(tc.get("expected")))
    return f"""    try {{
        auto actual = {call};
        std::string actualStr = reprValue(actual);
        std::string expectedStr = "{expected_str}";
        if (actualStr == expectedStr) {{
            std::cout << "RESULT|{test_id}|PASS|" << std::endl;
        }} else {{
            std::cout << "RESULT|{test_id}|FAIL|expected " << expectedStr << ", got " << actualStr << std::endl;
        }}
    }} catch (const std::exception& e) {{
        std::cout << "RESULT|{test_id}|FAIL|" << e.what() << std::endl;
    }}
"""


def _generate_main_cpp(test_cases: list[dict]) -> str:
    body = "\n".join(_generate_test_block(tc) for tc in test_cases)
    return f'{_HARNESS_PREAMBLE}\n#include "solution.cpp"\n\nint main() {{\n{body}\n    return 0;\n}}\n'


def _parse_results(stdout: str, test_cases: list[dict]) -> list[dict]:
    by_id = {tc["id"]: tc for tc in test_cases}
    results = []
    for line in stdout.splitlines():
        if not line.startswith("RESULT|"):
            continue
        parts = line.split("|", 3)
        if len(parts) < 3:
            continue
        _, test_id, verdict = parts[0], parts[1], parts[2]
        error = parts[3] if len(parts) > 3 and parts[3] else None
        tc = by_id.get(test_id, {})
        results.append({
            "id": test_id, "category": tc.get("category", "general"),
            "passed": verdict == "PASS", "error": error,
        })
    return results


class CppRunner(LanguageRunner):
    language = "cpp"

    def run(self, submission_content: str, test_cases: list[dict], timeout_seconds: int) -> ExecutionOutput:
        gpp = shutil.which("g++")
        if gpp is None:
            return ExecutionOutput(status="crash", raw_error="g++ is not installed on this server.")

        try:
            main_cpp = _generate_main_cpp(test_cases)
        except UnsupportedTypeError as e:
            return ExecutionOutput(status="crash", raw_error=f"Could not generate the test harness: {e}")

        tmp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp_dir, "solution.cpp"), "w") as f:
                f.write(submission_content)
            with open(os.path.join(tmp_dir, "main.cpp"), "w") as f:
                f.write(main_cpp)
            binary_path = os.path.join(tmp_dir, "solution_bin")

            compile_proc = subprocess.run(
                [gpp, "-std=c++17", "-O1", os.path.join(tmp_dir, "main.cpp"), "-o", binary_path],
                capture_output=True, text=True, timeout=30, cwd=tmp_dir,
            )
            if compile_proc.returncode != 0:
                # All-or-nothing per the module docstring — every test case shares this
                # one message, matching how feedback_agent.py already handles a
                # status="crash" with no results (its "file could not be run at all" path).
                return ExecutionOutput(status="crash", raw_error=compile_proc.stderr.strip()[-1200:])

            from app.execution_sandbox.limits import apply_resource_limits
            start = time.monotonic()
            try:
                run_proc = subprocess.run(
                    [binary_path], capture_output=True, text=True, timeout=timeout_seconds,
                    preexec_fn=apply_resource_limits(cpu_seconds=timeout_seconds + 2),
                )
            except subprocess.TimeoutExpired:
                return ExecutionOutput(
                    status="timeout",
                    raw_error=f"Execution exceeded {timeout_seconds}s timeout (likely infinite loop)",
                    elapsed_ms=round((time.monotonic() - start) * 1000, 1),
                )
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            if run_proc.returncode != 0:
                return ExecutionOutput(
                    status="crash",
                    raw_error=(run_proc.stderr.strip() or f"Program exited with code {run_proc.returncode}")[-800:],
                    elapsed_ms=elapsed_ms,
                )
            return ExecutionOutput(status="ok", results=_parse_results(run_proc.stdout, test_cases), elapsed_ms=elapsed_ms)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
