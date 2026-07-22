"""
Shared process-isolation helper used by every LanguageRunner.

No Docker (per the project's constraint) — this is deliberately NOT full
sandboxing. It's best-effort local isolation: a wall-clock timeout (every
runner already applies this via subprocess.run(timeout=...)) plus, on
POSIX systems, OS-level resource limits (CPU time, memory, process count)
applied in the child process before it execs the student's code or the
compiled binary. There is no network isolation and no filesystem jail
available without containers — that gap is real and intentionally not
hidden. See ARCHITECTURE.md §1 "Security model & limitations" for the
full threat model this was designed against.
"""
import sys


def apply_resource_limits(
    cpu_seconds: int = 10, memory_mb: int = 512, max_processes: int = 32, max_file_mb: int = 50,
    limit_address_space: bool = True,
):
    """Returns a zero-arg callable suitable for subprocess.run(preexec_fn=...).
    No-op on platforms without the `resource` module (Windows) — timeout-based
    isolation via subprocess's own `timeout=` still applies there, just without
    the extra CPU/memory/disk ceiling.

    limit_address_space=False skips RLIMIT_AS (virtual address space). The JVM
    reserves large virtual-memory regions up front — compressed-class space,
    metaspace, thread stacks, JIT code cache — independent of actual heap
    usage; even `java -Xmx256m` needs roughly 2GB of *virtual* address space
    just to start. Capping RLIMIT_AS at a realistic per-submission ceiling
    (e.g. 512MB) makes every Java submission crash at JVM init with
    "Could not reserve enough space for ... object heap" / "Could not
    allocate compressed class space" — a real bug this project hit, not a
    hypothetical: see java_runner.py, which passes limit_address_space=False
    and instead bounds actual Java heap/stack usage directly via `-Xmx`/`-Xss`
    on the `java` command line, relying on RLIMIT_CPU (still applied) and the
    wall-clock subprocess timeout for the rest."""
    if sys.platform == "win32":
        return None

    def _apply():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
        if limit_address_space:
            resource.setrlimit(resource.RLIMIT_AS, (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024))
        # Added in Phase 14: without this, a submission that writes an
        # ever-growing file (or an accidental infinite write loop) could fill
        # the disk — a resource-exhaustion vector that CPU/memory limits alone
        # don't cover, and a real gap in Phases 0-5's original sandbox design.
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (max_file_mb * 1024 * 1024, max_file_mb * 1024 * 1024))
        except (ValueError, OSError):
            pass
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (max_processes, max_processes))
        except (ValueError, OSError):
            pass  # some platforms/containers don't allow lowering NPROC from a child

    return _apply
