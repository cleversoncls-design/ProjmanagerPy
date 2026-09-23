from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_project_access, require_roles
from ..models import (
    AuditAction,
    Project,
    ProjectStatus,
    Resource,
    Task,
    TaskAssignment,
    Timesheet,
    TimesheetStatus,
    User,
    UserRole,
)
from ..schemas import TimesheetCreate, TimesheetRead, TimesheetStatusUpdate

router = APIRouter(tags=["timesheets"])


def _recalculate_actual_hours(db: Session, task_id: str | None) -> None:
    """Mantém `Task.actual_hours` como a soma dos timesheets APROVADOS da
    tarefa. Recalcula do zero a cada mudança de status (em vez de somar/
    subtrair incrementalmente) para nunca deixar o total dessincronizar.

    Esse campo existe no modelo desde a versão original, mas nada nunca o
    atualizava — toda tarefa ficava com `actual_hours = 0` para sempre.

    Soma em Python (em vez de `func.sum` no SQL) pelo mesmo motivo de
    `project_financials` em services.py: evita depender de como cada dialeto
    tipa o resultado de um agregado, e trabalha direto com os `Decimal`
    que o SQLAlchemy já entrega para colunas `Numeric`.
    """
    if not task_id:
        # Apontamento avulso, sem task — nada a recalcular.
        return
    task = db.get(Task, task_id)
    if not task:
        return
    hours = db.scalars(
        select(Timesheet.hours_spent).where(
            Timesheet.task_id == task_id, Timesheet.status == TimesheetStatus.APPROVED
        )
    ).all()
    task.actual_hours = sum((Decimal(h) for h in hours), Decimal("0"))


@router.post("/timesheets", response_model=TimesheetRead, status_code=status.HTTP_201_CREATED)
def create_timesheet(data: TimesheetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Timesheet:
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail="Usuário não possui recurso habilitado")

    task: Task | None = None
    project: Project | None = None

    if data.task_id:
        task = db.get(Task, data.task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        project = db.get(Project, task.project_id)
        require_project_access(project, user, write=True)
        if project.status != ProjectStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="Só é possível apontar horas em projetos ativos")

        assignment = db.scalar(
            select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.resource_id == resource.id)
        )
        if not assignment:
            raise HTTPException(status_code=403, detail="Recurso não está alocado nesta tarefa")

        duplicate = db.scalar(
            select(Timesheet).where(
                Timesheet.task_id == task.id,
                Timesheet.resource_id == resource.id,
                Timesheet.date == data.date,
            )
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Já existe um apontamento deste recurso nesta tarefa para esta data")
    elif data.project_id:
        # Apontamento avulso (sem task na EAP) mas alocado a um projeto —
        # ex.: reunião com o cliente, suporte pontual. Continua exigindo
        # escopo/escrita e projeto ativo, só dispensa TaskAssignment.
        project = db.get(Project, data.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        require_project_access(project, user, write=True)
        if project.status != ProjectStatus.ACTIVE:
            raise HTTPException(status_code=422, detail="Só é possível apontar horas em projetos ativos")
    # else: hora administrativa interna (sem task nem projeto) — qualquer
    # recurso autenticado pode lançar, sem checagem de escopo de cliente.

    entry = Timesheet(
        task_id=task.id if task else None,
        project_id=project.id if project else None,
        resource_id=resource.id,
        date=data.date,
        hours_spent=data.hours_spent,
        description=data.description,
    )
    db.add(entry)
    db.flush()
    record_audit(db, entity_type="timesheet", entity_id=entry.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/timesheets", response_model=list[TimesheetRead])
def list_timesheets(
    project_id: str | None = None,
    task_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Timesheet]:
    # outerjoin (não join) porque apontamentos avulsos têm task_id nulo —
    # um INNER JOIN os excluiria até de listagens por project_id, já que
    # esses registros também carregam o project_id diretamente em Timesheet.
    stmt = select(Timesheet).outerjoin(Task, Task.id == Timesheet.task_id)
    if task_id:
        stmt = stmt.where(Timesheet.task_id == task_id)
    elif project_id:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Projeto não encontrado")
        require_project_access(project, user)
        stmt = stmt.where(or_(Task.project_id == project_id, Timesheet.project_id == project_id))
    else:
        raise HTTPException(status_code=422, detail="Informe project_id ou task_id")
    return list(db.scalars(stmt).all())


@router.patch("/timesheets/{timesheet_id}/status", response_model=TimesheetRead)
def update_timesheet_status(
    timesheet_id: str,
    data: TimesheetStatusUpdate,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> Timesheet:
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Apontamento não encontrado")
    entry.status = data.status
    _recalculate_actual_hours(db, entry.task_id)
    record_audit(
        db,
        entity_type="timesheet",
        entity_id=entry.id,
        action=AuditAction.UPDATE,
        user_id=user.id,
        details={"status": data.status.value},
    )
    db.commit()
    db.refresh(entry)
    return entry
