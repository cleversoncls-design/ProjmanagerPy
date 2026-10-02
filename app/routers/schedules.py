from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import INTERNAL_ROLES, MANAGEMENT_ROLES, require_roles
from ..i18n import t as translate
from ..models import Project, Resource, ResourceSchedule, ResourceScheduleTask, Task, Timesheet, TimesheetStatus, User
from ..schemas import ResourceScheduleCreate, ResourceScheduleRead, ResourceScheduleUpdate

router = APIRouter(prefix="/resource-schedules", tags=["resource-schedules"])

# MANAGEMENT_ROLES monta a agenda (mesmo grupo que já gerencia
# recursos/projetos) — o consultor consulta a própria agenda (leitura
# liberada por INTERNAL_ROLES, mesmo padrão de GET /resources).
_MANAGE_ROLES = MANAGEMENT_ROLES
_READ_ROLES = INTERNAL_ROLES


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


def _check_absence(db: Session, resource_id: str, day: date) -> bool:
    """Bloqueia um novo agendamento do recurso num dia em que ele tem
    ausência da empresa registrada (Timesheet.absence_type — pedido do
    usuário: "Sim, já incluir nesta etapa"). Checagem por RECURSO (não por
    dia inteiro pra todo mundo, diferente do feriado do calendário padrão
    mostrado no frontend) — só o consultor ausente fica bloqueado, os
    demais continuam agendáveis normalmente nesse mesmo dia. REJECTED não
    conta (ausência rejeitada é como se não tivesse acontecido, mesmo
    critério de financials_by_task_type/project_burndown em services.py).
    Só entra na criação/na troca de data de um agendamento já existente —
    uma ausência registrada DEPOIS de um agendamento já feito não desfaz
    esse agendamento (mesmo espírito do feriado: "não impede visualizar os
    agendamentos que já existiam ali")."""
    return (
        db.scalar(
            select(Timesheet.id).where(
                Timesheet.resource_id == resource_id,
                Timesheet.date == day,
                Timesheet.absence_type.is_not(None),
                Timesheet.status != TimesheetStatus.REJECTED,
            )
        )
        is not None
    )


def _resolve_schedule_tasks(db: Session, project_id: str, task_ids: list[str], user: User) -> list[Task]:
    """Valida as tarefas vinculadas a um bloco da Agenda (pedido do
    usuário: "adicionar uma ou mais tarefas, sem horas, para a agenda") —
    cada uma precisa existir, pertencer ao MESMO projeto do agendamento e
    não ter tarefas-filhas (mesma regra de "só tarefa-folha" do apontamento
    de horas — ver _resolve_task_and_project em routers/timesheets.py: uma
    tarefa "pai"/resumo de EAP não é um item de trabalho de verdade).
    Ignora id repetido em vez de recusar (lista vem de checkboxes no
    frontend, nunca deveria repetir, mas não há necessidade de travar nisso)."""
    tasks: list[Task] = []
    seen: set[str] = set()
    for task_id in task_ids:
        if task_id in seen:
            continue
        seen.add(task_id)
        task = db.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail=translate("Tarefa não encontrada", user.language))
        if task.project_id != project_id:
            raise HTTPException(status_code=422, detail=translate("Tarefa não pertence ao projeto do agendamento", user.language))
        if db.scalar(select(Task.id).where(Task.parent_task_id == task.id)):
            raise HTTPException(
                status_code=422,
                detail=translate(
                    "Não é possível vincular uma tarefa que tem tarefas-filhas na Agenda — vincule a tarefa-filha", user.language
                ),
            )
        tasks.append(task)
    return tasks


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
    if _check_absence(db, data.resource_id, data.date):
        raise HTTPException(status_code=409, detail=translate("Recurso está ausente nesta data e não pode ser agendado", user.language))
    if _check_overlap(db, data.resource_id, data.date, data.start_time, data.end_time):
        raise HTTPException(status_code=409, detail=translate("Recurso já tem agendamento nesse horário", user.language))
    tasks = _resolve_schedule_tasks(db, data.project_id, data.task_ids, user)
    schedule = ResourceSchedule(**data.model_dump(exclude={"task_ids"}))
    schedule.schedule_tasks = [ResourceScheduleTask(task_id=task.id) for task in tasks]
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
    # task_ids não é coluna de ResourceSchedule (é a lista de ligação
    # ResourceScheduleTask) — tratado à parte abaixo, nunca pelo
    # setattr(schedule, field, value) genérico do final da função.
    task_ids = changes.pop("task_ids", None)
    if "project_id" in changes and not db.get(Project, changes["project_id"]):
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    new_date = changes.get("date", schedule.date)
    new_start = changes.get("start_time", schedule.start_time)
    new_end = changes.get("end_time", schedule.end_time)
    if new_end <= new_start:
        raise HTTPException(status_code=422, detail=translate("Hora final precisa ser depois da hora inicial", user.language))
    # Só checa ausência quando a DATA está mudando (ex.: arrastar-e-soltar
    # pra outro dia) — editar só o horário/descrição de um agendamento que já
    # existia não precisa revalidar isso (ver docstring de _check_absence).
    if "date" in changes and _check_absence(db, schedule.resource_id, new_date):
        raise HTTPException(status_code=409, detail=translate("Recurso está ausente nesta data e não pode ser agendado", user.language))
    if _check_overlap(db, schedule.resource_id, new_date, new_start, new_end, exclude_id=schedule.id):
        raise HTTPException(status_code=409, detail=translate("Recurso já tem agendamento nesse horário", user.language))
    if task_ids is not None:
        project_id_for_tasks = changes.get("project_id", schedule.project_id)
        tasks = _resolve_schedule_tasks(db, project_id_for_tasks, task_ids, user)
        schedule.schedule_tasks = [ResourceScheduleTask(task_id=task.id) for task in tasks]
    elif "project_id" in changes and changes["project_id"] != schedule.project_id:
        # Projeto trocado sem informar task_ids explicitamente — as tarefas
        # vinculadas eram do projeto antigo e não fazem mais sentido aqui.
        schedule.schedule_tasks = []
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
