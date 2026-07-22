"""JavaScript (Node) runner — same dynamic-dispatch approach as the Python
runner, just via require() instead of importlib. See harnesses/js_harness.js."""
import json
import os
import shutil
import subprocess
import tempfile
import time

from app.agents.evaluation.base_runner import LanguageRunner
from app.agents.evaluation.schemas import ExecutionOutput
from app.execution_sandbox.limits import apply_resource_limits

_HARNESS_PATH = os.path.join(os.path.dirname(__file__), "harnesses", "js_harness.js")


class JavaScriptRunner(LanguageRunner):
    language = "javascript"

    def run(self, submission_content: str, test_cases: list[dict], timeout_seconds: int) -> ExecutionOutput:
        node = shutil.which("node")
        if node is None:
            return ExecutionOutput(status="crash", raw_error="Node.js is not installed on this server.")

        tmp_dir = tempfile.mkdtemp()
        sub_path = os.path.join(tmp_dir, "submission.js")
        tc_path = os.path.join(tmp_dir, "test_cases.json")
        try:
            with open(sub_path, "w") as f:
                f.write(submission_content)
            with open(tc_path, "w") as f:
                json.dump(test_cases, f)

            start = time.monotonic()
            try:
                proc = subprocess.run(
                    [node, _HARNESS_PATH, sub_path, tc_path],
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
                return ExecutionOutput(status="crash", raw_error=proc.stderr.strip()[-800:] or "Unknown crash",
                                        elapsed_ms=elapsed_ms)
            try:
                payload_out = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                return ExecutionOutput(status="crash", raw_error="Harness produced non-JSON output",
                                        elapsed_ms=elapsed_ms)
            return ExecutionOutput(status="ok", results=payload_out["results"], elapsed_ms=elapsed_ms)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
