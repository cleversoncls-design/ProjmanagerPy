from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import (
    Calendar,
    DependencyType,
    Holiday,
    Project,
    Task,
    TaskDependency,
    Timesheet,
    TimesheetStatus,
    Resource,
    ProjectExpense,
)


class BusinessCalendar:
    """Calendário ISO: segunda-feira=0; working_days defaults to segunda a sexta."""

    def __init__(self, working_days: set[int] | None = None, holidays: set[date] | None = None):
        self.working_days = working_days or {0, 1, 2, 3, 4}
        self.holidays = holidays or set()

    def is_working_day(self, value: date) -> bool:
        return value.weekday() in self.working_days and value not in self.holidays

    def next_working_day(self, value: date) -> date:
        while not self.is_working_day(value):
            value += timedelta(days=1)
        return value

    def add_working_days(self, value: date, days: int) -> date:
        direction = 1 if days >= 0 else -1
        remaining = abs(days)
        current = value
        while remaining:
            current += timedelta(days=direction)
            if self.is_working_day(current):
                remaining -= 1
        return self.next_working_day(current) if direction > 0 else current


def calendar_from_db(session: Session, calendar_id: str) -> BusinessCalendar:
    calendar = session.get(Calendar, calendar_id)
    if not calendar:
        raise ValueError("Calendário não encontrado")
    holidays = set(session.scalars(select(Holiday.date).where(Holiday.calendar_id == calendar_id)).all())
    return BusinessCalendar(set(calendar.working_days), holidays)


def _duration_days(cal: BusinessCalendar, start: date, end: date) -> int:
    current, count = cal.next_working_day(start), 0
    while current <= end:
        if cal.is_working_day(current):
            count += 1
        current += timedelta(days=1)
    return max(count, 1)


def _successor_start(cal: BusinessCalendar, predecessor: Task, successor: Task, dependency: TaskDependency) -> date:
    pred_start = predecessor.planned_start_date or predecessor.planned_end_date
    pred_end = predecessor.planned_end_date or predecessor.planned_start_date
    if not pred_start or not pred_end:
        raise ValueError("Predecessora precisa ter datas planejadas")
    lagged_end = cal.add_working_days(pred_end, dependency.lag_days)
    lagged_start = cal.add_working_days(pred_start, dependency.lag_days)
    if dependency.dependency_type == DependencyType.FS:
        return cal.next_working_day(lagged_end + timedelta(days=1))
    if dependency.dependency_type == DependencyType.SS:
        return cal.next_working_day(lagged_start)
    if dependency.dependency_type == DependencyType.FF:
        successor_duration = _duration_days(cal, successor.planned_start_date or lagged_end, successor.planned_end_date or lagged_end)
        return cal.add_working_days(lagged_end, -(successor_duration - 1))
    # SF: sucessora termina quando a predecessora inicia; derive início pela duração atual.
    successor_duration = _duration_days(cal, successor.planned_start_date or lagged_start, successor.planned_end_date or lagged_start)
    return cal.add_working_days(lagged_start, -(successor_duration - 1))


def reschedule_cascade(session: Session, changed_task_id: str, cal: BusinessCalendar) -> list[Task]:
    """Recalcula as sucessoras a partir da tarefa alterada.

    Duas propriedades importantes que a versão anterior (DFS recursivo) não
    garantia:

    1. Uma sucessora com MÚLTIPLAS predecessoras precisa respeitar a mais
       restritiva (a que empurra o início mais tarde) entre todas elas, não
       apenas a última visitada — por isso o grafo afetado é processado em
       ordem topológica e a data final de cada sucessora é o `max()` dos
       candidatos calculados a partir de cada uma de suas predecessoras.
    2. A travessia é iterativa (fila de Kahn), então uma EAP muito profunda
       não esbarra no limite de recursão do Python.

    Ciclos no grafo de dependências continuam sendo rejeitados com
    ValueError.
    """
    changed = session.get(Task, changed_task_id)
    if not changed:
        raise ValueError("Tarefa não encontrada")

    # 1) BFS a partir da tarefa alterada para descobrir todas as sucessoras
    #    potencialmente afetadas (direta ou transitivamente).
    affected: set[str] = set()
    frontier = [changed_task_id]
    while frontier:
        current_id = frontier.pop()
        deps = session.scalars(
            select(TaskDependency).where(TaskDependency.predecessor_task_id == current_id)
        ).all()
        for dep in deps:
            if dep.successor_task_id not in affected:
                affected.add(dep.successor_task_id)
                frontier.append(dep.successor_task_id)

    if not affected:
        session.flush()
        return []

    # 2) Para cada sucessora afetada, carrega TODAS as suas dependências de
    #    predecessora (inclusive as que não mudaram nesta cascata), porque a
    #    data final precisa respeitar todas elas, não só o caminho que
    #    disparou a mudança.
    deps_by_successor: dict[str, list[TaskDependency]] = {}
    in_degree: dict[str, int] = {tid: 0 for tid in affected}
    successors_by_predecessor: dict[str, list[str]] = defaultdict(list)
    for tid in affected:
        deps = session.scalars(
            select(TaskDependency).where(TaskDependency.successor_task_id == tid)
        ).all()
        deps_by_successor[tid] = deps
        for dep in deps:
            if dep.predecessor_task_id in affected:
                in_degree[tid] += 1
                successors_by_predecessor[dep.predecessor_task_id].append(tid)

    # 3) Ordenação topológica (Kahn) do subconjunto afetado: uma sucessora só
    #    é processada depois que todas as suas predecessoras afetadas já
    #    tiverem sido recalculadas.
    queue = [tid for tid, degree in in_degree.items() if degree == 0]
    order: list[str] = []
    remaining = dict(in_degree)
    while queue:
        node = queue.pop()
        order.append(node)
        for succ in successors_by_predecessor.get(node, []):
            remaining[succ] -= 1
            if remaining[succ] == 0:
                queue.append(succ)

    if len(order) != len(affected):
        raise ValueError("Ciclo detectado nas dependências")

    # 4) Recalcula cada sucessora, tomando a data mais tardia entre todas as
    #    suas predecessoras (afetadas ou não).
    updated: list[Task] = []
    for successor_id in order:
        successor = session.get(Task, successor_id)
        if not successor:
            continue
        candidate_starts: list[date] = []
        for dep in deps_by_successor[successor_id]:
            predecessor = session.get(Task, dep.predecessor_task_id)
            if not predecessor or not predecessor.planned_start_date or not predecessor.planned_end_date:
                continue
            candidate_starts.append(_successor_start(cal, predecessor, successor, dep))
        if not candidate_starts:
            continue
        new_start = max(candidate_starts)
        old_start = successor.planned_start_date
        duration = _duration_days(cal, successor.planned_start_date or new_start, successor.planned_end_date or new_start)
        successor.planned_start_date = new_start
        successor.planned_end_date = cal.add_working_days(new_start, duration - 1)
        if successor.planned_start_date != old_start:
            updated.append(successor)

    session.flush()
    return updated


def project_financials(session: Session, project_id: str) -> dict[str, Decimal]:
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("Projeto não encontrado")
    rows = session.execute(
        select(Timesheet.hours_spent, Resource.internal_cost_per_hour)
        .join(Resource, Resource.id == Timesheet.resource_id)
        .join(Task, Task.id == Timesheet.task_id)
        .where(Task.project_id == project_id, Timesheet.status != TimesheetStatus.REJECTED)
    ).all()
    timesheet_cost = sum((Decimal(hours) * Decimal(rate) for hours, rate in rows), Decimal("0"))
    expense_cost = sum((Decimal(x) for x in session.scalars(select(ProjectExpense.amount).where(ProjectExpense.project_id == project_id)).all()), Decimal("0"))
    real_cost = timesheet_cost + expense_cost
    sold = Decimal(project.sold_value or 0)
    return {"sold_value": sold, "timesheet_cost": timesheet_cost, "expense_cost": expense_cost, "real_cost": real_cost, "profit_margin": sold - real_cost}
