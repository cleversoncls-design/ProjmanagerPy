"""Exportação da grade de tarefas do projeto pra planilha eletrônica
(.xlsx — formato lido tanto pelo Excel quanto pelo LibreOffice/OpenOffice
Calc, sem precisar gerar dois arquivos separados).

Usa exatamente os mesmos dados computados da tela de Tarefas (Duração/
Trabalho/Início/Fim agregados de tarefa-pai via rollup, linha de base mais
recente, SPI/CPI por tarefa — ver services.task_schedule_rows), pra quem
precisa levar o cronograma pra fora da aplicação: mandar pro cliente,
analisar à parte, ou arquivar uma versão pontual."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Project, Resource, Task, TaskAssignment, TaskDependency, TimesheetStatus, User
from .services import service_orders, task_schedule_rows

# Duplicados de frontend/src/utils/labels.js de propósito: a planilha é
# consumida fora da aplicação (Excel/LibreOffice), então não pode depender
# de nenhum código do frontend — só os valores crus dos enums (ver
# app/models.py) precisam ficar em sincronia manualmente se um novo status
# for adicionado.
_TASK_STATUS_LABELS = {
    "NOT_STARTED": "Não iniciada",
    "IN_PROGRESS": "Em andamento",
    "COMPLETED": "Concluída",
    "DELAYED": "Atrasada",
}
_APPROVAL_STATUS_LABELS = {
    "NOT_REQUIRED": "Não exigida",
    "PENDING": "Aguardando cliente",
    "APPROVED": "Aprovada",
    "REJECTED": "Rejeitada",
}

_HEADERS = [
    "WBS",
    "Nome da tarefa",
    "Duração (dias)",
    "Trabalho (horas)",
    "Início",
    "Fim",
    "Recursos",
    "Predecessora(s)",
    "% Realizado",
    "% Previsto",
    "SPI",
    "CPI",
    "Linha de base - Início",
    "Linha de base - Fim",
    "Status",
    "Aprovação do cliente",
]


def _num(value):
    """Decimal -> float pro openpyxl gravar como número (não texto) —
    None passa direto, célula fica em branco."""
    return None if value is None else float(value)


def build_tasks_workbook(session: Session, project: Project) -> bytes:
    schedule = task_schedule_rows(session, project)
    rows = schedule["rows"]
    tasks_by_id: dict[str, Task] = {row["task"].id: row["task"] for row in rows}
    task_ids = list(tasks_by_id.keys())

    # Recursos alocados por tarefa — mesma regra de exibição do frontend
    # (TasksTab.resourceLabel): nome do usuário dono do recurso
    # (Resource.user_id é obrigatório e único, então sempre existe).
    resources_by_task: dict[str, list[str]] = {}
    if task_ids:
        assignment_rows = session.execute(
            select(TaskAssignment.task_id, User.name)
            .join(Resource, Resource.id == TaskAssignment.resource_id)
            .join(User, User.id == Resource.user_id)
            .where(TaskAssignment.task_id.in_(task_ids))
        ).all()
        for task_id, user_name in assignment_rows:
            resources_by_task.setdefault(task_id, []).append(user_name)

    # Predecessoras por tarefa (sucessora) — mesma regra de exibição do
    # frontend (coluna "Predecessora(s)"): WBS da predecessora + tipo de
    # dependência + lag, quando houver.
    dependencies_by_successor: dict[str, list[TaskDependency]] = {}
    if task_ids:
        deps = session.scalars(
            select(TaskDependency).where(TaskDependency.successor_task_id.in_(task_ids))
        ).all()
        for dep in deps:
            dependencies_by_successor.setdefault(dep.successor_task_id, []).append(dep)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Tarefas"
    sheet.freeze_panes = "A2"
    sheet.append(_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for row in rows:
        task = row["task"]
        deps = dependencies_by_successor.get(task.id, [])
        predecessors_label = ", ".join(
            f"{tasks_by_id[dep.predecessor_task_id].wbs_code} ({dep.dependency_type}{f' {dep.lag_days:+}d' if dep.lag_days else ''})"
            for dep in deps
            if dep.predecessor_task_id in tasks_by_id
        )
        resources_label = ", ".join(resources_by_task.get(task.id, []))
        sheet.append(
            [
                task.wbs_code,
                task.name,
                _num(row["rollup_duration_days"] if row["rollup_duration_days"] is not None else task.duration_days),
                _num(row["rollup_estimated_hours"] if row["rollup_estimated_hours"] is not None else task.estimated_hours),
                row["rollup_start_date"] or task.planned_start_date,
                row["rollup_end_date"] or task.planned_end_date,
                resources_label,
                predecessors_label,
                _num(row["rollup_progress_percentage"] if row["rollup_progress_percentage"] is not None else task.progress_percentage),
                _num(row["planned_percent_complete"]),
                _num(row["spi"]),
                _num(row["cpi"]),
                row["baseline_start_date"],
                row["baseline_end_date"],
                _TASK_STATUS_LABELS.get(str(task.status), str(task.status)),
                _APPROVAL_STATUS_LABELS.get(str(task.client_approval_status), str(task.client_approval_status)),
            ]
        )

    for column_cells in sheet.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=8)
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max(length + 2, 10), 42)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _hours_hm(value: Decimal) -> str:
    """Horas decimais -> "HH:MM" — mesma conversão de formatHoursDuration
    em frontend/src/utils/format.js, duplicada aqui pelo mesmo motivo do
    resto deste arquivo: a planilha roda fora do frontend."""
    total_minutes = round(float(value) * 60)
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


_SO_HEADERS = [
    "Data",
    "Cliente",
    "Projeto",
    "Consultor",
    "Nº OS",
    "WBS",
    "Tarefa",
    "Hora início",
    "Hora fim",
    "Horas",
    "Status",
    "Descrição",
]


def _time_hm(value) -> str:
    return value.strftime("%H:%M") if value else ""


def build_service_orders_workbook(
    session: Session,
    *,
    start: date,
    end: date,
    project_id: str | None = None,
    resource_id: str | None = None,
    client_id: str | None = None,
) -> bytes:
    """Planilha das Ordens de Serviço do período filtrado (mesmos dados de
    GET /reports/service-orders, ver services.service_orders). Pedido do
    usuário: organizar "por dia, cliente, projeto" e detalhar "linha a
    linha também por tarefa" — então cada linha é uma atividade
    (apontamento) dentro de uma OS, não mais um resumo por OS. A ordem das
    linhas é a que `service_orders()` já devolve — (data, código do
    cliente, código do projeto, nome do consultor) — que já corresponde a
    "dia, cliente, projeto"; dentro de cada OS as atividades vêm ordenadas
    por hora de início (ver service_orders). Uma linha de subtotal fecha
    cada OS e uma linha de total geral fecha a planilha — mesmo padrão de
    antes, só que agora por OS em vez de por consultor."""
    orders = service_orders(session, start=start, end=end, project_id=project_id, resource_id=resource_id, client_id=client_id)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ordens de Serviço"
    sheet.freeze_panes = "A2"
    sheet.append(_SO_HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    grand_total = Decimal("0")
    for order in orders:
        client_label = f"{order['client_code']} - {order['client_name']}"
        project_label = f"{order['project_code']} - {order['project_name']}"
        for activity in order["activities"]:
            status_label = "Aprovado" if activity["status"] == TimesheetStatus.APPROVED else "Pendente"
            if activity["unscheduled"]:
                status_label += " / Fora da agenda"
            sheet.append(
                [
                    order["date"],
                    client_label,
                    project_label,
                    order["resource_name"],
                    order["order_number"],
                    activity["wbs_code"] or "—",
                    activity["task_name"] or "—",
                    _time_hm(activity["start_time"]),
                    _time_hm(activity["end_time"]),
                    _hours_hm(activity["hours"]),
                    status_label,
                    activity["description"] or "",
                ]
            )
        subtotal_row = [""] * len(_SO_HEADERS)
        subtotal_row[8] = f"Subtotal — OS {order['order_number']}"
        subtotal_row[9] = _hours_hm(order["total_hours"])
        sheet.append(subtotal_row)
        for cell in sheet[sheet.max_row]:
            cell.font = Font(bold=True)
        grand_total += order["total_hours"]

    sheet.append([])
    total_row = [""] * len(_SO_HEADERS)
    total_row[8] = "Total geral"
    total_row[9] = _hours_hm(grand_total)
    sheet.append(total_row)
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True)

    for column_cells in sheet.columns:
        length = max((len(str(cell.value)) for cell in column_cells if cell.value is not None), default=8)
        sheet.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max(length + 2, 10), 42)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
