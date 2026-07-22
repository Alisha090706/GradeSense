"""
Java Reference-Solution Verification — the Java counterpart of
harnesses/python_reference_harness.py, used by assignment_setup_agent.py
when language="java".

Same job as the Python harness: never trust the LLM's guess at a test
case's expected output — replace it with whatever the reference solution
*actually* returns (or raises), verified by really compiling and running
it. Reuses the same javac -> JVM execution -> method invocation pipeline
already proven out in java_runner.py (same JDK check, same -Xmx/-Xss +
RLIMIT_CPU sandboxing — see limits.py's apply_resource_limits docstring
for why RLIMIT_AS is skipped for the JVM), but instead of comparing actual
vs. proposed-expected and reporting PASS/FAIL, it serializes the actual
return value to JSON (via codegen.py's java_json_repr_expr /
JAVA_JSON_HELPERS) and hands it back to Python as a real typed value via
json.loads — so the resulting TestCase row's `expected` field is a plain
Python int/float/bool/str/list, exactly like the Python pipeline produces,
and grades identically against real student Java submissions afterwards
(java_runner.py's own codegen infers the Java return type from that same
Python value).
"""
import json
import os
import shutil
import subprocess
import tempfile

from app.agents.evaluation.codegen import (
    JAVA_JSON_HELPERS, UnsupportedTypeError, java_json_repr_expr, java_literal, java_type,
)
from app.execution_sandbox.limits import apply_resource_limits

_COMPILE_TIMEOUT_SECONDS = 30
_RUN_TIMEOUT_SECONDS = 15


def _escape_java_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _generate_capture_block(tc: dict) -> str | None:
    """Returns the Java `try { ... } catch { ... }` block that calls the reference
    solution for one proposed test case and prints its real outcome — or None if
    the test case's proposed args/expected shape can't be typed (dropped, same as
    the Python harness silently drops unverifiable cases)."""
    try:
        args_src = ", ".join(java_literal(a) for a in tc.get("args", []))
    except UnsupportedTypeError:
        return None
    call = f'sol.{tc["function"]}({args_src})'
    test_id = _escape_java_string(tc["id"])

    if "expect_raises" in tc:
        return f"""        try {{
            {call};
            System.out.println("RESULT|{test_id}|NOEXC|");
        }} catch (Exception e) {{
            System.out.println("RESULT|{test_id}|EXC|" + e.getClass().getSimpleName());
        }}
"""
    expected_hint = tc.get("expected")
    try:
        return_type = java_type(expected_hint)
        json_expr = java_json_repr_expr("actual", expected_hint)
    except UnsupportedTypeError:
        return None
    return f"""        try {{
            {return_type} actual = {call};
            System.out.println("RESULT|{test_id}|OK|" + {json_expr});
        }} catch (Exception e) {{
            System.out.println("RESULT|{test_id}|ERR|" + e.getClass().getSimpleName() + ": " + e.getMessage());
        }}
"""


def _generate_main_java(test_cases: list[dict]) -> tuple[str, list[dict]]:
    blocks = []
    usable = []
    for tc in test_cases:
        fn_name = tc.get("function")
        if not fn_name or "id" not in tc:
            continue
        block = _generate_capture_block(tc)
        if block is not None:
            blocks.append(block)
            usable.append(tc)
    body = "\n".join(blocks)
    main_java = f"""public class Main {{
    public static void main(String[] args) {{
        Solution sol = new Solution();
{body}    }}
{JAVA_JSON_HELPERS}}}
"""
    return main_java, usable


def verify_java_test_cases(proposed_test_cases: list[dict], reference_source: str) -> list[dict]:
    """Compiles+runs `reference_source` (must define `public class Solution`) against
    each proposed test case's args, replacing `expected`/`expect_raises` with the real
    outcome. Returns only the test cases that could be verified — same contract as
    _verify_python in assignment_setup_agent.py. Raises ValueError for setup problems
    (no JDK, compile error, timeout) that aren't just "this one test case didn't verify"."""
    javac = shutil.which("javac")
    java = shutil.which("java")
    if javac is None or java is None:
        raise ValueError("A JDK (javac) is not installed on this server — Java reference solutions "
                          "can't be compiled for verification.")

    main_java, usable = _generate_main_java(proposed_test_cases)
    if not usable:
        return []

    tmp_dir = tempfile.mkdtemp()
    try:
        with open(os.path.join(tmp_dir, "Solution.java"), "w") as f:
            f.write(reference_source)
        with open(os.path.join(tmp_dir, "Main.java"), "w") as f:
            f.write(main_java)

        compile_proc = subprocess.run(
            [javac, "Solution.java", "Main.java"],
            capture_output=True, text=True, timeout=_COMPILE_TIMEOUT_SECONDS, cwd=tmp_dir,
        )
        if compile_proc.returncode != 0:
            raise ValueError(f"Reference solution failed to compile: {compile_proc.stderr.strip()[-1200:]}")

        try:
            run_proc = subprocess.run(
                [java, "-Xmx256m", "-Xss8m", "-cp", tmp_dir, "Main"],
                capture_output=True, text=True, timeout=_RUN_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
                preexec_fn=apply_resource_limits(cpu_seconds=_RUN_TIMEOUT_SECONDS + 2, limit_address_space=False),
            )
        except subprocess.TimeoutExpired:
            raise ValueError(f"Verifying the reference solution took longer than {_RUN_TIMEOUT_SECONDS}s "
                              f"(likely an infinite loop) — generation was stopped rather than hanging.")

        if run_proc.returncode != 0:
            detail = run_proc.stderr.strip() or run_proc.stdout.strip() or f"exit code {run_proc.returncode}"
            raise ValueError(f"Reference solution crashed during verification: {detail[-800:]}")

        return _parse_capture_results(run_proc.stdout, usable)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _parse_capture_results(stdout: str, test_cases: list[dict]) -> list[dict]:
    by_id = {tc["id"]: tc for tc in test_cases}
    verified = []
    for line in stdout.splitlines():
        if not line.startswith("RESULT|"):
            continue
        parts = line.split("|", 3)
        if len(parts) < 3:
            continue
        _, test_id, verdict = parts[0], parts[1], parts[2]
        detail = parts[3] if len(parts) > 3 else ""
        tc = by_id.get(test_id)
        if tc is None:
            continue
        if verdict == "OK":
            try:
                tc["expected"] = json.loads(detail)
            except json.JSONDecodeError:
                continue  # couldn't parse the captured value — drop, don't guess
        elif verdict == "EXC":
            tc["expect_raises"] = detail
        else:
            continue  # NOEXC (expected an exception but didn't get one) or ERR — unverifiable
        tc.setdefault("points", 1)
        tc.setdefault("category", tc.get("function", "general"))
        verified.append(tc)
    return verified
