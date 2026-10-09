"""Tickets internos / pendentes (pedido do usuário).

Um consultor registra um incidente ligado a uma TAREFA de um projeto; o
gerente do projeto direciona para outro consultor/desenvolvedor; as
interações (comentários, mudanças de status, tempo apontado) ficam gravadas
no histórico até o SOLICITANTE confirmar a solução.

Fluxo: OPEN -> ASSIGNED -> IN_PROGRESS <-> WAITING_REQUESTER -> RESOLVED ->
CLOSED (só o solicitante fecha; se discordar, reabre = IN_PROGRESS).

Horas: o responsável informa data/hora inicial/final/intervalo no próprio
ticket e o sistema cria o apontamento (Timesheet) na tarefa do ticket, igual
ao apontamento normal (Pendente de aprovação) — ver `log_time`.

Quem vê: Admin/Gerente de Serviços/Diretor Geral veem todos; Gerente de
Projetos vê os dos projetos que gerencia; qualquer perfil interno vê os que
abriu ou recebeu. Perfis do cliente não têm acesso (fluxo interno)."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import ADMIN_LIKE_ROLES, INTERNAL_ROLES, MANAGEMENT_ROLES, get_current_user, require_roles
from ..i18n import t as translate
from ..models import (
    AuditAction,
    Project,
    ProjectStatus,
    Resource,
    Task,
    TaskStatus,
    Ticket,
    TicketCriticality,
    TicketInteraction,
    TicketInteractionKind,
    TicketStatus,
    Timesheet,
    TimesheetStatus,
    User,
    UserRole,
    UserStatus,
)
from ..notifications import notify_ticket_interaction
from ..schemas import (
    TicketAssign,
    TicketAssignee,
    TicketComment,
    TicketCreate,
    TicketCriticalityChange,
    TicketDetail,
    TicketRead,
    TicketStatusChange,
    TicketTimeEntry,
    TimesheetCreate,
)
from .timesheets import create_timesheet_entry

router = APIRouter(tags=["tickets"])

_S = TicketStatus
# Projetos em que ainda faz sentido abrir ticket.
_CLOSED_PROJECT_STATUSES = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED, ProjectStatus.MODELO}


# ---------------------------------------------------------------------------
# Regras de acesso
# ---------------------------------------------------------------------------


def _require_internal(user: User) -> None:
    if user.role not in INTERNAL_ROLES:
        raise HTTPException(status_code=403, detail=translate("Acesso restrito a perfis internos", user.language))


def _can_manage(ticket: Ticket, user: User) -> bool:
    """Gerencia o ticket (direciona, muda criticidade, cancela): perfis
    ADMIN_LIKE sempre; Gerente de Projetos só nos projetos que conduz."""
    if user.role in ADMIN_LIKE_ROLES:
        return True
    return user.role == UserRole.INTERNAL_PM and ticket.project.manager_id == user.id


def _can_view(ticket: Ticket, user: User) -> bool:
    if user.role not in INTERNAL_ROLES:
        return False
    return _can_manage(ticket, user) or user.id in (ticket.requester_id, ticket.assignee_id)


def _get_ticket(db: Session, ticket_id: str, user: User) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket or not _can_view(ticket, user):
        # 404 também para "sem acesso": não revela a existência do ticket.
        raise HTTPException(status_code=404, detail=translate("Ticket não encontrado", user.language))
    return ticket


def _allowed_statuses(ticket: Ticket, user: User) -> list[TicketStatus]:
    """Próximos status que ESTE usuário pode aplicar agora."""
    current = ticket.status
    manager = _can_manage(ticket, user)
    assignee = ticket.assignee_id == user.id
    requester = ticket.requester_id == user.id
    allowed: set[TicketStatus] = set()
    if assignee or manager:
        if current == _S.ASSIGNED:
            allowed.add(_S.IN_PROGRESS)
        elif current == _S.IN_PROGRESS:
            allowed |= {_S.WAITING_REQUESTER, _S.RESOLVED}
        elif current == _S.WAITING_REQUESTER:
            allowed |= {_S.IN_PROGRESS, _S.RESOLVED}
    if requester or manager:
        if current == _S.RESOLVED:
            allowed |= {_S.CLOSED, _S.IN_PROGRESS}
    if manager:
        if current != _S.CLOSED:
            allowed.add(_S.CLOSED)  # cancelamento / encerramento pelo gerente
        else:
            allowed.add(_S.IN_PROGRESS)  # reabertura pelo gerente
    # ordem estável (a do enum)
    return [status_ for status_ in TicketStatus if status_ in allowed and status_ != current]


# ---------------------------------------------------------------------------
# Montagem das respostas
# ---------------------------------------------------------------------------


def _hours_by_ticket(db: Session, ticket_ids: list[str]) -> dict[str, tuple[Decimal, Decimal]]:
    """(horas lançadas não rejeitadas, horas aprovadas) por ticket."""
    totals: dict[str, list[Decimal]] = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    if not ticket_ids:
        return {}
    rows = db.execute(
        select(Timesheet.ticket_id, Timesheet.status, func.sum(Timesheet.hours_spent))
        .where(Timesheet.ticket_id.in_(ticket_ids))
        .group_by(Timesheet.ticket_id, Timesheet.status)
    ).all()
    for ticket_id, ts_status, total in rows:
        total = Decimal(total or 0)
        if ts_status != TimesheetStatus.REJECTED:
            totals[ticket_id][0] += total
        if ts_status == TimesheetStatus.APPROVED:
            totals[ticket_id][1] += total
    return {key: (value[0], value[1]) for key, value in totals.items()}


def _ticket_dict(ticket: Ticket, hours: tuple[Decimal, Decimal]) -> dict:
    task = ticket.task
    parent_name = task.parent.name if task is not None and task.parent is not None else None
    return {
        "id": ticket.id,
        "code": ticket.code,
        "project_id": ticket.project_id,
        "project_code": ticket.project.code,
        "project_name": ticket.project.name,
        "task_id": ticket.task_id,
        "task_wbs": task.wbs_code if task else None,
        "task_name": task.name if task else None,
        "parent_task_name": parent_name,
        "title": ticket.title,
        "description": ticket.description,
        "criticality": ticket.criticality,
        "status": ticket.status,
        "requester_id": ticket.requester_id,
        "requester_name": ticket.requester.name if ticket.requester else None,
        "requester_email": ticket.requester.email if ticket.requester else None,
        "assignee_id": ticket.assignee_id,
        "assignee_name": ticket.assignee.name if ticket.assignee else None,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
        "resolved_at": ticket.resolved_at,
        "closed_at": ticket.closed_at,
        "hours_logged": hours[0],
        "hours_approved": hours[1],
    }


def _detail(db: Session, ticket: Ticket, user: User) -> dict:
    payload = _ticket_dict(ticket, _hours_by_ticket(db, [ticket.id]).get(ticket.id, (Decimal("0"), Decimal("0"))))
    payload["interactions"] = [
        {
            "id": item.id,
            "author_id": item.author_id,
            "author_name": item.author.name if item.author else None,
            "kind": item.kind,
            "message": item.message,
            "from_value": item.from_value,
            "to_value": item.to_value,
            "created_at": item.created_at,
        }
        for item in ticket.interactions
    ]
    manager = _can_manage(ticket, user)
    open_ticket = ticket.status != _S.CLOSED
    payload["allowed_statuses"] = _allowed_statuses(ticket, user)
    payload["can_assign"] = manager and open_ticket
    payload["can_comment"] = open_ticket and _can_view(ticket, user)
    payload["can_log_time"] = open_ticket and (ticket.assignee_id == user.id or user.role in MANAGEMENT_ROLES)
    payload["can_change_criticality"] = manager and open_ticket
    return payload


def _add_interaction(
    db: Session,
    ticket: Ticket,
    user: User | None,
    kind: TicketInteractionKind,
    *,
    message: str | None = None,
    from_value: str | None = None,
    to_value: str | None = None,
) -> TicketInteraction:
    now = datetime.utcnow()
    interaction = TicketInteraction(
        ticket_id=ticket.id,
        author_id=user.id if user else None,
        kind=kind.value,
        message=(message or "").strip() or None,
        from_value=from_value,
        to_value=to_value,
        created_at=now,
    )
    db.add(interaction)
    ticket.updated_at = now
    db.flush()
    return interaction


def _set_status(db: Session, ticket: Ticket, user: User, new_status: TicketStatus, message: str | None = None) -> TicketInteraction:
    old = ticket.status
    ticket.status = new_status.value
    now = datetime.utcnow()
    if new_status == _S.RESOLVED:
        ticket.resolved_at = now
        ticket.closed_at = None
    elif new_status == _S.CLOSED:
        ticket.closed_at = now
    else:
        # reaberto / voltou ao atendimento
        ticket.closed_at = None
        if old in (_S.RESOLVED, _S.CLOSED):
            ticket.resolved_at = None
    return _add_interaction(db, ticket, user, TicketInteractionKind.STATUS, message=message, from_value=old, to_value=new_status.value)


# ---------------------------------------------------------------------------
# Rotas
# ---------------------------------------------------------------------------


def _next_seq(db: Session, year: int) -> int:
    return (db.scalar(select(func.max(Ticket.seq)).where(Ticket.year == year)) or 0) + 1


@router.post("/tickets", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def create_ticket(
    data: TicketCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_internal(user)
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    if project.status in _CLOSED_PROJECT_STATUSES:
        raise HTTPException(status_code=422, detail=translate("Não é possível abrir ticket em projeto concluído, cancelado ou modelo", user.language))
    task = db.get(Task, data.task_id)
    if not task or task.project_id != project.id:
        raise HTTPException(status_code=404, detail=translate("Tarefa não encontrada", user.language))
    if db.scalar(select(Task.id).where(Task.parent_task_id == task.id)):
        raise HTTPException(
            status_code=422,
            detail=translate("Selecione uma tarefa sem tarefas-filhas — o tempo do ticket é apontado nela", user.language),
        )
    if task.status == TaskStatus.CLOSED:
        raise HTTPException(status_code=422, detail=translate("Não é possível abrir ticket em uma tarefa desativada", user.language))

    now = datetime.utcnow()
    ticket: Ticket | None = None
    for _ in range(5):
        seq = _next_seq(db, now.year)
        candidate = Ticket(
            code=f"TK-{now.year}-{seq:04d}",
            year=now.year,
            seq=seq,
            project_id=project.id,
            task_id=task.id,
            title=data.title.strip(),
            description=data.description.strip(),
            criticality=data.criticality.value,
            status=_S.OPEN.value,
            requester_id=user.id,
            created_at=now,
            updated_at=now,
        )
        try:
            db.add(candidate)
            db.flush()
        except IntegrityError:
            # Outro ticket pegou o mesmo número ao mesmo tempo — descarta e
            # tenta o próximo. O rollback é seguro: até aqui a requisição só
            # leu dados (nada mais pendente na sessão), e o projeto/tarefa
            # são relidos abaixo pelo `db.get`.
            db.rollback()
            project = db.get(Project, data.project_id)
            task = db.get(Task, data.task_id)
            continue
        ticket = candidate
        break
    if ticket is None:
        raise HTTPException(status_code=409, detail=translate("Não foi possível gerar o número do ticket. Tente novamente.", user.language))

    interaction = _add_interaction(db, ticket, user, TicketInteractionKind.CREATED, to_value=data.criticality.value)
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(ticket)
    background_tasks.add_task(notify_ticket_interaction, interaction.id)
    return _detail(db, ticket, user)


@router.get("/tickets", response_model=list[TicketRead])
def list_tickets(
    project_id: str | None = None,
    task_id: str | None = None,
    status_filter: TicketStatus | None = None,
    criticality: TicketCriticality | None = None,
    scope: str = "all",
    open_only: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """`scope`: `all` (tudo que o usuário pode ver), `requested` (abertos
    por mim) ou `assigned` (direcionados a mim)."""
    _require_internal(user)
    query = select(Ticket).join(Project, Project.id == Ticket.project_id)
    if user.role not in ADMIN_LIKE_ROLES:
        conditions = [Ticket.requester_id == user.id, Ticket.assignee_id == user.id]
        if user.role == UserRole.INTERNAL_PM:
            conditions.append(Project.manager_id == user.id)
        query = query.where(or_(*conditions))
    if scope == "requested":
        query = query.where(Ticket.requester_id == user.id)
    elif scope == "assigned":
        query = query.where(Ticket.assignee_id == user.id)
    if project_id:
        query = query.where(Ticket.project_id == project_id)
    if task_id:
        query = query.where(Ticket.task_id == task_id)
    if status_filter:
        query = query.where(Ticket.status == status_filter.value)
    if criticality:
        query = query.where(Ticket.criticality == criticality.value)
    if open_only:
        query = query.where(Ticket.status != _S.CLOSED.value)
    tickets = list(db.scalars(query.order_by(Ticket.created_at.desc())).all())
    hours = _hours_by_ticket(db, [ticket.id for ticket in tickets])
    zero = (Decimal("0"), Decimal("0"))
    return [_ticket_dict(ticket, hours.get(ticket.id, zero)) for ticket in tickets]


@router.get("/tickets/assignees", response_model=list[TicketAssignee])
def list_ticket_assignees(
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)), db: Session = Depends(get_db)
) -> list[User]:
    """Quem pode receber um ticket: usuário interno ativo com Recurso
    (só quem tem Recurso consegue apontar horas)."""
    return list(
        db.scalars(
            select(User)
            .join(Resource, Resource.user_id == User.id)
            .where(User.status == UserStatus.ACTIVE, User.role.in_(INTERNAL_ROLES))
            .order_by(User.name)
        ).all()
    )


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def read_ticket(ticket_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    _require_internal(user)
    return _detail(db, _get_ticket(db, ticket_id, user), user)


@router.post("/tickets/{ticket_id}/assign", response_model=TicketDetail)
def assign_ticket(
    ticket_id: str,
    data: TicketAssign,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Direciona (ou redireciona) o ticket para um consultor/desenvolvedor."""
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    if not _can_manage(ticket, user):
        raise HTTPException(status_code=403, detail=translate("Só o gerente do projeto pode direcionar o ticket", user.language))
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Ticket fechado não pode ser direcionado", user.language))
    assignee = db.get(User, data.assignee_id)
    has_resource = assignee is not None and db.scalar(select(Resource.id).where(Resource.user_id == assignee.id)) is not None
    if not assignee or assignee.status != UserStatus.ACTIVE or assignee.role not in INTERNAL_ROLES or not has_resource:
        raise HTTPException(
            status_code=422,
            detail=translate("O responsável precisa ser um usuário interno ativo com Recurso", user.language),
        )
    if ticket.assignee_id == assignee.id:
        raise HTTPException(status_code=422, detail=translate("O ticket já está direcionado a este usuário", user.language))

    previous_name = ticket.assignee.name if ticket.assignee else None
    ticket.assignee_id = assignee.id
    if ticket.status == _S.OPEN.value:
        ticket.status = _S.ASSIGNED.value
    interaction = _add_interaction(
        db, ticket, user, TicketInteractionKind.ASSIGNMENT, message=data.message, from_value=previous_name, to_value=assignee.name
    )
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.UPDATE, user_id=user.id, details={"assignee_id": assignee.id})
    db.commit()
    db.refresh(ticket)
    background_tasks.add_task(notify_ticket_interaction, interaction.id)
    return _detail(db, ticket, user)


@router.post("/tickets/{ticket_id}/status", response_model=TicketDetail)
def change_ticket_status(
    ticket_id: str,
    data: TicketStatusChange,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    if data.status not in _allowed_statuses(ticket, user):
        raise HTTPException(status_code=422, detail=translate("Mudança de status não permitida para este ticket", user.language))
    message = (data.message or "").strip()
    # Pedir informação, concluir, reabrir e cancelar exigem explicação.
    needs_message = data.status in (_S.WAITING_REQUESTER, _S.RESOLVED) or (
        data.status == _S.IN_PROGRESS and ticket.status in (_S.RESOLVED.value, _S.CLOSED.value)
    ) or (data.status == _S.CLOSED and ticket.status != _S.RESOLVED.value)
    if needs_message and not message:
        raise HTTPException(status_code=422, detail=translate("Informe uma mensagem para esta mudança de status", user.language))
    interaction = _set_status(db, ticket, user, data.status, message)
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.UPDATE, user_id=user.id, details={"status": data.status.value})
    db.commit()
    db.refresh(ticket)
    background_tasks.add_task(notify_ticket_interaction, interaction.id)
    return _detail(db, ticket, user)


@router.post("/tickets/{ticket_id}/comments", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def comment_ticket(
    ticket_id: str,
    data: TicketComment,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Ticket fechado não aceita novas interações", user.language))
    interaction = _add_interaction(db, ticket, user, TicketInteractionKind.COMMENT, message=data.message)
    db.flush()
    notify_ids = [interaction.id]
    # O solicitante respondeu o que o responsável pediu: volta ao atendimento.
    if ticket.status == _S.WAITING_REQUESTER.value and ticket.requester_id == user.id:
        status_interaction = _set_status(db, ticket, user, _S.IN_PROGRESS)
        notify_ids.append(status_interaction.id)
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.UPDATE, user_id=user.id, details={"comment": True})
    db.commit()
    db.refresh(ticket)
    for interaction_id in notify_ids[:1]:
        background_tasks.add_task(notify_ticket_interaction, interaction_id)
    return _detail(db, ticket, user)


@router.post("/tickets/{ticket_id}/criticality", response_model=TicketDetail)
def change_ticket_criticality(
    ticket_id: str,
    data: TicketCriticalityChange,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    if not _can_manage(ticket, user):
        raise HTTPException(status_code=403, detail=translate("Só o gerente do projeto pode alterar a criticidade", user.language))
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Ticket fechado não aceita novas interações", user.language))
    if ticket.criticality == data.criticality.value:
        raise HTTPException(status_code=422, detail=translate("A criticidade já é essa", user.language))
    old = ticket.criticality
    ticket.criticality = data.criticality.value
    interaction = _add_interaction(
        db, ticket, user, TicketInteractionKind.CRITICALITY, message=data.message, from_value=old, to_value=data.criticality.value
    )
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.UPDATE, user_id=user.id, details={"criticality": data.criticality.value})
    db.commit()
    db.refresh(ticket)
    background_tasks.add_task(notify_ticket_interaction, interaction.id)
    return _detail(db, ticket, user)


@router.post("/tickets/{ticket_id}/time", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def log_time(
    ticket_id: str,
    data: TicketTimeEntry,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Apontamento de tempo feito de dentro do ticket: cria um Timesheet na
    TAREFA do ticket (mesmas regras e aprovação do apontamento normal) e
    registra a linha "tempo apontado" no histórico."""
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Não é possível apontar horas em um ticket fechado", user.language))
    if ticket.assignee_id != user.id and user.role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail=translate("Só o responsável pelo ticket pode apontar horas nele", user.language))
    if not ticket.task_id:
        raise HTTPException(status_code=422, detail=translate("O ticket não tem tarefa vinculada para receber o apontamento", user.language))

    entry = create_timesheet_entry(
        TimesheetCreate(
            task_id=ticket.task_id,
            ticket_id=ticket.id,
            date=data.date,
            start_time=data.start_time,
            end_time=data.end_time,
            break_minutes=data.break_minutes,
            description=data.description,
            task_progress_percentage=data.task_progress_percentage,
        ),
        user,
        db,
    )
    period = f"{data.date.strftime('%d/%m/%Y')} {data.start_time.strftime('%H:%M')}-{data.end_time.strftime('%H:%M')}"
    _add_interaction(
        db, ticket, user, TicketInteractionKind.TIME, message=data.description, from_value=period, to_value=str(entry.hours_spent)
    )
    # Começou a trabalhar: ASSIGNED vira IN_PROGRESS sozinho.
    if ticket.status == _S.ASSIGNED.value:
        _set_status(db, ticket, user, _S.IN_PROGRESS)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)
