from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_project_access, require_roles
from ..i18n import t as translate
from ..models import (
    AuditAction,
    Project,
    ProjectStatus,
    Resource,
    ResourceSchedule,
    Task,
    TaskAssignment,
    Timesheet,
    TimesheetStatus,
    User,
    UserRole,
)
from ..schemas import TimesheetCreate, TimesheetRead, TimesheetStatusUpdate

router = APIRouter(tags=["timesheets"])

_MANAGEMENT_ROLES = (UserRole.ADMIN, UserRole.INTERNAL_PM)


def _compute_hours(data: TimesheetCreate, lang) -> Decimal:
    """`hours_spent` nunca é digitado — é sempre Hora Final − Hora Inicial −
    Intervalo, igual ao `sold_value` do projeto (ver create_project).
    Trabalha em minutos inteiros (nunca `float`/`datetime`) — `time` não tem
    fuso nem data, então a diferença em minutos é só aritmética simples;
    nenhum apontamento atravessa a meia-noite (isso seriam dois
    lançamentos)."""
    start_minutes = data.start_time.hour * 60 + data.start_time.minute
    end_minutes = data.end_time.hour * 60 + data.end_time.minute
    if end_minutes <= start_minutes:
        raise HTTPException(status_code=422, detail=translate("Hora final precisa ser depois da hora inicial", lang))
    span_minutes = end_minutes - start_minutes
    if data.break_minutes >= span_minutes:
        raise HTTPException(
            status_code=422,
            detail=translate("Intervalo não pode ser maior ou igual ao tempo entre a hora inicial e a final", lang),
        )
    hours = Decimal(span_minutes - data.break_minutes) / Decimal(60)
    if hours > 24:
        raise HTTPException(status_code=422, detail=translate("Um apontamento não pode passar de 24 horas", lang))
    return hours.quantize(Decimal("0.01"))


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
    # A sessão é criada com autoflush=False (app/database.py) — sem o flush
    # explícito aqui, a mudança de status pendente em `entry` (feita pelo
    # chamador logo antes) ainda não teria ido para o banco, e esta consulta
    # enxergaria o status antigo (ex.: PENDING), somando 0 horas mesmo depois
    # de aprovar o apontamento.
    db.flush()
    hours = db.scalars(
        select(Timesheet.hours_spent).where(
            Timesheet.task_id == task_id, Timesheet.status == TimesheetStatus.APPROVED
        )
    ).all()
    task.actual_hours = sum((Decimal(h) for h in hours), Decimal("0"))


def _resolve_task_and_project(
    data: TimesheetCreate, resource: Resource, user: User, db: Session, *, exclude_timesheet_id: str | None = None
) -> tuple[Task | None, Project | None]:
    """Validações de escopo/projeto ativo/alocação e a checagem de
    apontamento duplicado (mesmo recurso+tarefa+data) — compartilhadas por
    create_timesheet e update_timesheet. `exclude_timesheet_id` tira o
    próprio registro da checagem de duplicado ao editar (senão ele sempre
    "colidiria" consigo mesmo)."""
    task: Task | None = None
    project: Project | None = None

    if data.task_id:
        task = db.get(Task, data.task_id)
        if not task:
            raise HTTPException(status_code=404, detail=translate("Tarefa não encontrada", user.language))
        project = db.get(Project, task.project_id)
        require_project_access(project, user, write=True)
        if project.status != ProjectStatus.ACTIVE:
            raise HTTPException(status_code=422, detail=translate("Só é possível apontar horas em projetos ativos", user.language))

        assignment = db.scalar(
            select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.resource_id == resource.id)
        )
        if not assignment:
            raise HTTPException(status_code=403, detail=translate("Recurso não está alocado nesta tarefa", user.language))

        duplicate_stmt = select(Timesheet).where(
            Timesheet.task_id == task.id,
            Timesheet.resource_id == resource.id,
            Timesheet.date == data.date,
        )
        if exclude_timesheet_id:
            duplicate_stmt = duplicate_stmt.where(Timesheet.id != exclude_timesheet_id)
        duplicate = db.scalar(duplicate_stmt)
        if duplicate:
            raise HTTPException(status_code=409, detail=translate("Já existe um apontamento deste recurso nesta tarefa para esta data", user.language))
    elif data.project_id:
        # Apontamento avulso (sem task na EAP) mas alocado a um projeto —
        # ex.: reunião com o cliente, suporte pontual. Continua exigindo
        # escopo/escrita e projeto ativo, só dispensa TaskAssignment.
        project = db.get(Project, data.project_id)
        if not project:
            raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
        require_project_access(project, user, write=True)
        if project.status != ProjectStatus.ACTIVE:
            raise HTTPException(status_code=422, detail=translate("Só é possível apontar horas em projetos ativos", user.language))
    # else: hora administrativa interna (sem task nem projeto) — qualquer
    # recurso autenticado pode lançar, sem checagem de escopo de cliente.
    return task, project


def _resolve_schedule(
    data: TimesheetCreate, resource: Resource, project: Project | None, user: User, db: Session
) -> tuple[ResourceSchedule | None, bool]:
    """Regra da Agenda (Fase 2 do apontamento): só é "avulso" (exige
    aprovação extra do Administrador, ver update_timesheet_status) um
    apontamento ligado a um projeto em que o recurso NÃO tinha nenhum
    agendamento (ResourceSchedule) naquele dia. Hora administrativa interna
    (sem projeto) nunca entra nessa regra — não existe agenda de projeto pra
    checar. `schedule_id` explícito é só referência para auditoria; a
    checagem real é sempre refeita aqui, nunca confiando no que o cliente
    informou. Compartilhada por create_timesheet e update_timesheet."""
    schedule: ResourceSchedule | None = None
    project_id_for_schedule = project.id if project else None
    unscheduled = False
    if project_id_for_schedule:
        has_schedule = db.scalar(
            select(ResourceSchedule).where(
                ResourceSchedule.resource_id == resource.id,
                ResourceSchedule.project_id == project_id_for_schedule,
                ResourceSchedule.date == data.date,
            )
        )
        unscheduled = has_schedule is None
        if data.schedule_id:
            schedule = db.get(ResourceSchedule, data.schedule_id)
            if not schedule:
                raise HTTPException(status_code=404, detail=translate("Agendamento não encontrado", user.language))
            if schedule.resource_id != resource.id or schedule.project_id != project_id_for_schedule or schedule.date != data.date:
                raise HTTPException(
                    status_code=422,
                    detail=translate("O agendamento informado não corresponde a este recurso/projeto/data", user.language),
                )
    elif data.schedule_id:
        raise HTTPException(status_code=422, detail=translate("schedule_id exige project_id ou task_id", user.language))
    return schedule, unscheduled


def _require_own_editable_entry(timesheet_id: str, resource: Resource, user: User, db: Session) -> Timesheet:
    """Checagens comuns a editar/excluir um apontamento: precisa existir, ser
    do próprio recurso (nunca de outro consultor — isso é para gestor via
    Aprovações pendentes, não aqui) e ainda não ter sido aprovado. Depois de
    aprovado, o apontamento já afeta `Task.actual_hours` e possivelmente
    faturamento — mudar ou apagar silenciosamente quebraria esse número; se
    precisar corrigir um já aprovado, é rejeitar antes (fluxo do gestor).
    Bloqueio mensal (mês fechado) é uma trava futura, ainda não implementada
    — ver pedido do usuário."""
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail=translate("Apontamento não encontrado", user.language))
    if entry.resource_id != resource.id:
        raise HTTPException(status_code=403, detail=translate("Você só pode alterar seus próprios apontamentos", user.language))
    if entry.status == TimesheetStatus.APPROVED:
        raise HTTPException(status_code=422, detail=translate("Um apontamento já aprovado não pode ser alterado ou excluído", user.language))
    return entry


@router.post("/timesheets", response_model=TimesheetRead, status_code=status.HTTP_201_CREATED)
def create_timesheet(data: TimesheetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Timesheet:
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))

    task, project = _resolve_task_and_project(data, resource, user, db)
    hours_spent = _compute_hours(data, user.language)
    schedule, unscheduled = _resolve_schedule(data, resource, project, user, db)

    entry = Timesheet(
        task_id=task.id if task else None,
        project_id=project.id if project else None,
        resource_id=resource.id,
        schedule_id=schedule.id if schedule else None,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        break_minutes=data.break_minutes,
        hours_spent=hours_spent,
        unscheduled=unscheduled,
        description=data.description,
    )
    db.add(entry)
    db.flush()
    record_audit(db, entity_type="timesheet", entity_id=entry.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(entry)
    return entry


@router.put("/timesheets/{timesheet_id}", response_model=TimesheetRead)
def update_timesheet(
    timesheet_id: str, data: TimesheetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Timesheet:
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))
    entry = _require_own_editable_entry(timesheet_id, resource, user, db)

    task, project = _resolve_task_and_project(data, resource, user, db, exclude_timesheet_id=entry.id)
    hours_spent = _compute_hours(data, user.language)
    schedule, unscheduled = _resolve_schedule(data, resource, project, user, db)

    entry.task_id = task.id if task else None
    entry.project_id = project.id if project else None
    entry.schedule_id = schedule.id if schedule else None
    entry.date = data.date
    entry.start_time = data.start_time
    entry.end_time = data.end_time
    entry.break_minutes = data.break_minutes
    entry.hours_spent = hours_spent
    entry.unscheduled = unscheduled
    entry.description = data.description
    # Editar (inclusive um apontamento Rejeitado, pra corrigir e reenviar)
    # sempre volta pro estado Pendente — precisa passar pela aprovação de
    # novo, nunca herda um status antigo que não reflete mais o conteúdo.
    entry.status = TimesheetStatus.PENDING

    record_audit(db, entity_type="timesheet", entity_id=entry.id, action=AuditAction.UPDATE, user_id=user.id)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete("/timesheets/{timesheet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_timesheet(timesheet_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))
    entry = _require_own_editable_entry(timesheet_id, resource, user, db)
    record_audit(db, entity_type="timesheet", entity_id=entry.id, action=AuditAction.DELETE, user_id=user.id)
    db.delete(entry)
    db.commit()


@router.get("/timesheets", response_model=list[TimesheetRead])
def list_timesheets(
    project_id: str | None = None,
    task_id: str | None = None,
    resource_id: str | None = None,
    status_filter: TimesheetStatus | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Timesheet]:
    """`resource_id`/`status_filter` (query `?status_filter=`) são novos —
    permitem "meus apontamentos" (resource_id) e a fila de aprovação
    (status_filter=PENDING), sem precisar de project_id/task_id. Perfil não
    gerencial (fora de ADMIN/INTERNAL_PM) nunca enxerga apontamento de
    outro recurso: `resource_id` é sempre forçado pro recurso do próprio
    usuário, ignorando qualquer valor de terceiro que venha na query."""
    is_manager = user.role in _MANAGEMENT_ROLES
    if not is_manager:
        own_resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
        if not own_resource:
            raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))
        resource_id = own_resource.id

    # outerjoin (não join) porque apontamentos avulsos têm task_id nulo —
    # um INNER JOIN os excluiria até de listagens por project_id, já que
    # esses registros também carregam o project_id diretamente em Timesheet.
    stmt = select(Timesheet).outerjoin(Task, Task.id == Timesheet.task_id)
    if task_id:
        stmt = stmt.where(Timesheet.task_id == task_id)
    elif project_id:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
        require_project_access(project, user)
        stmt = stmt.where(or_(Task.project_id == project_id, Timesheet.project_id == project_id))
    elif not (resource_id or status_filter):
        raise HTTPException(
            status_code=422,
            detail=translate("Informe ao menos um filtro (project_id, task_id, resource_id ou status_filter)", user.language),
        )
    if resource_id:
        stmt = stmt.where(Timesheet.resource_id == resource_id)
    if status_filter:
        stmt = stmt.where(Timesheet.status == status_filter)
    return list(db.scalars(stmt.order_by(Timesheet.date.desc())).all())


@router.patch("/timesheets/{timesheet_id}/status", response_model=TimesheetRead)
def update_timesheet_status(
    timesheet_id: str,
    data: TimesheetStatusUpdate,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> Timesheet:
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail=translate("Apontamento não encontrado", user.language))
    # "Aprovação extra" (Fase 2): um apontamento avulso — sem agendamento
    # correspondente na Agenda — só pode ser APROVADO pelo Administrador;
    # INTERNAL_PM continua podendo rejeitar normalmente (rejeitar nunca
    # precisou de aprovação extra nenhuma).
    if entry.unscheduled and data.status == TimesheetStatus.APPROVED and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail=translate("Apontamento fora da agenda — só o Administrador pode aprová-lo", user.language),
        )
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
