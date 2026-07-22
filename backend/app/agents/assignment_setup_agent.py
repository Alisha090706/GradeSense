"""
Assignment Setup Agent — pydantic-wrapped port of the original
assignment_setup_agent.py. This is the seed of the split described in the
architecture doc (Assignment Agent + Test Generation Agent); the split
happens in Phase 2/3 once templates and the Rubric Agent exist to hand off
to. For Phase 0 it stays merged, matching the original prototype exactly.

No offline fallback by design — generating good test cases from a
description is exactly the kind of reasoning a rule-based fallback can't
usefully substitute for. Without a configured LLM, teachers fill in test
cases by hand instead (this agent simply isn't invoked).

The reference solution is executed locally to verify every proposed
expected value against its own real output — the LLM proposes inputs, the
actual answers are computed by running the teacher's own trusted code,
never trusted from model output.
"""
import ast
import json
import re
import os
import subprocess
import sys
import tempfile

from pydantic import BaseModel

from app.agents.base import Agent
from app.agents import llm_client
from app.agents.evaluation.java_reference_runner import verify_java_test_cases
from app.execution_sandbox.limits import apply_resource_limits

SYSTEM_PROMPT = """You design test cases for an automated {language_label} grading system. Given an
assignment description, the function signatures students must implement, and a working
reference solution, propose a diverse set of test cases: typical cases, edge cases (empty
input, single element, negatives, duplicates, boundaries), and at least one case per function
that should raise an exception if the assignment implies one (e.g. invalid input).

Respond ONLY as a valid JSON array, no prose outside it. Each element:
{{"id": "short_snake_case_id", "category": "human-readable grouping, usually the function name
or a sub-topic of it", "function": "exact function name from the signatures given",
"args": [ ...positional arguments, JSON-serializable... ],
"expected": <the value the reference solution should return for these args>,
"points": 1}}

For a case that should raise an exception instead of returning a value, use
"expect_raises": "{exception_hint}" instead of "expected". Propose 6-14 test cases total
across all functions, spread across categories. Keep args JSON-serializable (lists, numbers,
strings, booleans, null, flat lists) — no tuples, sets, dicts, or custom objects{java_note}."""

_LANGUAGE_PROMPT_VARS = {
    "python": {
        "language_label": "Python",
        "exception_hint": "ExceptionClassName",
        "java_note": "",
    },
    "java": {
        "language_label": "Java",
        "exception_hint": "ExceptionSimpleClassName (e.g. IllegalArgumentException)",
        "java_note": " — and only int/double/boolean/String or flat arrays of those, since the "
                      "grading harness generates typed Java, not JSON parsing",
    },
}

_HARNESS_PATH = os.path.join(os.path.dirname(__file__), "evaluation", "harnesses", "python_reference_harness.py")
_REFERENCE_TIMEOUT_SECONDS = 15


class FunctionSpec(BaseModel):
    name: str
    signature: str = ""


class AssignmentSetupInput(BaseModel):
    title: str
    description: str
    functions: list[FunctionSpec]
    reference_source: str
    language: str = "python"  # "python" or "java"


class AssignmentSetupOutput(BaseModel):
    test_cases: list[dict]


# --- Python reference-solution safety -------------------------------------
#
# Reject reference solutions containing executable top-level code (a bare
# `input()`/`print()` call, a `main()` invocation, a loop, etc.) rather than
# just hoping the subprocess timeout below saves us — a clear "here's what's
# wrong and how to fix it" error is much more useful to a teacher than
# "generation timed out" fifteen seconds later. The subprocess+timeout is
# still there as defense in depth (e.g. for a function that's only ever
# *called* during verification and hangs inside its own body), but this
# check is what turns the common case into an instant, actionable 400.
_DISALLOWED_TOP_LEVEL_CALL_NAMES = {"input", "eval", "exec", "compile", "__import__"}


def _describe_unsafe_top_level_node(node: ast.stmt) -> str | None:
    """Returns a human-readable reason the given top-level statement is unsafe/
    executable, or None if it's fine (def/class/import/simple assignment/docstring)."""
    allowed_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom)
    if isinstance(node, allowed_types):
        return None
    if isinstance(node, ast.Assign):
        # A plain constant assignment (MAX = 100) is fine; anything with a call on
        # the right-hand side could itself run arbitrary code (e.g. `X = input()`).
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Call):
                return "a top-level assignment that calls a function"
        return None
    if isinstance(node, ast.AnnAssign):
        return None
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        return None  # module docstring
    if isinstance(node, ast.If):
        # `if __name__ == "__main__": main()` is common and harmless here — exec_module
        # runs with __name__ == "reference" (see harness), never "__main__", so this
        # branch never actually executes during verification. Anything else at the top
        # level under `if` is still flagged as executable top-level code.
        test = node.test
        is_main_guard = (
            isinstance(test, ast.Compare) and isinstance(test.left, ast.Name) and test.left.id == "__name__"
            and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)
        )
        if is_main_guard:
            return None
        return "a top-level `if` block that runs code on import"
    return f"a top-level {type(node).__name__} statement"


def _reject_unsafe_reference_source(source_code: str) -> None:
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        raise ValueError(f"Reference solution has a syntax error: {e}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called = node.func
            name = called.id if isinstance(called, ast.Name) else getattr(called, "attr", None)
            if name in _DISALLOWED_TOP_LEVEL_CALL_NAMES:
                raise ValueError(
                    f"Reference solutions can't contain a top-level call to `{name}()` — it would "
                    f"block (or arbitrarily execute code during) automated test-case generation. "
                    f"Remove it, or move it inside a function that a test case actually calls."
                )

    for node in tree.body:
        reason = _describe_unsafe_top_level_node(node)
        if reason is not None:
            raise ValueError(
                f"Reference solutions must only contain function/class definitions and imports at "
                f"the top level (found {reason}). Executable top-level code — input(), print(), a "
                f"direct call to main(), a loop, etc. — can hang or otherwise misbehave when the "
                f"solution is loaded for automated verification. Wrap it in a function instead."
            )


def _verify_python(test_cases: list[dict], reference_source: str) -> list[dict]:
    _reject_unsafe_reference_source(reference_source)

    tc_fd, tc_path = tempfile.mkstemp(suffix=".json")
    ref_fd, ref_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(tc_fd, "w") as f:
            json.dump(test_cases, f)
        with os.fdopen(ref_fd, "w") as f:
            f.write(reference_source)

        try:
            proc = subprocess.run(
                [sys.executable, _HARNESS_PATH, tc_path, ref_path],
                capture_output=True, text=True, timeout=_REFERENCE_TIMEOUT_SECONDS,
                stdin=subprocess.DEVNULL,
                preexec_fn=apply_resource_limits(cpu_seconds=_REFERENCE_TIMEOUT_SECONDS + 2),
            )
        except subprocess.TimeoutExpired:
            raise ValueError(
                f"Verifying the reference solution took longer than {_REFERENCE_TIMEOUT_SECONDS}s "
                f"(likely an infinite loop inside one of its functions) — generation was stopped "
                f"rather than hanging indefinitely. Check the reference solution and try again."
            )

        if proc.returncode != 0 or not proc.stdout.strip():
            raise ValueError(f"Reference solution crashed during verification: "
                              f"{(proc.stderr.strip() or 'unknown error')[-500:]}")
        try:
            payload_out = json.loads(proc.stdout.strip())
        except json.JSONDecodeError:
            raise ValueError("Reference-solution verification harness produced unexpected output.")
        if payload_out.get("load_error"):
            raise ValueError(f"Reference solution failed to import: {payload_out['load_error']}")
        return payload_out["verified"]
    finally:
        os.unlink(tc_path)
        os.unlink(ref_path)


def _extract_json_array(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


class AssignmentSetupAgent(Agent[AssignmentSetupInput, AssignmentSetupOutput]):
    name = "assignment_setup_agent"

    def run(self, payload: AssignmentSetupInput) -> AssignmentSetupOutput:
        language = (payload.language or "python").lower()
        if language not in _LANGUAGE_PROMPT_VARS:
            raise ValueError(f"Unsupported reference-solution language '{language}'. "
                              f"Supported: {sorted(_LANGUAGE_PROMPT_VARS)}.")

        if not llm_client.is_live():
            raise ValueError("No LLM provider configured — set GEMINI_API_KEY (or GROQ_API_KEY) "
                              "in .env to use AI test case generation, or add test cases manually.")
        if not payload.reference_source.strip():
            raise ValueError("A reference solution is required so proposed test cases can be "
                              "verified against real output before saving.")

        system_prompt = SYSTEM_PROMPT.format(**_LANGUAGE_PROMPT_VARS[language])
        fn_list = "\n".join(f"- {f.name}: {f.signature or f.name + '(...)'}" for f in payload.functions)
        user_prompt = (
            f"Assignment title: {payload.title}\n\n"
            f"Description:\n{payload.description}\n\n"
            f"Functions students must implement:\n{fn_list}\n\n"
            f"Reference solution:\n```{language}\n{payload.reference_source}\n```\n\n"
            f"Propose the test cases now."
        )
        text = llm_client.complete(system_prompt, user_prompt, max_tokens=2000)
        try:
            proposed = _extract_json_array(text)
        except Exception as e:
            raise ValueError(f"Model did not return valid JSON test cases ({e}). Try again or "
                              f"add test cases manually.")

        if language == "java":
            verified = verify_java_test_cases(proposed, payload.reference_source)
        else:
            verified = _verify_python(proposed, payload.reference_source)

        if not verified:
            raise ValueError("None of the proposed test cases could be verified against the "
                              "reference solution. Try again or add test cases manually.")
        return AssignmentSetupOutput(test_cases=verified)
