"""
Assignments, rubrics, and test cases.

Test-case visibility: students only ever see `kind=public` test cases
through this API — hidden/edge cases stay server-side and are only ever
used internally by the Evaluation Agent. Teachers/admins see everything,
since they authored the assignment.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, require_approved_teacher
from app.db.models.assignment import AssignmentTemplate
from app.db.models.user import User, UserRole
from app.schemas.assignment import (
    AssignmentCreate, AssignmentOut, AssignmentTemplateOut, AssignmentUpdate, GenerateTestCasesRequest,
    RubricOut, TestCaseCreate, TestCaseOut,
)
from app.services import assignment_service
from app.services.assignment_service import NotFoundError, OwnershipError

router = APIRouter(tags=["assignments"])


def _http_error(e: Exception):
    if isinstance(e, NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, OwnershipError):
        return HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/assignment-templates", response_model=list[AssignmentTemplateOut])
async def list_assignment_templates(db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    result = await db.execute(select(AssignmentTemplate))
    return list(result.scalars().all())


@router.post("/courses/{course_id}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    course_id: uuid.UUID, payload: AssignmentCreate, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        return await assignment_service.create_assignment(
            db, course_id, teacher.teacher.id, payload.title, payload.description, payload.type,
            payload.template_id, payload.difficulty, payload.constraints, payload.timeout_seconds,
        )
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)


@router.get("/courses/{course_id}/assignments", response_model=list[AssignmentOut])
async def list_assignments(course_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    return await assignment_service.list_assignments(db, course_id)


@router.get("/assignments/{assignment_id}", response_model=AssignmentOut)
async def get_assignment(assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db), _user=Depends(get_current_user)):
    try:
        return await assignment_service.get_assignment(db, assignment_id)
    except NotFoundError as e:
        raise _http_error(e)


@router.patch("/assignments/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: uuid.UUID, payload: AssignmentUpdate, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    """Partial update. Primarily exists so a dedicated MCQ editor can save
    `constraints={"questions": [...]}` after the assignment already exists —
    previously there was no way to change constraints post-creation at all,
    which meant MCQ questions couldn't be added, edited, or removed."""
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        return await assignment_service.update_assignment(
            db, assignment_id, teacher.teacher.id, payload.model_dump(exclude_unset=True),
        )
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)


@router.post("/assignments/{assignment_id}/rubric/generate", response_model=RubricOut)
async def regenerate_rubric(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        return await assignment_service.regenerate_rubric(db, assignment_id, teacher.teacher.id)
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)


@router.post(
    "/assignments/{assignment_id}/test-cases", response_model=TestCaseOut, status_code=status.HTTP_201_CREATED,
)
async def add_test_case(
    assignment_id: uuid.UUID, payload: TestCaseCreate, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        return await assignment_service.add_test_case(
            db, assignment_id, teacher.teacher.id, payload.kind, payload.input, payload.expected_output,
            payload.points,
        )
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)


@router.get("/assignments/{assignment_id}/test-cases", response_model=list[TestCaseOut])
async def list_test_cases(
    assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    include_hidden = user.role in (UserRole.teacher, UserRole.admin)
    return await assignment_service.list_test_cases(db, assignment_id, include_hidden)


@router.post(
    "/assignments/{assignment_id}/test-cases/generate", response_model=list[TestCaseOut],
    status_code=status.HTTP_201_CREATED,
)
async def generate_test_cases(
    assignment_id: uuid.UUID, payload: GenerateTestCasesRequest, db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_approved_teacher),
):
    await db.refresh(teacher, attribute_names=["teacher"])
    try:
        return await assignment_service.generate_test_cases(
            db, assignment_id, teacher.teacher.id, payload.reference_solution, payload.functions,
            payload.language,
        )
    except (NotFoundError, OwnershipError) as e:
        raise _http_error(e)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
