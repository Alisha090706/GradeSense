"""
Execution Agent — Phase 5.

Now a thin dispatcher over the LanguageRunner interface
(agents/evaluation/base_runner.py) instead of being Python-specific logic
itself. The actual per-language work lives in agents/evaluation/
{python,java,cpp,js}_runner.py. ExecutionInput/ExecutionOutput are
re-exported from evaluation/schemas.py so existing imports of
`from app.agents.execution_agent import ExecutionInput` (orchestrator_v2.py,
etc.) keep working unchanged.
"""
from app.agents.base import Agent
from app.agents.evaluation.cpp_runner import CppRunner
from app.agents.evaluation.java_runner import JavaRunner
from app.agents.evaluation.js_runner import JavaScriptRunner
from app.agents.evaluation.python_runner import PythonRunner
from app.agents.evaluation.schemas import DEFAULT_TIMEOUT_SECONDS, ExecutionInput, ExecutionOutput  # noqa: F401

_RUNNERS = {
    "python": PythonRunner(),
    "java": JavaRunner(),
    "cpp": CppRunner(),
    "javascript": JavaScriptRunner(),
}


class ExecutionAgent(Agent[ExecutionInput, ExecutionOutput]):
    name = "execution_agent"

    def run(self, payload: ExecutionInput) -> ExecutionOutput:
        runner = _RUNNERS.get(payload.language)
        if runner is None:
            return ExecutionOutput(
                status="crash",
                raw_error=f"Unsupported language '{payload.language}'. Supported: {sorted(_RUNNERS)}.",
            )
        return runner.run(payload.submission_content, payload.test_cases, payload.timeout_seconds)
