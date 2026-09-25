from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_project_access
from ..i18n import t as translate
from ..models import Project, ProjectExpense, User
from ..schemas import ProjectExpenseCreate, ProjectExpenseRead

router = APIRouter(prefix="/projects/{project_id}/expenses", tags=["expenses"])


def _get_project_or_404(db: Session, project_id: str, lang: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", lang))
    return project


@router.post("", response_model=ProjectExpenseRead, status_code=201)
def create_expense(
    project_id: str,
    data: ProjectExpenseCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectExpense:
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user, write=True)
    expense = ProjectExpense(project_id=project_id, **data.model_dump())
    db.add(expense)
    db.commit()
    db.refresh(expense)
    return expense


@router.get("", response_model=list[ProjectExpenseRead])
def list_expenses(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProjectExpense]:
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    return list(db.scalars(select(ProjectExpense).where(ProjectExpense.project_id == project_id)).all())
