from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import EXTERNAL_ROLES, get_current_user, require_roles
from ..i18n import t as translate
from ..models import Client, ProjectIntake, User, UserRole
from ..schemas import ProjectIntakeCreate, ProjectIntakeRead, ProjectIntakeStatusUpdate

router = APIRouter(tags=["project-intakes"])


@router.post("/clients/{client_id}/intakes", response_model=ProjectIntakeRead, status_code=status.HTTP_201_CREATED)
def create_intake(
    client_id: str,
    data: ProjectIntakeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectIntake:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", user.language))
    if user.role in EXTERNAL_ROLES and (user.role != UserRole.CLIENT_PM or user.client_id != client_id):
        raise HTTPException(status_code=403, detail=translate("Somente o PM do cliente pode solicitar um novo projeto", user.language))
    intake = ProjectIntake(client_id=client_id, **data.model_dump())
    db.add(intake)
    db.commit()
    db.refresh(intake)
    return intake


@router.get("/clients/{client_id}/intakes", response_model=list[ProjectIntakeRead])
def list_intakes(client_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProjectIntake]:
    if user.role in EXTERNAL_ROLES and user.client_id != client_id:
        raise HTTPException(status_code=403, detail=translate("Fora do escopo do cliente", user.language))
    return list(db.scalars(select(ProjectIntake).where(ProjectIntake.client_id == client_id)).all())


@router.patch("/intakes/{intake_id}/status", response_model=ProjectIntakeRead)
def update_intake_status(
    intake_id: str,
    data: ProjectIntakeStatusUpdate,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> ProjectIntake:
    intake = db.get(ProjectIntake, intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail=translate("Solicitação não encontrada", user.language))
    intake.status = data.status
    db.commit()
    db.refresh(intake)
    return intake
