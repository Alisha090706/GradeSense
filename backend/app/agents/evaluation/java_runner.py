"""
Java runner — codegen-based, same pattern as cpp_runner.py (see
codegen.py's module docstring). The student's submission must define a
public class named `Solution`; a generated `Main.java` instantiates it
and hardcodes each test case as a literal method call, using
`String.valueOf` / `Arrays.toString` (java_repr_expr in codegen.py) to
format the return value into the same canonical string format every
other language's runner matches against.

Testing note, stated plainly rather than glossed over: this sandbox has a
JRE (`java`) but no JDK (`javac`), so unlike python_runner.py, js_runner.py,
and cpp_runner.py — all of which were compiled/run for real against
multiple real test cases while building this — this module could only be
code-reviewed against the same pattern already proven to work in C++, not
actually compiled here. Treat it as the least-verified of the four runners
and prioritize testing it first once you have a JDK locally
(`javac --version` — install via `apt install default-jdk` or similar if
missing).

Same scope limitations as the C++ runner: a missing/misnamed method is a
compile error affecting the whole submission (not a per-test-case
failure), and expect_raises is checked coarsely — any thrown Exception
whose simple class name matches is accepted; Java's actual checked-
exception rules aren't enforced against the student's method signature.
"""
import os
import shutil
import subprocess
import tempfile
import time

from app.agents.evaluation.base_runner import LanguageRunner
from app.agents.evaluation.codegen import UnsupportedTypeError, canonical_repr, java_literal, java_repr_expr, java_type
from app.agents.evaluation.schemas import ExecutionOutput
from app.execution_sandbox.limits import apply_resource_limits


def _escape_java_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _generate_test_block(tc: dict) -> str:
    args_src = ", ".join(java_literal(a) for a in tc.get("args", []))
    call = f'sol.{tc["function"]}({args_src})'
    test_id = _escape_java_string(tc["id"])

    if "expect_raises" in tc:
        expected_exc = _escape_java_string(tc["expect_raises"])
        # Call as a bare statement, not `Object actual = {call}` — the target method
        # may return void (common for a method whose only job here is to validate
        # input and throw), and `void` can't be assigned to `Object` in Java, which
        # used to make this a compile error for every void-returning method under
        # test, not just genuinely broken submissions.
        return f"""        try {{
            {call};
            System.out.println("RESULT|{test_id}|FAIL|expected an exception but got a return value");
        }} catch (Exception e) {{
            String excName = e.getClass().getSimpleName();
            if (excName.equals("{expected_exc}")) {{
                System.out.println("RESULT|{test_id}|PASS|");
            }} else {{
                System.out.println("RESULT|{test_id}|FAIL|expected " + "{expected_exc}" + " but got " + excName + ": " + e.getMessage());
            }}
        }}
"""
    expected_value = tc.get("expected")
    expected_str = _escape_java_string(canonical_repr(expected_value))
    return_type = java_type(expected_value)
    repr_expr = java_repr_expr("actual", expected_value)
    return f"""        try {{
            {return_type} actual = {call};
            String actualStr = {repr_expr};
            String expectedStr = "{expected_str}";
            if (actualStr.equals(expectedStr)) {{
                System.out.println("RESULT|{test_id}|PASS|");
            }} else {{
                System.out.println("RESULT|{test_id}|FAIL|expected " + expectedStr + ", got " + actualStr);
            }}
        }} catch (Exception e) {{
            System.out.println("RESULT|{test_id}|FAIL|" + e.getClass().getSimpleName() + ": " + e.getMessage());
        }}
"""


def _generate_main_java(test_cases: list[dict]) -> str:
    body = "\n".join(_generate_test_block(tc) for tc in test_cases)
    return f"""public class Main {{
    public static void main(String[] args) {{
        Solution sol = new Solution();
{body}    }}
}}
"""


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


class JavaRunner(LanguageRunner):
    language = "java"

    def run(self, submission_content: str, test_cases: list[dict], timeout_seconds: int) -> ExecutionOutput:
        javac = shutil.which("javac")
        java = shutil.which("java")
        if javac is None or java is None:
            return ExecutionOutput(status="crash", raw_error="A JDK (javac) is not installed on this server.")

        try:
            main_java = _generate_main_java(test_cases)
        except UnsupportedTypeError as e:
            return ExecutionOutput(status="crash", raw_error=f"Could not generate the test harness: {e}")

        tmp_dir = tempfile.mkdtemp()
        try:
            with open(os.path.join(tmp_dir, "Solution.java"), "w") as f:
                f.write(submission_content)
            with open(os.path.join(tmp_dir, "Main.java"), "w") as f:
                f.write(main_java)

            compile_proc = subprocess.run(
                [javac, "Solution.java", "Main.java"],
                capture_output=True, text=True, timeout=30, cwd=tmp_dir,
            )
            if compile_proc.returncode != 0:
                return ExecutionOutput(status="crash", raw_error=compile_proc.stderr.strip()[-1200:])

            start = time.monotonic()
            try:
                run_proc = subprocess.run(
                    # -Xmx/-Xss bound the JVM's actual heap/stack usage directly, since
                    # RLIMIT_AS can't be used here — see limits.py's apply_resource_limits
                    # docstring for why (the JVM needs ~2GB of virtual address space just
                    # to start, regardless of -Xmx, so limit_address_space=False below).
                    [java, "-Xmx256m", "-Xss8m", "-cp", tmp_dir, "Main"],
                    capture_output=True, text=True, timeout=timeout_seconds,
                    preexec_fn=apply_resource_limits(cpu_seconds=timeout_seconds + 2, limit_address_space=False),
                )
            except subprocess.TimeoutExpired:
                return ExecutionOutput(
                    status="timeout",
                    raw_error=f"Execution exceeded {timeout_seconds}s timeout (likely infinite loop)",
                    elapsed_ms=round((time.monotonic() - start) * 1000, 1),
                )
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            if run_proc.returncode != 0:
                # JVM init failures (e.g. "Could not reserve enough space for the
                # object heap") print to stdout, not stderr — check both rather
                # than losing the real reason behind a generic exit-code message.
                detail = run_proc.stderr.strip() or run_proc.stdout.strip() or f"Program exited with code {run_proc.returncode}"
                return ExecutionOutput(status="crash", raw_error=detail[-800:], elapsed_ms=elapsed_ms)
            return ExecutionOutput(status="ok", results=_parse_results(run_proc.stdout, test_cases), elapsed_ms=elapsed_ms)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
