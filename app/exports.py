"""Exportação da grade de tarefas do projeto pra planilha eletrônica
(.xlsx — formato lido tanto pelo Excel quanto pelo LibreOffice/OpenOffice
Calc, sem precisar gerar dois arquivos separados).

Usa exatamente os mesmos dados computados da tela de Tarefas (Duração/
Trabalho/Início/Fim agregados de tarefa-pai via rollup, linha de base mais
recente, SPI/CPI por tarefa — ver services.task_schedule_rows), pra quem
precisa levar o cronograma pra fora da aplicação: mandar pro cliente,
analisar à parte, ou arquivar uma versão pontual."""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Project, Resource, Task, TaskAssignment, TaskDependency, User
from .services import task_schedule_rows

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
    # (TasksTab.resourceLabel): nome do usuário dono do recurso, ou o
    # cargo (role_title) se o recurso não tiver usuário vinculado.
    resources_by_task: dict[str, list[str]] = {}
    if task_ids:
        assignment_rows = session.execute(
            select(TaskAssignment.task_id, User.name, Resource.role_title)
            .join(Resource, Resource.id == TaskAssignment.resource_id)
            .join(User, User.id == Resource.user_id)
            .where(TaskAssignment.task_id.in_(task_ids))
        ).all()
        for task_id, user_name, role_title in assignment_rows:
            resources_by_task.setdefault(task_id, []).append(user_name or role_title)

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
                _num(task.progress_percentage),
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
