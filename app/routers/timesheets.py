from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import ADMIN_LIKE_ROLES, MANAGEMENT_ROLES, get_current_user, require_project_access, require_roles
from ..i18n import t as translate
from ..models import (
    AbsenceType,
    AuditAction,
    Client,
    Project,
    ProjectResource,
    ProjectStatus,
    Resource,
    ResourceSchedule,
    Task,
    TaskAssignment,
    TaskStatus,
    Ticket,
    TicketStatus,
    Timesheet,
    TimesheetStatus,
    User,
    UserRole,
    WorkClassification,
)
from ..schemas import TimesheetCreate, TimesheetRead, TimesheetStatusUpdate

router = APIRouter(tags=["timesheets"])

_MANAGEMENT_ROLES = MANAGEMENT_ROLES


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


def _ticket_authorizes_time(data: TimesheetCreate, task: Task, user: User, db: Session) -> bool:
    """O apontamento cita um ticket DESTA tarefa em que o usuário é o
    responsável (ou é perfil de gestão)? Só decide a dispensa da alocação;
    as demais regras (ticket fechado etc.) continuam em `_validate_ticket`."""
    if not data.ticket_id:
        return False
    ticket = db.get(Ticket, data.ticket_id)
    if not ticket or ticket.task_id != task.id:
        return False
    return ticket.assignee_id == user.id or user.role in _MANAGEMENT_ROLES


def _resolve_task_and_project(
    data: TimesheetCreate, resource: Resource, user: User, db: Session
) -> tuple[Task | None, Project | None]:
    """Validações de escopo/projeto ativo/alocação — compartilhadas por
    create_timesheet e update_timesheet. Mais de um apontamento do mesmo
    recurso na mesma tarefa no mesmo dia é permitido de propósito (ex.:
    dois períodos de trabalho no mesmo dia) — não há checagem de
    duplicado aqui."""
    task: Task | None = None
    project: Project | None = None

    # "Traslado" (deslocamento, pedido do usuário) — sempre vinculado a um
    # projeto, nunca a uma tarefa específica (decisão confirmada com o
    # usuário). Checado antes de tudo, pra nunca cair no ramo de task_id
    # abaixo com os dois marcados ao mesmo tempo.
    if data.is_transit:
        if data.task_id:
            raise HTTPException(status_code=422, detail=translate("Traslado não pode ter uma tarefa específica vinculada", user.language))
        if not data.project_id:
            raise HTTPException(status_code=422, detail=translate("Traslado precisa de um projeto selecionado", user.language))

    # "Ausência da empresa" (Férias/Licença Médica/Licença Maternidade/
    # Ausência/Folga, pedido do usuário) — o espelho do Traslado acima:
    # SEMPRE custo interno da empresa, nunca de um cliente/projeto (decisão
    # confirmada com o usuário), então nunca aceita task_id nem project_id
    # junto, nem Traslado ao mesmo tempo (os dois são mutuamente exclusivos
    # — um apontamento não pode ser "ausência" e "deslocamento" ao mesmo
    # tempo). Checado antes do ramo de task_id/project_id abaixo pelo mesmo
    # motivo do Traslado.
    if data.absence_type:
        if data.is_transit:
            raise HTTPException(status_code=422, detail=translate("Ausência não pode ser marcada como Traslado ao mesmo tempo", user.language))
        if data.task_id:
            raise HTTPException(status_code=422, detail=translate("Ausência não pode ter uma tarefa vinculada", user.language))
        if data.project_id:
            raise HTTPException(status_code=422, detail=translate("Ausência não pode ter um projeto vinculado — é sempre custo interno da empresa", user.language))

    if data.task_id:
        task = db.get(Task, data.task_id)
        if not task:
            raise HTTPException(status_code=404, detail=translate("Tarefa não encontrada", user.language))
        # Tarefa "pai"/resumo de EAP (tem tarefas-filhas) — pedido do
        # usuário: apontamento só nas tarefas-filha, nunca na tarefa-pai que
        # só resume o grupo (mesma checagem de Task.parent_task_id usada em
        # delete_task, routers/tasks.py).
        if db.scalar(select(Task.id).where(Task.parent_task_id == task.id)):
            raise HTTPException(
                status_code=422,
                detail=translate("Não é possível apontar horas em uma tarefa que tem tarefas-filhas — aponte na tarefa-filha", user.language),
            )
        project = db.get(Project, task.project_id)
        require_project_access(project, user, write=True)
        if project.status != ProjectStatus.ACTIVE:
            raise HTTPException(status_code=422, detail=translate("Só é possível apontar horas em projetos ativos", user.language))
        # "Desativar tarefa" (CLOSED) bloqueia novo apontamento nela, igual a
        # um projeto inativo — pedido do usuário (ver TaskStatus em models.py).
        if task.status == TaskStatus.CLOSED:
            raise HTTPException(status_code=422, detail=translate("Não é possível apontar horas em uma tarefa desativada", user.language))

        # O gerente do projeto (Project.manager_id) sempre pode apontar
        # horas em qualquer tarefa do próprio projeto, alocado ou não
        # (pedido do usuário — encontrou o caso de criar uma tarefa de
        # Gestão, ser o gerente do projeto, e mesmo assim levar 403 até
        # também se vincular como Recurso do projeto: "não deveria tomar a
        # regra do gerente do projeto?"). Só dispensa a checagem de
        # alocação abaixo — projeto inativo e demais validações continuam
        # valendo normalmente pra ele também.
        is_project_manager = project.manager_id == resource.user_id

        assignment = db.scalar(
            select(TaskAssignment).where(TaskAssignment.task_id == task.id, TaskAssignment.resource_id == resource.id)
        )
        # Exceção dos tickets: o responsável do ticket (ou um perfil de
        # gestão) pode apontar na tarefa do ticket mesmo sem estar alocado
        # nela nem no projeto — quem é acionado para resolver um incidente
        # nem sempre faz parte do projeto. O apontamento segue o fluxo normal
        # (Pendente de aprovação; sem agenda no dia, exige aprovação de
        # Administrador, ver _resolve_schedule).
        ticket_authorizes = _ticket_authorizes_time(data, task, user, db)
        if not assignment and not is_project_manager and not ticket_authorizes:
            # Busca em cascata (pedido do usuário): "sempre busca primeiro
            # na tarefa e depois no projeto". Este recurso não está alocado
            # NESTA tarefa — mas se a tarefa não tem NENHUM recurso alocado
            # (não foi restrita a ninguém em particular), cai pro vínculo
            # do recurso com o projeto inteiro (ProjectResource, "Recursos
            # do projeto" na tela de Projeto). Uma tarefa que já tem
            # alocação própria (pra outro recurso) continua fechada só pra
            # quem está nela — o vínculo de projeto nunca abre uma tarefa
            # que o PM deixou restrita de propósito.
            task_has_any_assignment = db.scalar(select(TaskAssignment.id).where(TaskAssignment.task_id == task.id)) is not None
            resource_linked_to_project = not task_has_any_assignment and (
                db.scalar(
                    select(ProjectResource).where(
                        ProjectResource.project_id == project.id, ProjectResource.resource_id == resource.id
                    )
                )
                is not None
            )
            if not resource_linked_to_project:
                raise HTTPException(status_code=403, detail=translate("Recurso não está alocado nesta tarefa nem no projeto", user.language))
    elif data.project_id:
        # Chega aqui com project_id setado e task_id vazio — é o Traslado
        # (is_transit=True, já validado no bloco do topo) OU o antigo
        # "apontamento avulso" (projeto sem tarefa, ex.: reunião com
        # cliente). Continua exigindo escopo/escrita e projeto ativo, só
        # dispensa TaskAssignment.
        project = db.get(Project, data.project_id)
        if not project:
            raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
        require_project_access(project, user, write=True)
        if project.status != ProjectStatus.ACTIVE:
            raise HTTPException(status_code=422, detail=translate("Só é possível apontar horas em projetos ativos", user.language))
        if not data.is_transit:
            # Pedido do usuário: reverte a permissão de "avulso" (Fase 2) —
            # um projeto selecionado sem Traslado agora EXIGE uma tarefa.
            # TASK_TYPE_LABELS.ADHOC e o bucket "ADHOC" de
            # financials_by_task_type (services.py) continuam existindo só
            # para exibir registros antigos criados antes desta regra, não
            # para permitir criar novos.
            raise HTTPException(
                status_code=422,
                detail=translate("Selecione uma tarefa ou marque Traslado — não é possível apontar direto no projeto", user.language),
            )
    # else: hora administrativa interna (sem task nem projeto) — qualquer
    # recurso autenticado pode lançar, sem checagem de escopo de cliente.
    # Ausência cai aqui também (task/project continuam None pela checagem
    # acima, que já garantiu que nenhum dos dois veio preenchido).
    return task, project


def _validate_rework(data: TimesheetCreate, task: Task | None, user: User) -> None:
    """"% de Avanço da Tarefa" e o classificador Normal/Retrabalho (pedido
    do usuário) só fazem sentido num apontamento vinculado a uma tarefa do
    projeto (task_id setado) — Traslado/Ausência/hora interna não tem
    tarefa pra avançar nem pra "retrabalhar". Quando Retrabalho, exige pelo
    menos um motivo da lista fixa (ReworkReason); quando Normal (ou
    omitido — tratado como Normal por padrão), não aceita motivo nenhum.
    Chamada depois de `_resolve_task_and_project`, que já resolveu `task`
    com todas as outras validações de escopo/projeto ativo/alocação."""
    if not task:
        if data.work_classification is not None:
            raise HTTPException(
                status_code=422,
                detail=translate("O classificador Normal/Retrabalho só é aceito em apontamento de tarefa do projeto", user.language),
            )
        if data.rework_reasons:
            raise HTTPException(
                status_code=422,
                detail=translate("Motivo de retrabalho só é aceito em apontamento de tarefa do projeto", user.language),
            )
        if data.task_progress_percentage is not None:
            raise HTTPException(
                status_code=422,
                detail=translate("% de Avanço da Tarefa só é aceito em apontamento de tarefa do projeto", user.language),
            )
        return

    classification = data.work_classification or WorkClassification.NORMAL
    if classification == WorkClassification.REWORK:
        if not data.rework_reasons:
            raise HTTPException(status_code=422, detail=translate("Selecione ao menos um motivo de retrabalho", user.language))
    elif data.rework_reasons:
        raise HTTPException(
            status_code=422,
            detail=translate("Motivo de retrabalho só é aceito quando o apontamento é classificado como Retrabalho", user.language),
        )


def _apply_task_progress(entry: Timesheet, task: Task | None) -> None:
    """Espelha `Timesheet.task_progress_percentage` (quando informado) em
    `Task.progress_percentage` — o apontamento é justamente o momento em
    que o consultor reporta o avanço da tarefa (pedido do usuário). Sem
    valor informado, não mexe no progresso já registrado na tarefa."""
    if task and entry.task_progress_percentage is not None:
        task.progress_percentage = entry.task_progress_percentage


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


def _validate_ticket(
    data: TimesheetCreate, task: Task | None, user: User, db: Session, keep_ticket_id: str | None = None
) -> Ticket | None:
    """Ticket interno (pendente) informado no apontamento: precisa existir,
    não estar fechado, ser da MESMA tarefa do apontamento e o usuário ser o
    responsável do ticket (ou um perfil de gestão). Sem ticket_id, nada a
    validar. `keep_ticket_id` = ticket que o apontamento JÁ tinha (edição): se
    continua o mesmo, só a regra da tarefa vale — editar um apontamento antigo
    não pode ser bloqueado porque o ticket depois fechou."""
    if not data.ticket_id:
        return None
    ticket = db.get(Ticket, data.ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail=translate("Ticket não encontrado", user.language))
    if not task or ticket.task_id != task.id:
        raise HTTPException(status_code=422, detail=translate("O ticket pertence a outra tarefa — aponte na tarefa do ticket", user.language))
    if data.ticket_id == keep_ticket_id:
        return ticket
    if ticket.status == TicketStatus.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Não é possível apontar horas em um ticket fechado", user.language))
    if ticket.assignee_id != user.id and user.role not in _MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail=translate("Só o responsável pelo ticket pode apontar horas nele", user.language))
    return ticket


def _require_own_editable_entry(timesheet_id: str, resource: Resource, user: User, db: Session) -> Timesheet:
    """Checagem comum a editar/excluir um apontamento: precisa existir e ser
    do próprio recurso (nunca de outro consultor — isso é para gestor via
    Aprovações pendentes, não aqui). Decisão confirmada com o usuário:
    Aprovado/Rejeitado também podem ser alterados/excluídos (editar sempre
    volta pra Pendente, ver update_timesheet) — antes disso um Aprovado
    ficava travado aqui, porque já tinha afetado `Task.actual_hours`; agora
    quem chama depois de editar/excluir recalcula esse campo (ver
    `_recalculate_actual_hours` em update_timesheet/delete_timesheet) em vez
    de proibir a ação. O bloqueio real (mês fechado) é uma trava futura,
    ainda não implementada — é aqui que ela vai entrar."""
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail=translate("Apontamento não encontrado", user.language))
    if entry.resource_id != resource.id:
        raise HTTPException(status_code=403, detail=translate("Você só pode alterar seus próprios apontamentos", user.language))
    return entry


def create_timesheet_entry(data: TimesheetCreate, user: User, db: Session) -> Timesheet:
    """Cria o apontamento (flush + auditoria) SEM dar commit — quem chama
    decide quando commitar. Compartilhada por POST /timesheets e pelo
    apontamento de tempo feito de dentro de um ticket (routers/tickets.py),
    que precisa gravar o histórico do ticket na mesma transação."""
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))

    task, project = _resolve_task_and_project(data, resource, user, db)
    ticket = _validate_ticket(data, task, user, db)
    _validate_rework(data, task, user)
    hours_spent = _compute_hours(data, user.language)
    schedule, unscheduled = _resolve_schedule(data, resource, project, user, db)

    entry = Timesheet(
        task_id=task.id if task else None,
        project_id=project.id if project else None,
        resource_id=resource.id,
        schedule_id=schedule.id if schedule else None,
        ticket_id=ticket.id if ticket else None,
        date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        break_minutes=data.break_minutes,
        hours_spent=hours_spent,
        unscheduled=unscheduled,
        is_transit=data.is_transit,
        absence_type=data.absence_type,
        task_progress_percentage=data.task_progress_percentage if task else None,
        work_classification=(data.work_classification or WorkClassification.NORMAL) if task else None,
        rework_reasons=[reason.value for reason in data.rework_reasons] if (task and data.rework_reasons) else None,
        description=data.description,
    )
    db.add(entry)
    _apply_task_progress(entry, task)
    db.flush()
    record_audit(db, entity_type="timesheet", entity_id=entry.id, action=AuditAction.CREATE, user_id=user.id)
    return entry


@router.post("/timesheets", response_model=TimesheetRead, status_code=status.HTTP_201_CREATED)
def create_timesheet(data: TimesheetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Timesheet:
    entry = create_timesheet_entry(data, user, db)
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
    # Guarda a tarefa ANTES de sobrescrever entry.task_id abaixo — se o
    # apontamento editado estava Aprovado numa tarefa e o usuário troca de
    # tarefa (ou tira a tarefa), é essa tarefa antiga que precisa recalcular
    # Task.actual_hours pra não ficar com um total inflado (ver
    # _recalculate_actual_hours no final).
    old_task_id = entry.task_id

    task, project = _resolve_task_and_project(data, resource, user, db)
    ticket = _validate_ticket(data, task, user, db, keep_ticket_id=entry.ticket_id)
    _validate_rework(data, task, user)
    hours_spent = _compute_hours(data, user.language)
    schedule, unscheduled = _resolve_schedule(data, resource, project, user, db)

    entry.ticket_id = ticket.id if ticket else None
    entry.task_id = task.id if task else None
    entry.project_id = project.id if project else None
    entry.schedule_id = schedule.id if schedule else None
    entry.date = data.date
    entry.start_time = data.start_time
    entry.end_time = data.end_time
    entry.break_minutes = data.break_minutes
    entry.hours_spent = hours_spent
    entry.unscheduled = unscheduled
    entry.is_transit = data.is_transit
    entry.absence_type = data.absence_type
    entry.task_progress_percentage = data.task_progress_percentage if task else None
    entry.work_classification = (data.work_classification or WorkClassification.NORMAL) if task else None
    entry.rework_reasons = [reason.value for reason in data.rework_reasons] if (task and data.rework_reasons) else None
    entry.description = data.description
    _apply_task_progress(entry, task)
    # Editar (inclusive um apontamento Aprovado ou Rejeitado, pra corrigir e
    # reenviar) sempre volta pro estado Pendente — precisa passar pela
    # aprovação de novo, nunca herda um status antigo que não reflete mais o
    # conteúdo.
    entry.status = TimesheetStatus.PENDING

    # Como o status vira Pendente (nunca Aprovado), esta chamada nunca soma
    # o próprio `entry` de volta — só existe pra TIRAR a hora antiga da
    # tarefa antiga quando o apontamento editado estava Aprovado antes.
    _recalculate_actual_hours(db, old_task_id)
    if entry.task_id != old_task_id:
        _recalculate_actual_hours(db, entry.task_id)

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
    task_id = entry.task_id
    record_audit(db, entity_type="timesheet", entity_id=entry.id, action=AuditAction.DELETE, user_id=user.id)
    db.delete(entry)
    # Se o apontamento excluído estava Aprovado, Task.actual_hours ficaria
    # inflado (contando uma linha que não existe mais) sem este recálculo —
    # antes disso era impossível excluir um Aprovado, então isto nunca foi
    # necessário aqui.
    _recalculate_actual_hours(db, task_id)
    db.commit()


@router.get("/timesheets", response_model=list[TimesheetRead])
def list_timesheets(
    project_id: str | None = None,
    task_id: str | None = None,
    resource_id: str | None = None,
    client_id: str | None = None,
    status_filter: TimesheetStatus | None = None,
    start: date | None = None,
    end: date | None = None,
    has_absence: bool | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Timesheet]:
    """`resource_id`/`status_filter` (query `?status_filter=`) são novos —
    permitem "meus apontamentos" (resource_id) e a fila de aprovação
    (status_filter=PENDING), sem precisar de project_id/task_id. Perfil não
    gerencial (fora de ADMIN/INTERNAL_PM) nunca enxerga apontamento de
    outro recurso: `resource_id` é sempre forçado pro recurso do próprio
    usuário, ignorando qualquer valor de terceiro que venha na query.

    `start`/`end` (pedido do usuário: filtro por período na lista de
    apontamentos, tanto "Meus apontamentos" quanto Aprovações pendentes)
    filtram por `Timesheet.date`, inclusive nos dois extremos — igual ao
    padrão já usado em GET /reports/service-orders.

    `client_id` (pedido do usuário: filtro por cliente em "Meus
    apontamentos") não existe direto em Timesheet — resolve pra um
    subquery com os `project_id` do cliente e aplica o mesmo OR
    Task.project_id/Timesheet.project_id usado no filtro por projeto logo
    abaixo, pra pegar tanto apontamento em tarefa quanto avulso.

    Fila de aprovação (status_filter=PENDING) pra INTERNAL_PM só traz os
    projetos onde ele é o gerente (Project.manager_id) — pedido do
    usuário: antes qualquer INTERNAL_PM via TODO apontamento pendente do
    sistema inteiro, não só dos projetos que ele conduz. ADMIN_LIKE_ROLES
    (Administrador, Gerente de Serviços, Diretor Geral) continuam vendo
    tudo, sem essa restrição — são os únicos perfis que podem aprovar
    apontamento "fora da agenda" (ver update_timesheet_status abaixo),
    então precisam enxergar a fila inteira mesmo em projeto que não
    gerenciam.

    `has_absence` (pedido do usuário: bloquear a Agenda de consultores em
    dia de ausência) filtra só apontamentos com `absence_type` setado
    (True) ou só sem (False) — usado pela tela de Agenda pra descobrir, num
    período, quais recursos têm ausência registrada antes de permitir um
    novo agendamento (ver ScheduleFormModal/MoveScheduleConfirmModal em
    SchedulesPage.jsx)."""
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
    elif not (resource_id or client_id or status_filter or start or end or has_absence is not None):
        raise HTTPException(
            status_code=422,
            detail=translate(
                "Informe ao menos um filtro (project_id, task_id, resource_id, client_id, status_filter, start ou end)", user.language
            ),
        )
    if resource_id:
        stmt = stmt.where(Timesheet.resource_id == resource_id)
    if client_id:
        if not db.get(Client, client_id):
            raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", user.language))
        client_project_ids = select(Project.id).where(Project.client_id == client_id)
        stmt = stmt.where(or_(Task.project_id.in_(client_project_ids), Timesheet.project_id.in_(client_project_ids)))
    if status_filter:
        stmt = stmt.where(Timesheet.status == status_filter)
    if status_filter == TimesheetStatus.PENDING and user.role == UserRole.INTERNAL_PM:
        managed_project_ids = select(Project.id).where(Project.manager_id == user.id)
        stmt = stmt.where(or_(Task.project_id.in_(managed_project_ids), Timesheet.project_id.in_(managed_project_ids)))
    if start:
        stmt = stmt.where(Timesheet.date >= start)
    if end:
        stmt = stmt.where(Timesheet.date <= end)
    if has_absence is True:
        stmt = stmt.where(Timesheet.absence_type.is_not(None))
    elif has_absence is False:
        stmt = stmt.where(Timesheet.absence_type.is_(None))
    return list(db.scalars(stmt.order_by(Timesheet.date.desc())).all())


@router.patch("/timesheets/{timesheet_id}/status", response_model=TimesheetRead)
def update_timesheet_status(
    timesheet_id: str,
    data: TimesheetStatusUpdate,
    user: User = Depends(require_roles(*_MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> Timesheet:
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail=translate("Apontamento não encontrado", user.language))
    # "Aprovação extra" (Fase 2): um apontamento avulso — sem agendamento
    # correspondente na Agenda — só pode ser APROVADO por ADMIN_LIKE_ROLES
    # (Administrador, Gerente de Serviços, Diretor Geral); INTERNAL_PM
    # continua podendo rejeitar normalmente (rejeitar nunca precisou de
    # aprovação extra nenhuma).
    if entry.unscheduled and data.status == TimesheetStatus.APPROVED and user.role not in ADMIN_LIKE_ROLES:
        raise HTTPException(
            status_code=403,
            detail=translate("Apontamento fora da agenda — só Administrador, Gerente de Serviços ou Diretor Geral podem aprová-lo", user.language),
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
