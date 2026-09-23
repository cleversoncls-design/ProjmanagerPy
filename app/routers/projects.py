from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import EXTERNAL_ROLES, get_current_user, require_project_access, require_roles
from ..models import AuditAction, Client, Project, User, UserRole
from ..schemas import ProjectCreate, ProjectDetail, ProjectSummary, ProjectUpdate
from ..services import project_financials

router = APIRouter(prefix="/projects", tags=["projects"])

_FINANCIAL_FIELDS = ("management_hours", "management_rate", "consulting_hours", "consulting_rate")


def _recompute_sold_value(project: Project) -> None:
    """`sold_value` nunca é digitado diretamente: é sempre horas × taxa de
    cada bolsa (gestão + consultoria), recalculado aqui sempre que qualquer
    um dos quatro campos muda — para nunca ficar dessincronizado do pacote
    realmente vendido."""
    project.sold_value = (project.management_hours * project.management_rate) + (
        project.consulting_hours * project.consulting_rate
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> Project:
    if not db.get(Client, data.client_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    manager = db.get(User, data.manager_id)
    if not manager or manager.role not in {UserRole.ADMIN, UserRole.INTERNAL_PM}:
        raise HTTPException(status_code=422, detail="manager_id precisa ser um usuário interno (ADMIN ou INTERNAL_PM)")
    if db.scalar(select(Project).where(Project.code == data.code)):
        raise HTTPException(status_code=409, detail="Já existe um projeto com este código")
    project = Project(**data.model_dump())
    _recompute_sold_value(project)
    db.add(project)
    db.flush()
    record_audit(db, entity_type="project", entity_id=project.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    client_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    stmt = select(Project)
    if user.role in EXTERNAL_ROLES:
        stmt = stmt.where(Project.client_id == user.client_id)
    elif client_id:
        stmt = stmt.where(Project.client_id == client_id)
    return list(db.scalars(stmt.order_by(Project.created_at.desc())).all())


@router.get("/{project_id}", response_model=ProjectDetail)
def read_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user)
    payload = ProjectDetail.model_validate(project).model_dump()
    if user.role in EXTERNAL_ROLES:
        payload["sold_value"] = None
        payload["financials"] = None
        for field in _FINANCIAL_FIELDS:
            payload[field] = None
    else:
        payload["financials"] = project_financials(db, project.id)
    return payload


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    changes = data.model_dump(exclude_unset=True)
    if "manager_id" in changes:
        manager = db.get(User, changes["manager_id"])
        if not manager or manager.role not in {UserRole.ADMIN, UserRole.INTERNAL_PM}:
            raise HTTPException(status_code=422, detail="manager_id precisa ser um usuário interno (ADMIN ou INTERNAL_PM)")
    if user.role in EXTERNAL_ROLES:
        for field in _FINANCIAL_FIELDS:
            changes.pop(field, None)
    for field, value in changes.items():
        setattr(project, field, value)
    if any(field in changes for field in _FINANCIAL_FIELDS):
        _recompute_sold_value(project)
    if changes:
        record_audit(db, entity_type="project", entity_id=project.id, action=AuditAction.UPDATE, user_id=user.id, details={"fields": sorted(changes.keys())})
    db.commit()
    db.refresh(project)
    return project
