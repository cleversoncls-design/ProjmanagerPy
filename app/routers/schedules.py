from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..i18n import t as translate
from ..models import Project, Resource, ResourceSchedule, User, UserRole
from ..schemas import ResourceScheduleCreate, ResourceScheduleRead, ResourceScheduleUpdate

router = APIRouter(prefix="/resource-schedules", tags=["resource-schedules"])

# Só ADMIN/INTERNAL_PM montam a agenda (mesmo grupo que já gerencia
# recursos/projetos) — o consultor consulta a própria agenda (leitura
# liberada pros três perfis internos, mesmo padrão de GET /resources).
_MANAGE_ROLES = (UserRole.ADMIN, UserRole.INTERNAL_PM)
_READ_ROLES = (UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)


def _check_overlap(db: Session, resource_id: str, day: date, start_time, end_time, *, exclude_id: str | None = None) -> bool:
    """Um recurso não pode ter dois agendamentos com horário sobreposto no
    mesmo dia — sem essa checagem, a agenda podia mostrar o mesmo consultor
    "em dois lugares ao mesmo tempo" sem avisar ninguém. Sobreposição
    clássica de intervalos: start_a < end_b AND start_b < end_a."""
    stmt = select(ResourceSchedule).where(
        ResourceSchedule.resource_id == resource_id,
        ResourceSchedule.date == day,
        ResourceSchedule.start_time < end_time,
        ResourceSchedule.end_time > start_time,
    )
    if exclude_id:
        stmt = stmt.where(ResourceSchedule.id != exclude_id)
    return db.scalar(stmt) is not None


@router.post("", response_model=ResourceScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    data: ResourceScheduleCreate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> ResourceSchedule:
    if not db.get(Resource, data.resource_id):
        raise HTTPException(status_code=404, detail=translate("Recurso não encontrado", user.language))
    if not db.get(Project, data.project_id):
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    if data.end_time <= data.start_time:
        raise HTTPException(status_code=422, detail=translate("Hora final precisa ser depois da hora inicial", user.language))
    if _check_overlap(db, data.resource_id, data.date, data.start_time, data.end_time):
        raise HTTPException(status_code=409, detail=translate("Recurso já tem agendamento nesse horário", user.language))
    schedule = ResourceSchedule(**data.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[ResourceScheduleRead])
def list_schedules(
    resource_id: str | None = None,
    client_id: str | None = None,
    project_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    _: User = Depends(require_roles(*_READ_ROLES)),
    db: Session = Depends(get_db),
) -> list[ResourceSchedule]:
    """Filtros pedidos na tela "Agenda de consultores": consultor
    (resource_id), cliente (client_id — via join em Project, já que a
    agenda não guarda client_id direto), projeto (project_id) e período
    (start/end, inclusive dos dois lados)."""
    stmt = select(ResourceSchedule)
    if resource_id:
        stmt = stmt.where(ResourceSchedule.resource_id == resource_id)
    if project_id:
        stmt = stmt.where(ResourceSchedule.project_id == project_id)
    if client_id:
        stmt = stmt.join(Project, Project.id == ResourceSchedule.project_id).where(Project.client_id == client_id)
    if start:
        stmt = stmt.where(ResourceSchedule.date >= start)
    if end:
        stmt = stmt.where(ResourceSchedule.date <= end)
    return list(db.scalars(stmt.order_by(ResourceSchedule.date, ResourceSchedule.start_time)).all())


@router.patch("/{schedule_id}", response_model=ResourceScheduleRead)
def update_schedule(
    schedule_id: str,
    data: ResourceScheduleUpdate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> ResourceSchedule:
    schedule = db.get(ResourceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail=translate("Agendamento não encontrado", user.language))
    changes = data.model_dump(exclude_unset=True)
    if "project_id" in changes and not db.get(Project, changes["project_id"]):
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    new_date = changes.get("date", schedule.date)
    new_start = changes.get("start_time", schedule.start_time)
    new_end = changes.get("end_time", schedule.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=422, detail=translate("Hora final precisa ser depois da hora inicial", user.language))
    if _check_overlap(db, schedule.resource_id, new_date, new_start, new_end, exclude_id=schedule.id):
        raise HTTPException(status_code=409, detail=translate("Recurso já tem agendamento nesse horário", user.language))
    for field, value in changes.items():
        setattr(schedule, field, value)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    schedule = db.get(ResourceSchedule, schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail=translate("Agendamento não encontrado", user.language))
    db.delete(schedule)
    db.commit()
