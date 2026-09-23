from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Calendar,
    Client,
    DependencyType,
    Holiday,
    Project,
    Resource,
    Risk,
    RiskLevel,
    RiskStatus,
    Task,
    TaskAssignment,
    TaskDependency,
    TaskStatus,
    TaskType,
    Timesheet,
    ProjectExpense,
    User,
    UserRole,
)
from app.services import (
    BusinessCalendar,
    financials_by_task_type,
    portfolio_rows,
    project_burndown,
    project_financials,
    project_progress,
    project_roi,
    reschedule_cascade,
    resource_utilization,
    risk_matrix,
    velocity_series,
)


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _make_project(db, *, code: str) -> Project:
    client = Client(code=code, legal_name=f"Cliente {code}")
    user = User(name="PM", email=f"pm-{code.lower()}@example.com", password_hash="x", role=UserRole.INTERNAL_PM)
    db.add_all([client, user])
    db.flush()
    project = Project(client_id=client.id, manager_id=user.id, code=code, name=f"Projeto {code}")
    db.add(project)
    db.flush()
    return project


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


def test_financials_include_adhoc_timesheet_allocated_to_project():
    """Regressão: um apontamento avulso (sem task, só com project_id) precisa
    entrar no custo real do projeto — o outerjoin em project_financials()
    existe para isso; um INNER JOIN via Task excluiria esse lançamento."""
    db = session()
    project = _make_project(db, code="PRJ-ADHOC")
    resource = Resource(
        user_id=project.manager_id, role_title="Consultor", internal_cost_per_hour=Decimal("50"), billing_rate_per_hour=Decimal("100")
    )
    db.add(resource)
    db.flush()
    db.add(
        Timesheet(
            task_id=None,
            project_id=project.id,
            resource_id=resource.id,
            date=date(2026, 8, 24),
            hours_spent=Decimal("3"),
        )
    )
    db.commit()

    result = project_financials(db, project.id)
    assert result["timesheet_cost"] == Decimal("150.00")
    assert result["real_cost"] == Decimal("150.00")


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


def test_ss_cascade_starts_successor_together_with_predecessor():
    """SS (Start-to-Start): a sucessora deve iniciar junto com a predecessora
    (sem lag), preservando sua própria duração original."""
    db = session()
    project = _make_project(db, code="PRJ-SS")

    pred = Task(project_id=project.id, name="A", wbs_code="1", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 26))
    succ = Task(project_id=project.id, name="B", wbs_code="2", planned_start_date=date(2026, 9, 1), planned_end_date=date(2026, 9, 2))
    db.add_all([pred, succ])
    db.flush()
    db.add(TaskDependency(predecessor_task_id=pred.id, successor_task_id=succ.id, dependency_type=DependencyType.SS))
    db.commit()

    updated = reschedule_cascade(db, pred.id, BusinessCalendar())

    assert len(updated) == 1
    assert updated[0].id == succ.id
    # B passa a iniciar junto com A (24/08, segunda), preservando os 2 dias
    # úteis de duração que já tinha (24/08 a 25/08).
    assert updated[0].planned_start_date == date(2026, 8, 24)
    assert updated[0].planned_end_date == date(2026, 8, 25)


def test_ff_cascade_finishes_successor_together_with_predecessor():
    """FF (Finish-to-Finish): a sucessora deve terminar junto com a
    predecessora, com seu início recalculado para trás a partir da duração
    original."""
    db = session()
    project = _make_project(db, code="PRJ-FF")

    pred = Task(project_id=project.id, name="A", wbs_code="1", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 26))
    succ = Task(project_id=project.id, name="B", wbs_code="2", planned_start_date=date(2026, 8, 20), planned_end_date=date(2026, 8, 21))
    db.add_all([pred, succ])
    db.flush()
    db.add(TaskDependency(predecessor_task_id=pred.id, successor_task_id=succ.id, dependency_type=DependencyType.FF))
    db.commit()

    updated = reschedule_cascade(db, pred.id, BusinessCalendar())

    assert len(updated) == 1
    assert updated[0].id == succ.id
    # B (2 dias úteis de duração) passa a terminar junto com A, em 26/08
    # (quarta), logo precisa iniciar em 25/08 (terça).
    assert updated[0].planned_start_date == date(2026, 8, 25)
    assert updated[0].planned_end_date == date(2026, 8, 26)


def test_sf_cascade_finishes_successor_when_predecessor_starts():
    """SF (Start-to-Finish): a sucessora deve terminar quando a predecessora
    inicia, com seu início recalculado para trás a partir da duração
    original. É a dependência mais incomum das quatro, mas a API a expõe."""
    db = session()
    project = _make_project(db, code="PRJ-SF")

    pred = Task(project_id=project.id, name="A", wbs_code="1", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 26))
    succ = Task(project_id=project.id, name="B", wbs_code="2", planned_start_date=date(2026, 8, 17), planned_end_date=date(2026, 8, 19))
    db.add_all([pred, succ])
    db.flush()
    db.add(TaskDependency(predecessor_task_id=pred.id, successor_task_id=succ.id, dependency_type=DependencyType.SF))
    db.commit()

    updated = reschedule_cascade(db, pred.id, BusinessCalendar())

    assert len(updated) == 1
    assert updated[0].id == succ.id
    # B (3 dias úteis de duração) passa a terminar quando A inicia (24/08,
    # segunda), logo precisa iniciar em 20/08 (quinta).
    assert updated[0].planned_start_date == date(2026, 8, 20)
    assert updated[0].planned_end_date == date(2026, 8, 24)


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


def test_project_progress_weighted_by_estimated_hours():
    """Regressão: o % concluído do projeto é ponderado pelas
    estimated_hours de cada tarefa, não uma média simples entre elas —
    senão uma tarefa de 2h concluída pesaria o mesmo que uma de 18h ainda
    não iniciada."""
    db = session()
    project = _make_project(db, code="PRJ-PROG")
    small = Task(
        project_id=project.id, name="Pequena", wbs_code="1",
        estimated_hours=Decimal("2"), progress_percentage=Decimal("100"), status=TaskStatus.COMPLETED,
    )
    big = Task(
        project_id=project.id, name="Grande", wbs_code="2",
        estimated_hours=Decimal("18"), progress_percentage=Decimal("0"), status=TaskStatus.NOT_STARTED,
    )
    db.add_all([small, big])
    db.commit()

    result = project_progress(db, project.id)
    assert result["tasks_total"] == 2
    assert result["tasks_remaining"] == 1
    assert result["tasks_by_status"] == {"COMPLETED": 1, "NOT_STARTED": 1}
    # (2h*100% + 18h*0%) / 20h = 10% — a média simples daria 50%.
    assert result["percent_complete"] == Decimal("10.00")


def test_financials_by_task_type_splits_management_consulting_and_adhoc():
    db = session()
    project = _make_project(db, code="PRJ-SPLIT")
    mgmt_task = Task(project_id=project.id, name="Gestão", wbs_code="1", task_type=TaskType.MANAGEMENT)
    cons_task = Task(project_id=project.id, name="Consultoria", wbs_code="2", task_type=TaskType.CONSULTING)
    resource = Resource(
        user_id=project.manager_id, role_title="Consultor", internal_cost_per_hour=Decimal("50"), billing_rate_per_hour=Decimal("100")
    )
    db.add_all([mgmt_task, cons_task, resource])
    db.flush()
    db.add_all(
        [
            Timesheet(task_id=mgmt_task.id, resource_id=resource.id, date=date(2026, 8, 24), hours_spent=Decimal("2")),
            Timesheet(task_id=cons_task.id, resource_id=resource.id, date=date(2026, 8, 24), hours_spent=Decimal("3")),
            # Avulso: sem task_id, alocado só via project_id — não tem task_type, cai em "ADHOC".
            Timesheet(task_id=None, project_id=project.id, resource_id=resource.id, date=date(2026, 8, 24), hours_spent=Decimal("1")),
        ]
    )
    db.commit()

    result = financials_by_task_type(db, project.id)
    assert result["MANAGEMENT"] == {"hours": Decimal("2.00"), "cost": Decimal("100.00")}
    assert result["CONSULTING"] == {"hours": Decimal("3.00"), "cost": Decimal("150.00")}
    assert result["ADHOC"] == {"hours": Decimal("1.00"), "cost": Decimal("50.00")}


def test_project_burndown_reflects_timesheets_and_planned_end_dates():
    db = session()
    project = _make_project(db, code="PRJ-BURN")
    project.start_date = date(2026, 8, 3)
    project.end_date = date(2026, 8, 17)
    task = Task(project_id=project.id, name="Única", wbs_code="1", estimated_hours=Decimal("10"), planned_end_date=date(2026, 8, 10))
    resource = Resource(
        user_id=project.manager_id, role_title="Consultor", internal_cost_per_hour=Decimal("50"), billing_rate_per_hour=Decimal("100")
    )
    db.add_all([task, resource])
    db.flush()
    db.add(Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 5), hours_spent=Decimal("4")))
    db.commit()

    points = project_burndown(db, project.id)
    assert [p["date"] for p in points] == [date(2026, 8, 3), date(2026, 8, 10), date(2026, 8, 17)]
    # No início: nada apontado ainda e a tarefa não chegou no planned_end_date.
    assert points[0]["planned_remaining_hours"] == Decimal("10.00")
    assert points[0]["actual_remaining_hours"] == Decimal("10.00")
    # No fim do projeto: a tarefa já passou do planned_end_date (queda total no
    # "planejado") e as 4h apontadas em 05/08 já entraram no "realizado".
    assert points[-1]["planned_remaining_hours"] == Decimal("0.00")
    assert points[-1]["actual_remaining_hours"] == Decimal("6.00")


def test_resource_utilization_computes_capacity_and_actual_hours():
    db = session()
    project = _make_project(db, code="PRJ-UTIL")
    calendar = Calendar(name="Padrão", working_days=[0, 1, 2, 3, 4])
    db.add(calendar)
    db.flush()
    db.add(Holiday(calendar_id=calendar.id, date=date(2026, 8, 5), description="Feriado"))
    resource = Resource(
        user_id=project.manager_id,
        role_title="Consultor",
        internal_cost_per_hour=Decimal("50"),
        billing_rate_per_hour=Decimal("100"),
        daily_capacity_hours=Decimal("8"),
        calendar_id=calendar.id,
    )
    task = Task(project_id=project.id, name="T", wbs_code="1")
    db.add_all([resource, task])
    db.flush()
    db.add(TaskAssignment(task_id=task.id, resource_id=resource.id, allocated_hours=Decimal("40")))
    db.add(Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 4), hours_spent=Decimal("6")))
    db.commit()

    # 03/08 (segunda) a 07/08 (sexta): 5 dias úteis - 1 feriado (05/08) = 4.
    rows = resource_utilization(db, start=date(2026, 8, 3), end=date(2026, 8, 7), resource_id=resource.id)
    assert len(rows) == 1
    row = rows[0]
    assert row["capacity_hours"] == Decimal("32.00")
    assert row["actual_hours"] == Decimal("6.00")
    assert row["allocated_hours"] == Decimal("40.00")
    assert row["utilization_percentage"] == Decimal("18.75")


def test_velocity_series_buckets_hours_by_week():
    db = session()
    project = _make_project(db, code="PRJ-VEL")
    task = Task(project_id=project.id, name="T", wbs_code="1")
    resource = Resource(
        user_id=project.manager_id, role_title="Consultor", internal_cost_per_hour=Decimal("50"), billing_rate_per_hour=Decimal("100")
    )
    db.add_all([task, resource])
    db.flush()
    db.add_all(
        [
            # Semana de 03/08 (segunda).
            Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 4), hours_spent=Decimal("5")),
            Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 6), hours_spent=Decimal("3")),
            # Semana seguinte, de 10/08.
            Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 11), hours_spent=Decimal("7")),
        ]
    )
    db.commit()

    points = velocity_series(db, start=date(2026, 8, 1), end=date(2026, 8, 15), project_id=project.id)
    assert points == [
        {"period_start": date(2026, 8, 3), "hours_delivered": Decimal("8.00")},
        {"period_start": date(2026, 8, 10), "hours_delivered": Decimal("7.00")},
    ]


def test_project_roi_uses_margin_over_real_cost():
    db = session()
    project = _make_project(db, code="PRJ-ROI")
    project.sold_value = Decimal("1000")
    task = Task(project_id=project.id, name="T", wbs_code="1")
    resource = Resource(
        user_id=project.manager_id, role_title="Consultor", internal_cost_per_hour=Decimal("50"), billing_rate_per_hour=Decimal("100")
    )
    db.add_all([task, resource])
    db.flush()
    db.add(Timesheet(task_id=task.id, resource_id=resource.id, date=date(2026, 8, 24), hours_spent=Decimal("10")))
    db.commit()

    result = project_roi(db, project.id)
    # real_cost = 10h * 50 = 500; margem = 1000 - 500 = 500; ROI = margem/custo*100 = 100%.
    assert result["real_cost"] == Decimal("500.00")
    assert result["roi_percentage"] == Decimal("100.00")


def test_project_roi_is_none_without_real_cost():
    db = session()
    project = _make_project(db, code="PRJ-ROI-0")
    project.sold_value = Decimal("1000")
    db.commit()

    result = project_roi(db, project.id)
    assert result["roi_percentage"] is None


def test_portfolio_rows_show_next_milestone_and_hide_margin_when_excluded():
    db = session()
    project = _make_project(db, code="PRJ-PORT")
    project.sold_value = Decimal("1000")
    future_milestone = date.today() + timedelta(days=10)
    past_milestone = date.today() - timedelta(days=10)
    m1 = Task(project_id=project.id, name="Marco passado", wbs_code="1", is_milestone=True, planned_end_date=past_milestone)
    m2 = Task(project_id=project.id, name="Marco futuro", wbs_code="2", is_milestone=True, planned_end_date=future_milestone)
    db.add_all([m1, m2])
    db.commit()

    internal_rows = portfolio_rows(db, [project], include_financials=True)
    assert internal_rows[0]["next_milestone_name"] == "Marco futuro"
    assert internal_rows[0]["next_milestone_date"] == future_milestone
    assert internal_rows[0]["margin"] == Decimal("1000.00")

    external_rows = portfolio_rows(db, [project], include_financials=False)
    assert external_rows[0]["margin"] is None


def test_risk_matrix_counts_by_cell_and_flags_high_priority_open_risks():
    db = session()
    project = _make_project(db, code="PRJ-RISK")
    db.add_all(
        [
            Risk(project_id=project.id, description="Baixo/baixo", probability=RiskLevel.LOW, impact=RiskLevel.LOW),
            Risk(project_id=project.id, description="Alto/alto aberto", probability=RiskLevel.HIGH, impact=RiskLevel.HIGH, status=RiskStatus.OPEN),
            Risk(
                project_id=project.id, description="Alto/alto fechado", probability=RiskLevel.HIGH, impact=RiskLevel.HIGH, status=RiskStatus.CLOSED
            ),
        ]
    )
    db.commit()

    result = risk_matrix(db, project.id)
    assert result["grid"]["HIGH"]["HIGH"] == 2
    assert result["grid"]["LOW"]["LOW"] == 1
    # Só o risco HIGH/HIGH ainda aberto (não CLOSED) entra na priorização.
    assert len(result["high_priority"]) == 1
    assert result["high_priority"][0].description == "Alto/alto aberto"
