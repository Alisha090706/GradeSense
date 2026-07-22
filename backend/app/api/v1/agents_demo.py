"""
Demo endpoints proving the ported agents are wired up end-to-end through the
new FastAPI app, running against the bundled `second-largest-pair-sum` demo
assignment (via legacy_store — see agents/legacy_store.py docstring for why
this is temporary). These are NOT the real Phase 2+ assignment/submission
API — that gets proper DB-backed routes, request auth, and resource-shaped
URLs once Auth (Phase 1) and Assignment CRUD (Phase 2) land. This router
exists purely to make Phase 0 demoable end-to-end over HTTP.
"""
from fastapi import APIRouter, HTTPException

from app.agents import legacy_store, orchestrator

router = APIRouter(prefix="/agents-demo", tags=["agents-demo (temporary, pre-auth)"])


@router.get("/assignments")
def list_demo_assignments():
    return legacy_store.list_assignments()


@router.post("/assignments/{assignment_id}/grade/{student_id}")
def grade_one_demo(assignment_id: str, student_id: str):
    try:
        return orchestrator.grade_one(assignment_id, student_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/assignments/{assignment_id}/run-pipeline")
def run_pipeline_demo(assignment_id: str):
    try:
        logs: list[str] = []
        feedback, insights, similarity = orchestrator.run_pipeline(assignment_id, log=logs.append)
        return {"log": logs, "feedback": feedback, "insights": insights, "similarity": similarity}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
