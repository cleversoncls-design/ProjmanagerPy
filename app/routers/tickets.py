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

import os
import uuid
from collections import defaultdict
from datetime import datetime, time, timezone
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..ics import app_timezone
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
    TicketAttachment,
    TicketCriticality,
    TicketInteraction,
    TicketInteractionKind,
    TicketStatus,
    TicketWorkSession,
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
    TicketIndicators,
    TicketRead,
    TicketStatusChange,
    TicketTimeEntry,
    TicketWorkFinish,
    TimesheetCreate,
)
from .timesheets import create_timesheet_entry

router = APIRouter(tags=["tickets"])

_S = TicketStatus
# Projetos em que ainda faz sentido abrir ticket.
_CLOSED_PROJECT_STATUSES = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED, ProjectStatus.MODELO}

# --- Anexos -----------------------------------------------------------------
# Pasta dos arquivos (volume do Docker, ver docker-compose.yml). Lida a cada
# chamada (`_upload_dir`) para os testes poderem trocar o valor.
UPLOADS_DIR = Path(os.getenv("UPLOADS_DIR", "/app/uploads"))
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # por arquivo
MAX_FILES_PER_UPLOAD = 5  # por envio
MAX_ATTACHMENTS_PER_TICKET = 10
# extensão -> tipo MIME (o tipo informado pelo navegador nunca é confiado).
ALLOWED_ATTACHMENT_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "pdf": "application/pdf",
    "txt": "text/plain",
    "log": "text/plain",
    "csv": "text/csv",
    "json": "application/json",
    "xml": "application/xml",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "zip": "application/zip",
}
# Assinatura (primeiros bytes) das extensões em que ela é fixa: barra arquivo
# renomeado (ex.: executável chamado .png).
_SIGNATURES = {
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "pdf": (b"%PDF-",),
    "xlsx": (b"PK\x03\x04",),
    "docx": (b"PK\x03\x04",),
    "zip": (b"PK\x03\x04", b"PK\x05\x06"),
    "xls": (b"\xd0\xcf\x11\xe0",),
    "doc": (b"\xd0\xcf\x11\xe0",),
}


def _upload_dir() -> Path:
    return UPLOADS_DIR


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
    if requester and current in (_S.IN_PROGRESS, _S.WAITING_REQUESTER):
        # O solicitante recebeu o retorno e confirma que resolveu: fecha o
        # ticket direto, sem esperar o responsável marcar "Resolvido".
        allowed.add(_S.CLOSED)
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
        "client_id": ticket.project.client_id,
        "client_name": ticket.project.client.legal_name if ticket.project.client else None,
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


def _active_session(db: Session, user: User) -> TicketWorkSession | None:
    return db.scalar(
        select(TicketWorkSession).where(TicketWorkSession.user_id == user.id, TicketWorkSession.ended_at.is_(None))
    )


def _detail(db: Session, ticket: Ticket, user: User) -> dict:
    payload = _ticket_dict(ticket, _hours_by_ticket(db, [ticket.id]).get(ticket.id, (Decimal("0"), Decimal("0"))))
    attachments_by_interaction: dict[str | None, list[dict]] = defaultdict(list)
    for attachment in db.scalars(
        select(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id).order_by(TicketAttachment.created_at)
    ).all():
        attachments_by_interaction[attachment.interaction_id].append(
            {"id": attachment.id, "filename": attachment.filename, "content_type": attachment.content_type, "size_bytes": attachment.size_bytes}
        )
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
            "attachments": attachments_by_interaction.get(item.id, []),
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
    active = _active_session(db, user)
    payload["my_work_session"] = None
    payload["my_other_work_ticket"] = None
    if active is not None:
        if active.ticket_id == ticket.id:
            elapsed = max(0, int((datetime.utcnow() - active.started_at).total_seconds()))
            payload["my_work_session"] = {"id": active.id, "started_at": active.started_at, "elapsed_seconds": elapsed}
        else:
            other = db.get(Ticket, active.ticket_id)
            payload["my_other_work_ticket"] = other.code if other else None
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
    client_id: str | None = None,
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
    if client_id:
        query = query.where(Project.client_id == client_id)
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
    # Exceção: o solicitante confirmando a solução (ticket ainda em
    # atendimento) fecha sem precisar de texto.
    requester_confirms = (
        data.status == _S.CLOSED
        and ticket.requester_id == user.id
        and ticket.status in (_S.IN_PROGRESS.value, _S.WAITING_REQUESTER.value)
    )
    needs_message = data.status in (_S.WAITING_REQUESTER, _S.RESOLVED) or (
        data.status == _S.IN_PROGRESS and ticket.status in (_S.RESOLVED.value, _S.CLOSED.value)
    ) or (data.status == _S.CLOSED and ticket.status != _S.RESOLVED.value and not requester_confirms)
    if needs_message and not message:
        raise HTTPException(status_code=422, detail=translate("Informe uma mensagem para esta mudança de status", user.language))
    interaction = _set_status(db, ticket, user, data.status, message)
    if requester_confirms:
        ticket.resolved_at = ticket.closed_at
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.UPDATE, user_id=user.id, details={"status": data.status.value})
    db.commit()
    db.refresh(ticket)
    background_tasks.add_task(notify_ticket_interaction, interaction.id)
    return _detail(db, ticket, user)


def _post_comment(db: Session, ticket: Ticket, user: User, message: str | None) -> TicketInteraction:
    """Registra um comentário (com ou sem texto, quando só há anexos). Se o
    solicitante responde enquanto o ticket está Aguardando solicitante, ele
    volta sozinho a Em atendimento. Não dá commit."""
    interaction = _add_interaction(db, ticket, user, TicketInteractionKind.COMMENT, message=message)
    if ticket.status == _S.WAITING_REQUESTER.value and ticket.requester_id == user.id:
        _set_status(db, ticket, user, _S.IN_PROGRESS)
    record_audit(db, entity_type="ticket", entity_id=ticket.id, action=AuditAction.UPDATE, user_id=user.id, details={"comment": True})
    return interaction


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
    interaction = _post_comment(db, ticket, user, data.message)
    db.commit()
    db.refresh(ticket)
    background_tasks.add_task(notify_ticket_interaction, interaction.id)
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
    _require_time_permission(ticket, user)

    _register_ticket_time(
        db,
        ticket,
        user,
        day=data.date,
        start=data.start_time,
        end=data.end_time,
        break_minutes=data.break_minutes,
        description=data.description,
        progress=data.task_progress_percentage,
    )
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


def _register_ticket_time(
    db: Session,
    ticket: Ticket,
    user: User,
    *,
    day,
    start: time,
    end: time,
    break_minutes: int,
    description: str | None,
    progress: Decimal | None,
):
    """Cria o apontamento na TAREFA do ticket (Pendente de aprovação, mesmas
    regras do apontamento normal) e a linha "tempo apontado" no histórico;
    ASSIGNED vira IN_PROGRESS. Não dá commit. Compartilhada pelo apontamento
    manual e por "Finalizar atendimento"."""
    entry = create_timesheet_entry(
        TimesheetCreate(
            task_id=ticket.task_id,
            ticket_id=ticket.id,
            date=day,
            start_time=start,
            end_time=end,
            break_minutes=break_minutes,
            description=description,
            task_progress_percentage=progress,
        ),
        user,
        db,
    )
    period = f"{day.strftime('%d/%m/%Y')} {start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    interaction = _add_interaction(
        db, ticket, user, TicketInteractionKind.TIME, message=description, from_value=period, to_value=str(entry.hours_spent)
    )
    # Começou a trabalhar: ASSIGNED vira IN_PROGRESS sozinho.
    if ticket.status == _S.ASSIGNED.value:
        _set_status(db, ticket, user, _S.IN_PROGRESS)
    return entry, interaction


def _require_time_permission(ticket: Ticket, user: User) -> None:
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Não é possível apontar horas em um ticket fechado", user.language))
    if ticket.assignee_id != user.id and user.role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail=translate("Só o responsável pelo ticket pode apontar horas nele", user.language))
    if not ticket.task_id:
        raise HTTPException(status_code=422, detail=translate("O ticket não tem tarefa vinculada para receber o apontamento", user.language))


@router.post("/tickets/{ticket_id}/work/start", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
def start_work(ticket_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """"Iniciar atendimento": começa o cronômetro do responsável. Um usuário
    só tem um atendimento aberto por vez. ASSIGNED vira IN_PROGRESS."""
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    _require_time_permission(ticket, user)
    if not db.scalar(select(Resource.id).where(Resource.user_id == user.id)):
        raise HTTPException(status_code=422, detail=translate("Usuário não possui recurso habilitado", user.language))
    active = _active_session(db, user)
    if active is not None:
        other = db.get(Ticket, active.ticket_id)
        raise HTTPException(
            status_code=422,
            detail=translate("Você já tem um atendimento em andamento no ticket {code}", user.language).format(code=other.code if other else "-"),
        )
    db.add(TicketWorkSession(ticket_id=ticket.id, user_id=user.id, started_at=datetime.utcnow()))
    if ticket.status == _S.ASSIGNED.value:
        _set_status(db, ticket, user, _S.IN_PROGRESS)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


@router.post("/tickets/{ticket_id}/work/finish", response_model=TicketDetail)
def finish_work(
    ticket_id: str,
    data: TicketWorkFinish,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """"Finalizar atendimento" (não finaliza o ticket): pega a hora do
    momento como hora final e gera o apontamento de horas na tarefa do
    ticket. Horários no fuso da aplicação (APP_TIMEZONE); se o atendimento
    atravessou a meia-noite, o apontamento é cortado em 23:59 do dia em que
    começou (um apontamento nunca cruza a virada do dia)."""
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    session = _active_session(db, user)
    if session is None or session.ticket_id != ticket.id:
        raise HTTPException(status_code=422, detail=translate("Nenhum atendimento em andamento neste ticket", user.language))
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Não é possível apontar horas em um ticket fechado", user.language))

    zone = app_timezone()
    ended_at = datetime.utcnow()
    start_local = session.started_at.replace(tzinfo=timezone.utc).astimezone(zone)
    end_local = ended_at.replace(tzinfo=timezone.utc).astimezone(zone)
    day = start_local.date()
    start = time(start_local.hour, start_local.minute)
    end = time(end_local.hour, end_local.minute) if end_local.date() == day else time(23, 59)
    if end <= start:
        raise HTTPException(
            status_code=422,
            detail=translate("O atendimento tem menos de 1 minuto — continue trabalhando ou descarte", user.language),
        )
    entry, interaction = _register_ticket_time(
        db,
        ticket,
        user,
        day=day,
        start=start,
        end=end,
        break_minutes=data.break_minutes,
        description=data.message,
        progress=data.task_progress_percentage,
    )
    session.ended_at = ended_at
    session.timesheet_id = entry.id
    db.commit()
    db.refresh(ticket)
    if interaction.message:
        background_tasks.add_task(notify_ticket_interaction, interaction.id)
    return _detail(db, ticket, user)


@router.post("/tickets/{ticket_id}/work/cancel", response_model=TicketDetail)
def cancel_work(ticket_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Descarta o atendimento em andamento (nenhum apontamento é gerado)."""
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    session = _active_session(db, user)
    if session is None or session.ticket_id != ticket.id:
        raise HTTPException(status_code=422, detail=translate("Nenhum atendimento em andamento neste ticket", user.language))
    db.delete(session)
    db.commit()
    db.refresh(ticket)
    return _detail(db, ticket, user)


# ---------------------------------------------------------------------------
# Anexos
# ---------------------------------------------------------------------------


def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _clean_filename(filename: str) -> str:
    """Só o nome (sem pasta) e sem caracteres de controle, no máximo 200."""
    name = (filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:200] or "arquivo"


@router.post("/tickets/{ticket_id}/attachments", response_model=TicketDetail, status_code=status.HTTP_201_CREATED)
async def upload_ticket_attachments(
    ticket_id: str,
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    message: str | None = Form(None),
    interaction_id: str | None = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Anexa arquivos ao ticket. Sem `interaction_id`, o envio vira uma nova
    interação (comentário, com `message` opcional); com `interaction_id`
    (ex.: a abertura do ticket), anexa a uma interação SUA já existente."""
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    lang = user.language
    if ticket.status == _S.CLOSED.value:
        raise HTTPException(status_code=422, detail=translate("Ticket fechado não aceita novas interações", lang))
    if not files:
        raise HTTPException(status_code=422, detail=translate("Selecione ao menos um arquivo", lang))
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=422, detail=translate("Máximo de {max} arquivos por envio", lang).format(max=MAX_FILES_PER_UPLOAD)
        )
    existing = db.scalar(select(func.count(TicketAttachment.id)).where(TicketAttachment.ticket_id == ticket.id)) or 0
    if existing + len(files) > MAX_ATTACHMENTS_PER_TICKET:
        raise HTTPException(
            status_code=422,
            detail=translate("O ticket aceita no máximo {max} anexos", lang).format(max=MAX_ATTACHMENTS_PER_TICKET),
        )

    # Valida TODOS os arquivos antes de gravar qualquer coisa.
    prepared: list[tuple[str, str, bytes]] = []
    for upload in files:
        name = _clean_filename(upload.filename or "")
        ext = _extension(name)
        if ext not in ALLOWED_ATTACHMENT_TYPES:
            raise HTTPException(
                status_code=422,
                detail=translate("Tipo de arquivo não permitido: {name}", lang).format(name=name),
            )
        content = await upload.read(MAX_ATTACHMENT_BYTES + 1)
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=422,
                detail=translate("Arquivo muito grande (máximo {mb} MB): {name}", lang).format(mb=MAX_ATTACHMENT_BYTES // (1024 * 1024), name=name),
            )
        if not content:
            raise HTTPException(status_code=422, detail=translate("Arquivo vazio: {name}", lang).format(name=name))
        signatures = _SIGNATURES.get(ext)
        if signatures and not content.startswith(signatures):
            raise HTTPException(
                status_code=422,
                detail=translate("O conteúdo do arquivo não corresponde ao tipo informado: {name}", lang).format(name=name),
            )
        prepared.append((name, ext, content))

    notify_id: str | None = None
    if interaction_id:
        interaction = db.get(TicketInteraction, interaction_id)
        if not interaction or interaction.ticket_id != ticket.id:
            raise HTTPException(status_code=404, detail=translate("Interação não encontrada", lang))
        if interaction.author_id != user.id:
            raise HTTPException(status_code=403, detail=translate("Só o autor da interação pode anexar arquivos a ela", lang))
    else:
        interaction = _post_comment(db, ticket, user, message)
        notify_id = interaction.id

    directory = _upload_dir()
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        for name, ext, content in prepared:
            stored_name = f"{uuid.uuid4().hex}.{ext}"
            path = directory / stored_name
            path.write_bytes(content)
            written.append(path)
            db.add(
                TicketAttachment(
                    ticket_id=ticket.id,
                    interaction_id=interaction.id,
                    filename=name,
                    stored_name=stored_name,
                    content_type=ALLOWED_ATTACHMENT_TYPES[ext],
                    size_bytes=len(content),
                    uploaded_by_id=user.id,
                )
            )
        ticket.updated_at = datetime.utcnow()
        db.commit()
    except Exception:
        # Falhou no meio (disco cheio, permissão...): não deixa arquivo órfão.
        db.rollback()
        for path in written:
            path.unlink(missing_ok=True)
        raise
    db.refresh(ticket)
    if notify_id:
        background_tasks.add_task(notify_ticket_interaction, notify_id)
    return _detail(db, ticket, user)


@router.get("/tickets/{ticket_id}/attachments/{attachment_id}")
def download_ticket_attachment(
    ticket_id: str,
    attachment_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    _require_internal(user)
    ticket = _get_ticket(db, ticket_id, user)
    attachment = db.get(TicketAttachment, attachment_id)
    if not attachment or attachment.ticket_id != ticket.id:
        raise HTTPException(status_code=404, detail=translate("Anexo não encontrado", user.language))
    path = _upload_dir() / attachment.stored_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=translate("Arquivo do anexo não encontrado no servidor", user.language))
    # Sempre como download (nunca inline) + nosniff: o navegador não
    # interpreta o conteúdo enviado por um usuário.
    return FileResponse(
        path,
        media_type=attachment.content_type,
        filename=attachment.filename,
        headers={"X-Content-Type-Options": "nosniff"},
    )


# ---------------------------------------------------------------------------
# Indicadores (gerentes)
# ---------------------------------------------------------------------------

_AGING_BUCKETS = [("0-2 dias", 0, 2), ("3-7 dias", 3, 7), ("8-15 dias", 8, 15), ("16+ dias", 16, 10**6)]


@router.get("/tickets-indicators", response_model=TicketIndicators)
def ticket_indicators(
    project_id: str | None = None,
    client_id: str | None = None,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    """Indicadores para gerentes: abertos por criticidade e status, tempo de
    espera (idade dos abertos), horas gastas em tickets por projeto e carga
    por responsável. Administrador/Gerente de Serviços/Diretor Geral veem
    tudo; Gerente de Projetos, só os projetos que conduz."""
    query = select(Ticket).join(Project, Project.id == Ticket.project_id)
    if user.role not in ADMIN_LIKE_ROLES:
        query = query.where(Project.manager_id == user.id)
    if project_id:
        query = query.where(Ticket.project_id == project_id)
    if client_id:
        query = query.where(Project.client_id == client_id)
    tickets = list(db.scalars(query).all())
    ids = [ticket.id for ticket in tickets]
    hours = _hours_by_ticket(db, ids)
    zero = (Decimal("0"), Decimal("0"))
    now = datetime.utcnow()

    open_tickets = [ticket for ticket in tickets if ticket.status != _S.CLOSED.value]
    ages = {ticket.id: max(0, (now - ticket.created_at).days) for ticket in open_tickets}

    by_criticality = {level.value: 0 for level in TicketCriticality}
    for ticket in open_tickets:
        by_criticality[ticket.criticality] = by_criticality.get(ticket.criticality, 0) + 1
    by_status = {state.value: 0 for state in TicketStatus}
    for ticket in tickets:
        by_status[ticket.status] = by_status.get(ticket.status, 0) + 1

    buckets = [
        {"label": label, "count": sum(1 for age in ages.values() if low <= age <= high)} for label, low, high in _AGING_BUCKETS
    ]
    oldest = sorted(open_tickets, key=lambda ticket: ages[ticket.id], reverse=True)[:8]
    average_age = (Decimal(sum(ages.values())) / Decimal(len(ages))).quantize(Decimal("0.1")) if ages else None

    projects: dict[str, dict] = {}
    for ticket in tickets:
        row = projects.setdefault(
            ticket.project_id,
            {
                "project_id": ticket.project_id,
                "project_code": ticket.project.code,
                "project_name": ticket.project.name,
                "tickets_total": 0,
                "tickets_open": 0,
                "hours_logged": Decimal("0"),
                "hours_approved": Decimal("0"),
            },
        )
        logged, approved = hours.get(ticket.id, zero)
        row["tickets_total"] += 1
        row["tickets_open"] += 1 if ticket.status != _S.CLOSED.value else 0
        row["hours_logged"] += logged
        row["hours_approved"] += approved

    # Carga por responsável: tickets abertos direcionados + horas que a
    # pessoa apontou em tickets.
    workload: dict[str, dict] = {}
    for ticket in open_tickets:
        if ticket.assignee_id:
            row = workload.setdefault(
                ticket.assignee_id,
                {"user_id": ticket.assignee_id, "name": ticket.assignee.name if ticket.assignee else "-", "open_tickets": 0, "hours_logged": Decimal("0")},
            )
            row["open_tickets"] += 1
    if ids:
        for owner_id, total in db.execute(
            select(Resource.user_id, func.sum(Timesheet.hours_spent))
            .join(Resource, Resource.id == Timesheet.resource_id)
            .where(Timesheet.ticket_id.in_(ids), Timesheet.status != TimesheetStatus.REJECTED)
            .group_by(Resource.user_id)
        ).all():
            owner = db.get(User, owner_id)
            row = workload.setdefault(
                owner_id, {"user_id": owner_id, "name": owner.name if owner else "-", "open_tickets": 0, "hours_logged": Decimal("0")}
            )
            row["hours_logged"] += Decimal(total or 0)

    return {
        "total_tickets": len(tickets),
        "open_tickets": len(open_tickets),
        "closed_tickets": len(tickets) - len(open_tickets),
        "average_age_days": average_age,
        "hours_logged": sum((value[0] for value in hours.values()), Decimal("0")),
        "hours_approved": sum((value[1] for value in hours.values()), Decimal("0")),
        "open_by_criticality": by_criticality,
        "by_status": by_status,
        "aging_buckets": buckets,
        "oldest_open": [
            {
                "id": ticket.id,
                "code": ticket.code,
                "title": ticket.title,
                "project_code": ticket.project.code,
                "criticality": ticket.criticality,
                "status": ticket.status,
                "assignee_name": ticket.assignee.name if ticket.assignee else None,
                "age_days": ages[ticket.id],
            }
            for ticket in oldest
        ],
        "hours_by_project": sorted(projects.values(), key=lambda row: row["hours_logged"], reverse=True),
        "workload": sorted(workload.values(), key=lambda row: (row["open_tickets"], row["hours_logged"]), reverse=True),
    }
