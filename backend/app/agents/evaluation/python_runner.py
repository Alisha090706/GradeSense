"""
Python runner — the Phase 0 execution_agent.py logic, now behind the
LanguageRunner interface (base_runner.py) and taking submission content
directly (writes its own temp file) rather than a path, so callers don't
need to know each runner's on-disk mechanics. Also now applies the
execution_sandbox resource limits on top of the existing wall-clock
timeout — see execution_sandbox/limits.py.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

from app.agents.evaluation.base_runner import LanguageRunner
from app.agents.evaluation.schemas import ExecutionOutput
from app.execution_sandbox.limits import apply_resource_limits

_HARNESS_PATH = os.path.join(os.path.dirname(__file__), "harnesses", "python_harness.py")


class PythonRunner(LanguageRunner):
    language = "python"

    def run(self, submission_content: str, test_cases: list[dict], timeout_seconds: int) -> ExecutionOutput:
        sub_fd, sub_path = tempfile.mkstemp(suffix=".py")
        tc_fd, tc_path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(sub_fd, "w") as f:
                f.write(submission_content)
            with os.fdopen(tc_fd, "w") as f:
                json.dump(test_cases, f)

            start = time.monotonic()
            try:
                proc = subprocess.run(
                    [sys.executable, _HARNESS_PATH, tc_path, sub_path],
                    capture_output=True, text=True, timeout=timeout_seconds,
                    preexec_fn=apply_resource_limits(cpu_seconds=timeout_seconds + 2),
                )
            except subprocess.TimeoutExpired:
                return ExecutionOutput(
                    status="timeout",
                    raw_error=f"Execution exceeded {timeout_seconds}s timeout (likely infinite loop)",
                    elapsed_ms=round((time.monotonic() - start) * 1000, 1),
                )
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            if proc.returncode != 0 or not proc.stdout.strip():
                return ExecutionOutput(
                    status="crash",
                    raw_error=proc.stderr.strip()[-800:] or "Unknown crash (no stdout)",
                    elapsed_ms=elapsed_ms,
                )
            try:
                payload_out = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                return ExecutionOutput(status="crash", raw_error="Harness produced non-JSON output",
                                        elapsed_ms=elapsed_ms)
            return ExecutionOutput(status="ok", results=payload_out["results"], elapsed_ms=elapsed_ms)
        finally:
            os.unlink(sub_path)
            os.unlink(tc_path)
