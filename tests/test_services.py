from datetime import date
from decimal import Decimal

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
