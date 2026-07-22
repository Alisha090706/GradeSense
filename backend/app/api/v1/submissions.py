"""
Submissions — students submit, the OrchestratorV2 decision-table pipeline
grades them in-line (synchronous for now; the architecture doc's background-
job note in the tech-stack table is the natural upgrade once grading a full
class batch needs to happen without blocking each individual request),
students see their own results, and the owning teacher (or an admin) can
review any submission for their course.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_role
from app.db.models.assignment import Assignment
from app.db.models.academic import Course
from app.db.models.user import User, UserRole
from app.schemas.submission import SubmissionCreate, SubmissionResultOut
from app.services import submission_service
from app.services.submission_service import NotFoundError

router = APIRouter(tags=["submissions"])


async def _student_id(db: AsyncSession, user: User) -> uuid.UUID:
    await db.refresh(user, attribute_names=["student"])
    if user.student is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="No student profile on this account.")
    return user.student.id


@router.post(
    "/assignments/{assignment_id}/submissions", response_model=SubmissionResultOut,
    status_code=status.HTTP_201_CREATED,
)
async def submit(
    assignment_id: uuid.UUID, payload: SubmissionCreate, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.student)),
):
    student_id = await _student_id(db, user)
    try:
        result = await submission_service.create_submission(
            db, assignment_id, student_id, payload.content, payload.language,
        )
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return SubmissionResultOut(
        submission_id=result["submission_id"], exec_status=result["exec_status"], score=result["score"],
        total_points=result["total_points"], breakdown=result["breakdown"], feedback=result["feedback"],
        failing_tests=result["failing_tests"],
        similarity_flagged=[
            {"peer_student_id": f["peer_student_id"], "similarity": f["similarity"], "technique": f["technique"]}
            for f in result["similarity_flagged"]
        ],
        pipeline_log=result["pipeline_log"],
    )


@router.get("/assignments/{assignment_id}/submissions/mine")
async def list_my_submissions(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role(UserRole.student)),
):
    student_id = await _student_id(db, user)
    submissions = await submission_service.list_my_submissions(db, assignment_id, student_id)
    return [{"id": s.id, "created_at": s.created_at, "language": s.language} for s in submissions]


@router.get("/submissions/{submission_id}")
async def get_submission(
    submission_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(require_role(
        UserRole.student, UserRole.teacher, UserRole.admin,
    )),
):
    try:
        submission = await submission_service.get_submission_detail(db, submission_id)
    except NotFoundError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))

    if user.role == UserRole.student:
        await db.refresh(user, attribute_names=["student"])
        if user.student is None or submission.student_id != user.student.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not your submission.")
    elif user.role == UserRole.teacher:
        await db.refresh(user, attribute_names=["teacher"])
        assignment = await db.get(Assignment, submission.assignment_id)
        course = await db.get(Course, assignment.course_id)
        if user.teacher is None or course.teacher_id != user.teacher.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="You do not own this submission's course.")

    await db.refresh(submission, attribute_names=["execution_result", "feedback"])
    return {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "student_id": submission.student_id,
        "content": submission.content,
        "language": submission.language,
        "created_at": submission.created_at,
        "execution_result": (
            {"status": submission.execution_result.status, "runtime_ms": submission.execution_result.runtime_ms}
            if submission.execution_result else None
        ),
        "feedback": (
            {
                "score": submission.feedback.score, "total_points": submission.feedback.total_points,
                "breakdown": submission.feedback.breakdown, "text": submission.feedback.strengths,
            } if submission.feedback else None
        ),
    }
