from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_project_access
from ..models import Project, Risk, User
from ..schemas import RiskCreate, RiskRead, RiskUpdate

router = APIRouter(tags=["risks"])


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


@router.post("/projects/{project_id}/risks", response_model=RiskRead, status_code=201)
def create_risk(project_id: str, data: RiskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Risk:
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user, write=True)
    risk = Risk(project_id=project_id, **data.model_dump())
    db.add(risk)
    db.commit()
    db.refresh(risk)
    return risk


@router.get("/projects/{project_id}/risks", response_model=list[RiskRead])
def list_risks(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Risk]:
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user)
    return list(db.scalars(select(Risk).where(Risk.project_id == project_id)).all())


@router.patch("/risks/{risk_id}", response_model=RiskRead)
def update_risk(risk_id: str, data: RiskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Risk:
    risk = db.get(Risk, risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risco não encontrado")
    require_project_access(risk.project, user, write=True)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(risk, field, value)
    db.commit()
    db.refresh(risk)
    return risk
