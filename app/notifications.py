"""E-mails de negócio (pedido do usuário: "preciso criar um processo de
envio de emails" para alguns casos — "estes são alguns casos, que vão ser
incrementados"). Cada função aqui monta o assunto/corpo de UM tipo de
aviso e delega o envio de verdade para `app.email_service.send_email`
(que por sua vez lê a configuração de `EmailSettings` e nunca levanta
exceção — ver docstring de lá).

As funções chamadas em `BackgroundTasks` (ver app/routers/schedules.py)
abrem a PRÓPRIA sessão de banco (`get_session_factory()()`), em vez de
reaproveitar a sessão da requisição que já terminou quando a tarefa de
fundo roda — é o mesmo padrão já usado pelos scripts em `scripts/`.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from html import escape as h

from sqlalchemy import select
from sqlalchemy.orm import Session

from .email_service import get_email_settings, send_email
from .ics import build_invite_ics, wall_clock_to_utc
from .i18n import t as translate
from .models import Project, Resource, ResourceSchedule, Task, Timesheet, TimesheetStatus, User


def _schedule_email_content(schedule: ResourceSchedule, user: User, *, created: bool) -> tuple[str, str, str]:
    """Monta (assunto, html, texto) do aviso de agendamento. Separado de
    `notify_resource_schedule` só para facilitar teste direto do
    conteúdo, sem precisar passar por uma sessão de banco de verdade."""
    lang = user.language
    project = schedule.project
    tasks = schedule.tasks
    date_str = schedule.date.strftime("%d/%m/%Y")
    time_str = f"{schedule.start_time.strftime('%H:%M')} - {schedule.end_time.strftime('%H:%M')}"

    subject = translate(
        "Novo agendamento criado na sua Agenda de consultores" if created else "Agendamento atualizado na sua Agenda de consultores",
        lang,
    )
    greeting = translate("Olá, {name}!", lang).format(name=user.name)
    intro = translate(
        "Um novo bloco foi agendado para você na Agenda de consultores:" if created else "Um bloco da sua Agenda foi alterado:",
        lang,
    )
    label_project = translate("Projeto", lang)
    label_date = translate("Data", lang)
    label_time = translate("Horário", lang)
    label_tasks = translate("Tarefas vinculadas", lang)
    label_none = translate("Nenhuma tarefa vinculada a este bloco", lang)

    project_name = project.name if project else "-"
    task_items_html = "".join(f"<li>{h(task.wbs_code)} — {h(task.name)}</li>" for task in tasks) or f"<li>{h(label_none)}</li>"
    task_items_text = "\n".join(f"  - {task.wbs_code} — {task.name}" for task in tasks) or f"  - {label_none}"

    html_body = (
        f"<p>{h(greeting)}</p>"
        f"<p>{h(intro)}</p>"
        "<ul>"
        f"<li><strong>{h(label_project)}:</strong> {h(project_name)}</li>"
        f"<li><strong>{h(label_date)}:</strong> {h(date_str)}</li>"
        f"<li><strong>{h(label_time)}:</strong> {h(time_str)}</li>"
        "</ul>"
        f"<p><strong>{h(label_tasks)}:</strong></p>"
        f"<ul>{task_items_html}</ul>"
    )
    text_body = (
        f"{greeting}\n\n{intro}\n\n"
        f"{label_project}: {project_name}\n{label_date}: {date_str}\n{label_time}: {time_str}\n\n"
        f"{label_tasks}:\n{task_items_text}\n"
    )
    return subject, html_body, text_body


def _invite_recipient(resource: Resource, user: User) -> str | None:
    """Endereço que recebe o convite de calendário, ou None se o consultor
    não ligou a opção (menu do avatar → "Meu Google Calendar")."""
    if not resource.calendar_invite_enabled:
        return None
    return resource.calendar_invite_email or user.email or None


def _invite_description(schedule_tasks: list[str], note: str | None, lang) -> str:
    parts: list[str] = []
    if note:
        parts.append(note)
    if schedule_tasks:
        parts.append(translate("Tarefas vinculadas", lang) + ":\n" + "\n".join(f"- {task}" for task in schedule_tasks))
    return "\n\n".join(parts)


def notify_resource_schedule(schedule_id: str, *, created: bool) -> None:
    """Dispara o aviso de agendamento (pedido do usuário, caso 1: "Agendas
    definidas para consultores"). Chamada em segundo plano a partir de
    create_schedule/update_schedule (app/routers/schedules.py) — nunca
    bloqueia a resposta da API, e uma falha de envio nunca desfaz o
    agendamento (mesma regra da integração com Google Calendar).

    Se o consultor ligou o convite de calendário, o MESMO e-mail segue pro
    endereço da conta Google dele com o `.ics` (METHOD:REQUEST) anexado — um
    e-mail só, não dois. Reenvios do mesmo agendamento mantêm o UID e sobem
    o SEQUENCE, então o Google atualiza o evento em vez de duplicar."""
    from .database import get_session_factory

    session = get_session_factory()()
    try:
        schedule = session.get(ResourceSchedule, schedule_id)
        if not schedule:
            return
        resource = schedule.resource
        user = resource.user if resource else None
        if not user or not user.email:
            return
        subject, html_body, text_body = _schedule_email_content(schedule, user, created=created)
        invite_to = _invite_recipient(resource, user)
        settings = get_email_settings(session) if invite_to else None
        if not invite_to or not settings:
            send_email(
                session, to_email=user.email, to_name=user.name, subject=subject, html_body=html_body, text_body=text_body, kind="agendamento"
            )
            return
        if not created:
            schedule.ics_sequence = (schedule.ics_sequence or 0) + 1
            session.commit()
        lang = user.language
        note = translate(
            "Este e-mail traz um convite de calendário: ele é adicionado ao seu Google Calendar (ou fica pendente de aceite).", lang
        )
        html_body += f"<p><em>{h(note)}</em></p>"
        text_body += f"\n{note}\n"
        project = schedule.project
        ics = build_invite_ics(
            method="REQUEST",
            uid=f"{schedule.id}@projmanagerpy",
            sequence=schedule.ics_sequence or 0,
            start_utc=wall_clock_to_utc(schedule.date, schedule.start_time),
            end_utc=wall_clock_to_utc(schedule.date, schedule.end_time),
            summary=project.name if project else "Agenda",
            description=_invite_description([f"{task.wbs_code} — {task.name}" for task in schedule.tasks], schedule.description, lang),
            organizer_email=settings.from_email,
            organizer_name=settings.from_name,
            attendee_email=invite_to,
            attendee_name=user.name,
        )
        send_email(
            session,
            to_email=invite_to,
            to_name=user.name,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            kind="convite_agenda",
            ics_method="REQUEST",
            ics_content=ics,
        )
    finally:
        session.close()


def snapshot_schedule_for_cancel(schedule: ResourceSchedule) -> dict | None:
    """Foto do agendamento ANTES de ser excluído (depois o registro não
    existe mais). Devolve None quando o consultor não usa convite de
    calendário — nesse caso excluir continua sem aviso, como sempre foi."""
    resource = schedule.resource
    user = resource.user if resource else None
    if not resource or not user:
        return None
    invite_to = _invite_recipient(resource, user)
    if not invite_to:
        return None
    return {
        "uid": f"{schedule.id}@projmanagerpy",
        "sequence": (schedule.ics_sequence or 0) + 1,
        "date": schedule.date,
        "start_time": schedule.start_time,
        "end_time": schedule.end_time,
        "project_name": schedule.project.name if schedule.project else "Agenda",
        "to_email": invite_to,
        "to_name": user.name,
        "lang": user.language,
    }


def notify_resource_schedule_cancelled(snapshot: dict) -> None:
    """Cancelamento do convite (METHOD:CANCEL) quando o agendamento é
    excluído — remove o evento da agenda do consultor. Roda em segundo plano
    com a foto tirada por `snapshot_schedule_for_cancel`."""
    from .database import get_session_factory

    session = get_session_factory()()
    try:
        settings = get_email_settings(session)
        if not settings:
            return
        lang = snapshot["lang"]
        subject = translate("Agendamento cancelado na sua Agenda de consultores", lang)
        greeting = translate("Olá, {name}!", lang).format(name=snapshot["to_name"])
        intro = translate("Um bloco da sua Agenda foi cancelado:", lang)
        date_str = snapshot["date"].strftime("%d/%m/%Y")
        time_str = f"{snapshot['start_time'].strftime('%H:%M')} - {snapshot['end_time'].strftime('%H:%M')}"
        html_body = (
            f"<p>{h(greeting)}</p><p>{h(intro)}</p><ul>"
            f"<li><strong>{h(translate('Projeto', lang))}:</strong> {h(snapshot['project_name'])}</li>"
            f"<li><strong>{h(translate('Data', lang))}:</strong> {h(date_str)}</li>"
            f"<li><strong>{h(translate('Horário', lang))}:</strong> {h(time_str)}</li></ul>"
        )
        text_body = (
            f"{greeting}\n\n{intro}\n\n{translate('Projeto', lang)}: {snapshot['project_name']}\n"
            f"{translate('Data', lang)}: {date_str}\n{translate('Horário', lang)}: {time_str}\n"
        )
        ics = build_invite_ics(
            method="CANCEL",
            uid=snapshot["uid"],
            sequence=snapshot["sequence"],
            start_utc=wall_clock_to_utc(snapshot["date"], snapshot["start_time"]),
            end_utc=wall_clock_to_utc(snapshot["date"], snapshot["end_time"]),
            summary=snapshot["project_name"],
            description="",
            organizer_email=settings.from_email,
            organizer_name=settings.from_name,
            attendee_email=snapshot["to_email"],
            attendee_name=snapshot["to_name"],
        )
        send_email(
            session,
            to_email=snapshot["to_email"],
            to_name=snapshot["to_name"],
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            kind="convite_agenda",
            ics_method="CANCEL",
            ics_content=ics,
        )
    finally:
        session.close()


def send_calendar_invite_test(session: Session, resource: Resource, user: User) -> tuple[bool, str | None]:
    """Botão "Enviar convite de teste" do modal "Meu Google Calendar": manda
    um convite real, amanhã às 09:00–09:30 (fuso da aplicação), pro endereço
    configurado — o jeito de o consultor (e o administrador) conferirem que
    o Google aceita os convites desse remetente (SPF/DKIM) antes de depender
    deles. O consultor apaga o evento de teste na própria agenda depois."""
    import uuid
    from datetime import datetime as _dt, time as _time, timedelta

    from .ics import app_timezone

    settings = get_email_settings(session)
    if not settings or not settings.enabled:
        return False, translate("O envio de e-mails do sistema está desativado ou não configurado", user.language)
    invite_to = resource.calendar_invite_email or user.email
    tomorrow = (_dt.now(app_timezone()) + timedelta(days=1)).date()
    lang = user.language
    subject = translate("Teste de convite — Agenda de consultores", lang)
    note = translate("Este é um convite de teste. Se ele apareceu na sua agenda, a integração está funcionando; pode excluí-lo.", lang)
    ics = build_invite_ics(
        method="REQUEST",
        uid=f"teste-{uuid.uuid4()}@projmanagerpy",
        sequence=0,
        start_utc=wall_clock_to_utc(tomorrow, _time(9, 0)),
        end_utc=wall_clock_to_utc(tomorrow, _time(9, 30)),
        summary=subject,
        description=note,
        organizer_email=settings.from_email,
        organizer_name=settings.from_name,
        attendee_email=invite_to,
        attendee_name=user.name,
    )
    return send_email(
        session,
        to_email=invite_to,
        to_name=user.name,
        subject=subject,
        html_body=f"<p>{h(translate('Olá, {name}!', lang).format(name=user.name))}</p><p>{h(note)}</p>",
        text_body=f"{translate('Olá, {name}!', lang).format(name=user.name)}\n\n{note}\n",
        kind="convite_agenda_teste",
        ics_method="REQUEST",
        ics_content=ics,
    )


def _digest_email_content(manager_name: str, lang, rows: list[dict], total_hours: Decimal) -> tuple[str, str, str]:
    subject = translate("Apontamentos aguardando sua aprovação", lang)
    greeting = translate("Olá, {name}!", lang).format(name=manager_name)
    intro = translate(
        "Há {count} apontamento(s) aguardando sua aprovação, totalizando {hours}h:",
        lang,
    ).format(count=len(rows), hours=total_hours)
    col_project = translate("Projeto", lang)
    col_resource = translate("Consultor", lang)
    col_date = translate("Data", lang)
    col_task = translate("Tarefa", lang)
    col_hours = translate("Horas", lang)

    rows_html = "".join(
        "<tr>"
        f"<td>{h(row['project_name'])}</td>"
        f"<td>{h(row['resource_name'])}</td>"
        f"<td>{h(row['date_str'])}</td>"
        f"<td>{h(row['task_name'])}</td>"
        f"<td style=\"text-align:right\">{row['hours']}</td>"
        "</tr>"
        for row in rows
    )
    html_body = (
        f"<p>{h(greeting)}</p><p>{h(intro)}</p>"
        "<table border=\"1\" cellpadding=\"6\" cellspacing=\"0\" style=\"border-collapse:collapse\">"
        f"<thead><tr><th>{h(col_project)}</th><th>{h(col_resource)}</th><th>{h(col_date)}</th>"
        f"<th>{h(col_task)}</th><th>{h(col_hours)}</th></tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )
    text_rows = "\n".join(
        f"  - {row['date_str']} | {row['project_name']} | {row['resource_name']} | {row['task_name']} | {row['hours']}h"
        for row in rows
    )
    text_body = f"{greeting}\n\n{intro}\n\n{text_rows}\n"
    return subject, html_body, text_body


def send_pending_approval_digests(db: Session, *, dry_run: bool = False) -> list[dict]:
    """Agrupa os apontamentos PENDING por `Project.manager_id` (mesmo
    critério de visibilidade da fila de Aprovações — ver list_timesheets
    em app/routers/timesheets.py: INTERNAL_PM só vê os apontamentos dos
    projetos que gerencia) e manda UM e-mail-resumo por gerente, em vez de
    um e-mail por apontamento (decisão confirmada com o usuário: "Resumo
    periódico"). Hora administrativa interna (sem project_id, nem via
    tarefa) não entra — não existe gerente de projeto pra avisar.

    Pensada pra ser chamada tanto pelo endpoint/trigger quanto por
    `scripts/send_pending_approval_digest.py` (rodado por um cron externo
    no servidor do usuário — este ambiente de desenvolvimento não tem
    como agendar um job recorrente de verdade). Retorna um resumo por
    gerente (usado tanto pelo `--dry-run` do script quanto pelos testes);
    com `dry_run=True`, NENHUM e-mail é enviado de verdade."""
    pending = db.scalars(
        select(Timesheet).outerjoin(Task, Task.id == Timesheet.task_id).where(Timesheet.status == TimesheetStatus.PENDING)
    ).all()

    by_manager: dict[str, list[tuple[Timesheet, Project]]] = defaultdict(list)
    for entry in pending:
        project_id = entry.task.project_id if entry.task else entry.project_id
        if not project_id:
            continue
        project = db.get(Project, project_id)
        if not project:
            continue
        by_manager[project.manager_id].append((entry, project))

    summaries: list[dict] = []
    for manager_id, items in by_manager.items():
        manager = db.get(User, manager_id)
        if not manager or not manager.email:
            continue
        rows = []
        total_hours = Decimal("0")
        for entry, project in items:
            resource = db.get(Resource, entry.resource_id)
            rows.append(
                {
                    "project_name": project.name,
                    "resource_name": resource.user.name if resource and resource.user else "-",
                    "date_str": entry.date.strftime("%d/%m/%Y"),
                    "task_name": entry.task.name if entry.task else translate("Avulso/Traslado", manager.language),
                    "hours": entry.hours_spent,
                }
            )
            total_hours += entry.hours_spent
        summaries.append(
            {
                "manager_id": manager_id,
                "manager_email": manager.email,
                "manager_name": manager.name,
                "count": len(items),
                "total_hours": total_hours,
                "rows": rows,
            }
        )
        if not dry_run:
            subject, html_body, text_body = _digest_email_content(manager.name, manager.language, rows, total_hours)
            send_email(
                db,
                to_email=manager.email,
                to_name=manager.name,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                kind="resumo_aprovacoes",
            )
    return summaries
