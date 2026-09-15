from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import Base, Client, Project, Resource, Task, TaskDependency, Timesheet, ProjectExpense, User, UserRole
from app.services import BusinessCalendar, project_financials, reschedule_cascade


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_fs_cascade_skips_weekend_and_holiday():
    db = session()
    client = Client(code="CLI-1", legal_name="Acme")
    user = User(name="PM", email="pm@example.com", password_hash="x", role=UserRole.INTERNAL_PM)
    project = Project(client=client, manager_id="not-used", code="PRJ-1", name="Implantação")
    # manager_id FK is not enforced by SQLite by default in this test; use IDs after flush.
    db.add_all([client, user]); db.flush(); project.manager_id = user.id; db.add(project); db.flush()
    pred = Task(project_id=project.id, name="Predecessora", wbs_code="1", planned_start_date=date(2026, 8, 28), planned_end_date=date(2026, 8, 28))
    succ = Task(project_id=project.id, name="Sucessora", wbs_code="2", planned_start_date=date(2026, 8, 31), planned_end_date=date(2026, 9, 1))
    db.add_all([pred, succ]); db.flush(); db.add(TaskDependency(predecessor_task_id=pred.id, successor_task_id=succ.id)); db.commit()
    changed = reschedule_cascade(db, pred.id, BusinessCalendar(holidays={date(2026, 8, 31)}))
    assert changed[0].planned_start_date == date(2026, 9, 1)


def test_financials_hide_no_data_and_calculate_margin():
    db = session()
    client = Client(code="CLI-2", legal_name="Beta")
    user = User(name="PM", email="pm2@example.com", password_hash="x", role=UserRole.INTERNAL_PM)
    db.add_all([client, user]); db.flush()
    project = Project(client_id=client.id, manager_id=user.id, code="PRJ-2", name="Projeto", sold_value=Decimal("1000"))
    db.add(project); db.flush()
    task = Task(project_id=project.id, name="Tarefa", wbs_code="1"); resource = Resource(user_id=user.id, role_title="Consultor", internal_cost_per_hour=Decimal("50"), billing_rate_per_hour=Decimal("100"))
    db.add_all([task, resource]); db.flush()
    db.add(Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 24), hours_spent=Decimal("10")))
    db.add(ProjectExpense(project_id=project.id, description="Viagem", category="Deslocamento", amount=Decimal("100"), expense_date=date(2026, 8, 24))); db.commit()
    result = project_financials(db, project.id)
    assert result["real_cost"] == Decimal("600.00")
    assert result["profit_margin"] == Decimal("400.00")


def test_cascade_uses_most_restrictive_predecessor():
    """Regressão do bug em que a sucessora era recalculada com base apenas na
    última predecessora visitada, em vez da mais restritiva entre todas.

    C depende de A (termina quarta 26/08) e de B (termina segunda 24/08). A
    exige um início mais tardio para C do que B. Disparando a cascata a
    partir de B (a predecessora "mais fraca"), C ainda precisa respeitar A.
    """
    db = session()
    client = Client(code="CLI-3", legal_name="Acme 3")
    user = User(name="PM", email="pm3@example.com", password_hash="x", role=UserRole.INTERNAL_PM)
    db.add_all([client, user]); db.flush()
    project = Project(client_id=client.id, manager_id=user.id, code="PRJ-3", name="Projeto 3")
    db.add(project); db.flush()

    task_a = Task(project_id=project.id, name="A", wbs_code="1", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 26))
    task_b = Task(project_id=project.id, name="B", wbs_code="2", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 24))
    task_c = Task(project_id=project.id, name="C", wbs_code="3", planned_start_date=date(2026, 9, 1), planned_end_date=date(2026, 9, 2))
    db.add_all([task_a, task_b, task_c]); db.flush()
    db.add_all([
        TaskDependency(predecessor_task_id=task_a.id, successor_task_id=task_c.id),
        TaskDependency(predecessor_task_id=task_b.id, successor_task_id=task_c.id),
    ])
    db.commit()

    cal = BusinessCalendar()
    updated = reschedule_cascade(db, task_b.id, cal)

    assert len(updated) == 1
    assert updated[0].id == task_c.id
    # A (termina 26/08, quarta) empurra C para 27/08 (quinta); B sozinha
    # empurraria para 25/08 (terça) — a versão com bug usaria essa data
    # menor só porque foi a última (ou única) predecessora processada.
    assert updated[0].planned_start_date == date(2026, 8, 27)
    # Duração original de C (2 dias úteis) é preservada.
    assert updated[0].planned_end_date == date(2026, 8, 28)


def test_cascade_detects_cycle():
    db = session()
    client = Client(code="CLI-4", legal_name="Acme 4")
    user = User(name="PM", email="pm4@example.com", password_hash="x", role=UserRole.INTERNAL_PM)
    db.add_all([client, user]); db.flush()
    project = Project(client_id=client.id, manager_id=user.id, code="PRJ-4", name="Projeto 4")
    db.add(project); db.flush()

    task_x = Task(project_id=project.id, name="X", wbs_code="1", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 24))
    task_y = Task(project_id=project.id, name="Y", wbs_code="2", planned_start_date=date(2026, 8, 25), planned_end_date=date(2026, 8, 25))
    db.add_all([task_x, task_y]); db.flush()
    db.add_all([
        TaskDependency(predecessor_task_id=task_x.id, successor_task_id=task_y.id),
        TaskDependency(predecessor_task_id=task_y.id, successor_task_id=task_x.id),
    ])
    db.commit()

    with pytest.raises(ValueError, match="Ciclo"):
        reschedule_cascade(db, task_x.id, BusinessCalendar())
