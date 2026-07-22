"""
Ingestion Agent — pydantic-wrapped port of the original prototype's
ingestion_agent.py. Logic is unchanged: scan a submissions folder, extract
a student ID from each filename, lightweight structural pre-check. Deep
correctness checks are left to the Evaluation Agent (execution_agent.py).
"""
import os
import re

from pydantic import BaseModel

from app.agents.base import Agent

FILENAME_PATTERN = re.compile(r"^(?P<student_id>[A-Za-z0-9]+)_submission\.py$")


class IngestionInput(BaseModel):
    submissions_dir: str


class IngestedFile(BaseModel):
    student_id: str
    path: str
    ok: bool
    note: str | None = None


class IngestionOutput(BaseModel):
    items: list[IngestedFile]


class IngestionAgent(Agent[IngestionInput, IngestionOutput]):
    name = "ingestion_agent"

    def run(self, payload: IngestionInput) -> IngestionOutput:
        items: list[IngestedFile] = []
        for fname in sorted(os.listdir(payload.submissions_dir)):
            path = os.path.join(payload.submissions_dir, fname)
            if not os.path.isfile(path):
                continue
            match = FILENAME_PATTERN.match(fname)
            if not match:
                items.append(IngestedFile(
                    student_id=fname, path=path, ok=False,
                    note="filename does not match '<studentID>_submission.py' convention",
                ))
                continue
            if os.path.getsize(path) == 0:
                items.append(IngestedFile(
                    student_id=match.group("student_id"), path=path, ok=False, note="empty file",
                ))
                continue
            items.append(IngestedFile(student_id=match.group("student_id"), path=path, ok=True))
        return IngestionOutput(items=items)
