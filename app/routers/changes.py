from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_project_access, require_roles
from ..models import ChangeRequest, Project, User, UserRole
from ..schemas import ChangeRequestCreate, ChangeRequestRead, ChangeRequestStatusUpdate

router = APIRouter(tags=["change-requests"])


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


@router.post("/projects/{project_id}/change-requests", response_model=ChangeRequestRead, status_code=201)
def create_change_request(
    project_id: str,
    data: ChangeRequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChangeRequest:
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user, write=True)
    change = ChangeRequest(project_id=project_id, requested_by=user.id, **data.model_dump())
    db.add(change)
    db.commit()
    db.refresh(change)
    return change


@router.get("/projects/{project_id}/change-requests", response_model=list[ChangeRequestRead])
def list_change_requests(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ChangeRequest]:
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user)
    return list(db.scalars(select(ChangeRequest).where(ChangeRequest.project_id == project_id)).all())


@router.patch("/change-requests/{change_id}/status", response_model=ChangeRequestRead)
def update_change_request_status(
    change_id: str,
    data: ChangeRequestStatusUpdate,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> ChangeRequest:
    change = db.get(ChangeRequest, change_id)
    if not change:
        raise HTTPException(status_code=404, detail="Solicitação de mudança não encontrada")
    change.status = data.status
    db.commit()
    db.refresh(change)
    return change
