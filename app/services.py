from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Calendar, DependencyType, Holiday, Project, Task, TaskDependency, Timesheet, Resource, ProjectExpense


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
            old_start = successor.planned_start_date
            new_start = _successor_start(cal, predecessor, successor, dep)
            duration = _duration_days(cal, successor.planned_start_date or new_start, successor.planned_end_date or new_start)
            successor.planned_start_date = new_start
            successor.planned_end_date = cal.add_working_days(new_start, duration - 1)
            if successor.planned_start_date != old_start:
                updated.append(successor)
            visit(successor)
        visiting.remove(predecessor.id)

    visit(changed)
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
        .where(Task.project_id == project_id, Timesheet.status != "REJECTED")
    ).all()
    timesheet_cost = sum((Decimal(hours) * Decimal(rate) for hours, rate in rows), Decimal("0"))
    expense_cost = sum((Decimal(x) for x in session.scalars(select(ProjectExpense.amount).where(ProjectExpense.project_id == project_id)).all()), Decimal("0"))
    real_cost = timesheet_cost + expense_cost
    sold = Decimal(project.sold_value or 0)
    return {"sold_value": sold, "timesheet_cost": timesheet_cost, "expense_cost": expense_cost, "real_cost": real_cost, "profit_margin": sold - real_cost}
