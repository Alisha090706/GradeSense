"""
execution_sandbox/limits.py — the one test in this whole suite that's
slow by design: it actually spawns a subprocess with an infinite CPU-bound
loop and confirms the resource limit kills it, rather than trusting the
wall-clock timeout every LanguageRunner also has as a second line of
defense. Mirrors the real verification run while building Phase 5 (see
that phase's README section).
"""
import subprocess
import sys

from app.execution_sandbox.limits import apply_resource_limits


class TestApplyResourceLimits:
    def test_normal_subprocess_runs_fine_under_limits(self):
        preexec = apply_resource_limits(cpu_seconds=2, memory_mb=256, max_processes=16)
        proc = subprocess.run(
            [sys.executable, "-c", "print('hello')"], capture_output=True, text=True, preexec_fn=preexec, timeout=5,
        )
        assert proc.returncode == 0
        assert proc.stdout.strip() == "hello"

    def test_cpu_bound_infinite_loop_is_actually_killed(self):
        # Real proof the CPU limit works, not just that setrlimit was called
        # without erroring — a wall-clock timeout alone would also "work" here,
        # which is exactly why this asserts on the *mechanism* (a negative
        # returncode from a signal, well under the 10s subprocess timeout used
        # as a backstop) rather than just "the process eventually stopped."
        preexec = apply_resource_limits(cpu_seconds=1, memory_mb=256)
        proc = subprocess.run(
            [sys.executable, "-c", "x = 0\nwhile True: x += 1"],
            capture_output=True, text=True, preexec_fn=preexec, timeout=10,
        )
        assert proc.returncode < 0  # killed by a signal (SIGKILL from the CPU limit), not a clean exit

    def test_file_size_limit_actually_caps_disk_writes(self, tmp_path):
        # Added in Phase 14 — closes a real gap the CPU/memory limits didn't
        # cover (a submission writing an ever-growing file could fill disk).
        # This asserts the write is genuinely capped at the configured limit,
        # not just that the subprocess eventually exits.
        output_file = tmp_path / "output.bin"
        preexec = apply_resource_limits(cpu_seconds=5, memory_mb=256, max_file_mb=1)
        code = (
            f"with open({str(output_file)!r}, 'wb') as f:\n"
            f"    for _ in range(1000):\n"
            f"        f.write(b'x' * 1024 * 1024)\n"
        )
        subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, preexec_fn=preexec, timeout=10)
        assert output_file.exists()
        assert output_file.stat().st_size <= 2 * 1024 * 1024  # capped near the 1MB limit, not the attempted 1000MB
