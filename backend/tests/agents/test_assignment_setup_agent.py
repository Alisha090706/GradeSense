"""
agents/assignment_setup_agent.py — reference-solution safety.

Regression tests for the "POST /generate-test-cases stays pending
forever" bug: a reference solution containing a top-level `input()` call
used to be imported in-process with importlib, blocking indefinitely
(and, since the calling route awaited it synchronously with no timeout,
blocking the whole event loop — every other request too). Fixed with (1)
an AST-based rejection that catches the common case instantly with an
actionable error, and (2) a subprocess-with-timeout harness as defense in
depth for anything the AST check doesn't catch (e.g. a function that
hangs only when actually called).

test_subprocess_timeout_is_a_real_bound is intentionally slow (~15s) —
same tradeoff as test_execution_sandbox.py's real subprocess-kill test:
proving the actual mechanism, not just that no exception was raised.
"""
import time

import pytest

from app.agents.assignment_setup_agent import _reject_unsafe_reference_source, _verify_python


class TestRejectUnsafeReferenceSource:
    def test_top_level_input_call_is_rejected(self):
        source = 'def add(a, b):\n    return a + b\n\nx = input("go: ")\n'
        with pytest.raises(ValueError, match="input"):
            _reject_unsafe_reference_source(source)

    def test_bare_top_level_print_is_rejected(self):
        source = 'def add(a, b):\n    return a + b\n\nprint("loaded")\n'
        with pytest.raises(ValueError):
            _reject_unsafe_reference_source(source)

    def test_top_level_function_call_to_main_is_rejected(self):
        source = 'def add(a, b):\n    return a + b\n\ndef main():\n    pass\n\nmain()\n'
        with pytest.raises(ValueError):
            _reject_unsafe_reference_source(source)

    def test_main_guard_is_allowed_since_it_never_executes_on_import(self):
        # exec_module runs with __name__ == "reference", never "__main__", so this
        # extremely common pattern is safe and must not be rejected.
        source = (
            'def add(a, b):\n    return a + b\n\n'
            'if __name__ == "__main__":\n    print(add(1, 2))\n'
        )
        _reject_unsafe_reference_source(source)  # must not raise

    def test_plain_constant_assignment_is_allowed(self):
        source = 'MAX_SIZE = 100\n\ndef add(a, b):\n    return a + b\n'
        _reject_unsafe_reference_source(source)  # must not raise

    def test_syntax_error_is_reported_clearly(self):
        with pytest.raises(ValueError, match="syntax error"):
            _reject_unsafe_reference_source("def add(a, b:\n    return a + b")


class TestVerifyPython:
    SAFE_SOURCE = (
        "def add(a, b):\n    return a + b\n\n"
        "def is_even(n):\n"
        "    if n < 0:\n        raise ValueError('negative')\n"
        "    return n % 2 == 0\n"
    )

    def test_replaces_expected_with_real_return_value(self):
        verified = _verify_python(
            [{"id": "t1", "function": "add", "args": [2, 2]}], self.SAFE_SOURCE,
        )
        assert verified[0]["expected"] == 4

    def test_captures_real_exception_type(self):
        verified = _verify_python(
            [{"id": "t1", "function": "is_even", "args": [-1], "expect_raises": "AnythingGuessedWrong"}],
            self.SAFE_SOURCE,
        )
        assert verified[0]["expect_raises"] == "ValueError"

    def test_unsafe_source_is_rejected_before_any_subprocess_runs(self):
        with pytest.raises(ValueError):
            _verify_python([{"id": "t1", "function": "add", "args": [1, 1]}], 'x = input()\n')

    def test_subprocess_timeout_is_a_real_bound_not_an_infinite_hang(self):
        # A function that hangs only when *called* (not caught by the AST check,
        # which only looks at top-level statements) must still be bounded by the
        # subprocess timeout rather than hanging the caller forever.
        source = "def spins():\n    while True:\n        pass\n"
        start = time.monotonic()
        with pytest.raises(ValueError, match="longer than"):
            _verify_python([{"id": "t1", "function": "spins", "args": []}], source)
        # Bounded, not instant and not actually infinite — proves the timeout fired.
        assert time.monotonic() - start < 30
