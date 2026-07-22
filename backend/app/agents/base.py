"""
Agent protocol.

Every agent exposes exactly one entrypoint, `run(input) -> output`, where
input/output are pydantic models. This uniformity is what lets the
Orchestrator (orchestrator.py) treat every agent polymorphically — it never
needs to know an agent's internals, only its declared AgentIO contract.

This is intentionally a very thin layer: it exists to *force* every agent to
declare a typed contract, not to add framework machinery on top of them.
"""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from pydantic import BaseModel

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class Agent(ABC, Generic[InputT, OutputT]):
    name: str = "agent"

    @abstractmethod
    def run(self, payload: InputT) -> OutputT:
        ...
