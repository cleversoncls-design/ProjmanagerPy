from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Calendar, DependencyType, Holiday, Project, Task, TaskAssignment, TaskDependency, Timesheet, Resource, ProjectExpense


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
        successor_duration = max(1, int(successor.duration_days or _duration_days(cal, successor.planned_start_date or lagged_end, successor.planned_end_date or lagged_end)))
        return cal.add_working_days(lagged_end, -(successor_duration - 1))
    # SF: sucessora termina quando a predecessora inicia; derive início pela duração atual.
    successor_duration = max(1, int(successor.duration_days or _duration_days(cal, successor.planned_start_date or lagged_start, successor.planned_end_date or lagged_start)))
    return cal.add_working_days(lagged_start, -(successor_duration - 1))


def reschedule_cascade(session: Session, changed_task_id: str, cal: BusinessCalendar, calendar_resolver: Callable[[Task], BusinessCalendar] | None = None) -> list[Task]:
    """Recalcula sucessoras em profundidade; rejeita ciclos no grafo de dependências."""
    changed = session.get(Task, changed_task_id)
    if not changed:
        raise ValueError("Tarefa não encontrada")
    updated: list[Task] = []
    visiting: set[str] = set()

    def visit(predecessor: Task) -> None:
        if predecessor.id in visiting:
            raise ValueError("Ciclo detectado nas dependências")
        visiting.add(predecessor.id)
        deps = session.scalars(select(TaskDependency).where(TaskDependency.predecessor_task_id == predecessor.id)).all()
        for dep in deps:
            successor = session.get(Task, dep.successor_task_id)
            if not successor:
                continue
            successor_calendar = calendar_resolver(successor) if calendar_resolver else cal
            old_start = successor.planned_start_date
            new_start = _successor_start(successor_calendar, predecessor, successor, dep)
            duration = max(1, int(successor.duration_days or _duration_days(successor_calendar, successor.planned_start_date or new_start, successor.planned_end_date or new_start)))
            successor.planned_start_date = new_start
            successor.planned_end_date = successor_calendar.add_working_days(new_start, duration - 1)
            if successor.planned_start_date != old_start:
                updated.append(successor)
            visit(successor)
        visiting.remove(predecessor.id)

    visit(changed)
    session.flush()
    return updated


def task_tree_ids(session: Session, task_id: str) -> list[str]:
    """Retorna a tarefa e todos os descendentes, preservando o escopo do projeto."""
    task = session.get(Task, task_id)
    if not task:
        return []
    tasks = session.scalars(select(Task).where(Task.project_id == task.project_id)).all()
    children_by_parent: dict[str | None, list[Task]] = defaultdict(list)
    for row in tasks:
        children_by_parent[row.parent_task_id].append(row)
    result: list[str] = []
    visiting: set[str] = set()

    def visit(current_id: str) -> None:
        if current_id in visiting:
            raise ValueError("Ciclo detectado na hierarquia de tarefas")
        visiting.add(current_id)
        result.append(current_id)
        for child in children_by_parent.get(current_id, []):
            visit(child.id)
        visiting.remove(current_id)

    visit(task_id)
    return result


def renumber_task_tree(session: Session, project_id: str) -> None:
    """Gera WBS 1, 1.1, 1.2... a partir da hierarquia pai/filho.

    A ordem entre irmãos preserva o código anterior quando existir; uma tarefa
    nova, sem código, entra ao final da lista de irmãos. O cliente não controla
    mais o código: ele é sempre reescrito antes do commit.
    """
    tasks = session.scalars(select(Task).where(Task.project_id == project_id)).all()
    children_by_parent: dict[str | None, list[Task]] = defaultdict(list)
    previous_order: dict[str, tuple[tuple[int, ...], str]] = {}
    for row in tasks:
        children_by_parent[row.parent_task_id].append(row)
        pieces: list[int] = []
        try:
            pieces = [int(piece) for piece in (row.wbs_code or "").split(".") if piece != ""]
        except ValueError:
            pieces = []
        previous_order[row.id] = (tuple(pieces) if pieces else (10**9,), row.id)
    for siblings in children_by_parent.values():
        siblings.sort(key=lambda row: previous_order[row.id])

    visited: set[str] = set()

    def assign(parent_id: str | None, prefix: str, path: set[str]) -> None:
        for index, row in enumerate(children_by_parent.get(parent_id, []), start=1):
            if row.id in path:
                raise ValueError("Ciclo detectado na hierarquia de tarefas")
            if row.id in visited:
                continue
            visited.add(row.id)
            row.wbs_code = f"{prefix}.{index}" if prefix else str(index)
            assign(row.id, row.wbs_code, path | {row.id})

    assign(None, "", set())
    # Não descartar silenciosamente uma árvore corrompida: a API deve sinalizar.
    if len(visited) != len(tasks):
        raise ValueError("A hierarquia contém tarefa órfã ou ciclo")
    session.flush()


def rollup_task_derived_fields(session: Session, project_id: str, calendar_resolver: Callable[[Task], BusinessCalendar] | None = None, capacity_resolver: Callable[[Task], Decimal] | None = None) -> None:
    """Consolida horas e agenda dos pais a partir da árvore de tarefas.

    Para uma tarefa com filhos, as horas são a soma recursiva das folhas. O
    intervalo planejado cobre o menor início e o maior término dos filhos; a
    duração é contada em dias úteis. Se os filhos ainda não tiverem datas, a
    duração usa oito horas úteis por dia como fallback e as datas ficam vazias.
    """
    tasks = session.scalars(select(Task).where(Task.project_id == project_id)).all()
    by_id = {row.id: row for row in tasks}
    children_by_parent: dict[str | None, list[Task]] = defaultdict(list)
    for row in tasks:
        children_by_parent[row.parent_task_id].append(row)
    visiting: set[str] = set()

    def total(task: Task) -> Decimal:
        if task.id in visiting:
            raise ValueError("Ciclo detectado na hierarquia de tarefas")
        visiting.add(task.id)
        children = children_by_parent.get(task.id, [])
        if children:
            child_totals = [total(child) for child in children]
            task.estimated_hours = sum(child_totals, Decimal("0"))
            starts = [child.planned_start_date for child in children if child.planned_start_date]
            ends = [child.planned_end_date for child in children if child.planned_end_date]
            task.planned_start_date = min(starts) if starts else None
            task.planned_end_date = max(ends) if ends else None
            capacity = capacity_resolver(task) if capacity_resolver else Decimal("8")
            task.duration_days = max(1, int((task.estimated_hours / max(capacity, Decimal("0.01"))).to_integral_value(rounding=ROUND_CEILING)))
        value = Decimal(task.estimated_hours or 0)
        visiting.remove(task.id)
        return value

    for row in tasks:
        if row.parent_task_id is None or row.parent_task_id not in by_id:
            total(row)
    session.flush()


def rollup_estimated_hours(session: Session, project_id: str) -> None:
    """Compatibilidade: consolida horas e campos planejados da hierarquia."""
    rollup_task_derived_fields(session, project_id)


def normalize_task_hierarchy(session: Session, project_id: str, calendar_resolver: Callable[[Task], BusinessCalendar] | None = None, capacity_resolver: Callable[[Task], Decimal] | None = None) -> None:
    renumber_task_tree(session, project_id)
    rollup_task_derived_fields(session, project_id, calendar_resolver, capacity_resolver)


def task_actuals(session: Session, task_id: str) -> dict[str, Decimal | date | None]:
    task_ids = task_tree_ids(session, task_id) or [task_id]
    rows = session.execute(
        select(Timesheet.date, Timesheet.hours_spent, Resource.internal_cost_per_hour)
        .join(Resource, Resource.id == Timesheet.resource_id)
        .where(Timesheet.task_id.in_(task_ids), Timesheet.status != "REJECTED")
        .order_by(Timesheet.date)
    ).all()
    actual_hours = sum((Decimal(hours) for _, hours, _ in rows), Decimal("0"))
    actual_cost = sum((Decimal(hours) * Decimal(rate) for _, hours, rate in rows), Decimal("0"))
    return {
        "actual_hours": actual_hours,
        "actual_cost": actual_cost,
        "actual_start_date": rows[0][0] if rows else None,
        "actual_end_date": rows[-1][0] if rows else None,
    }


def task_planned_progress(task: Task, cal: BusinessCalendar, today: date | None = None) -> Decimal:
    today = today or date.today()
    if not task.planned_start_date or not task.planned_end_date:
        return Decimal("0")
    start = cal.next_working_day(task.planned_start_date)
    end = task.planned_end_date
    if today < start:
        return Decimal("0")
    total = _duration_days(cal, start, end)
    if today >= end:
        return Decimal("100")
    elapsed = _duration_days(cal, start, min(today, end))
    return (Decimal(elapsed) / Decimal(total) * Decimal("100")).quantize(Decimal("0.01"))


def task_evm(session: Session, task: Task, cal: BusinessCalendar, today: date | None = None) -> dict[str, Decimal | date | None]:
    actuals = task_actuals(session, task.id)
    task_ids = task_tree_ids(session, task.id) or [task.id]
    assignments = session.execute(
        select(TaskAssignment.allocated_hours, Resource.internal_cost_per_hour)
        .join(Resource, Resource.id == TaskAssignment.resource_id)
        .where(TaskAssignment.task_id.in_(task_ids))
    ).all()
    budget = sum((Decimal(hours) * Decimal(rate) for hours, rate in assignments), Decimal("0"))
    if budget <= 0:
        budget = Decimal(task.estimated_hours or 0)
    planned = task_planned_progress(task, cal, today)
    actual = Decimal(task.progress_percentage or 0)
    pv = (budget * planned / Decimal("100")).quantize(Decimal("0.01"))
    ev = (budget * actual / Decimal("100")).quantize(Decimal("0.01"))
    ac = Decimal(actuals["actual_cost"] or 0)
    spi = (ev / pv).quantize(Decimal("0.01")) if pv > 0 else (Decimal("1.00") if ev == 0 else Decimal("0.00"))
    cpi = (ev / ac).quantize(Decimal("0.01")) if ac > 0 else (Decimal("1.00") if ev == 0 else Decimal("0.00"))
    return {
        **actuals,
        "planned_percentage": planned,
        "earned_value": ev,
        "planned_value": pv,
        "actual_cost": ac,
        "spi": spi,
        "cpi": cpi,
    }


def project_financials(session: Session, project_id: str) -> dict[str, Decimal]:
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("Projeto não encontrado")
    rows = session.execute(
        select(Timesheet.hours_spent, Resource.internal_cost_per_hour)
        .join(Resource, Resource.id == Timesheet.resource_id)
        .join(Task, Task.id == Timesheet.task_id)
        .where(Task.project_id == project_id, Timesheet.status != "REJECTED")
    ).all()
    timesheet_cost = sum((Decimal(hours) * Decimal(rate) for hours, rate in rows), Decimal("0"))
    expense_cost = sum((Decimal(x) for x in session.scalars(select(ProjectExpense.amount).where(ProjectExpense.project_id == project_id)).all()), Decimal("0"))
    real_cost = timesheet_cost + expense_cost
    sold = Decimal(project.sold_value or 0)
    return {"sold_value": sold, "timesheet_cost": timesheet_cost, "expense_cost": expense_cost, "real_cost": real_cost, "profit_margin": sold - real_cost}
