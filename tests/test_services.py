from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import (
    Base,
    Baseline,
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
    apply_effort_driven,
    financials_by_task_type,
    move_task,
    portfolio_rows,
    project_burndown,
    project_evm,
    project_financials,
    project_progress,
    project_roi,
    project_statistics,
    recalculate_schedule,
    recalculate_wbs,
    reschedule_cascade,
    resource_utilization,
    risk_matrix,
    task_dot_colors,
    task_schedule_rows,
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


# ---------------------------------------------------------------------------
# Fase 4: motor de agendamento effort-driven, WBS, mover tarefa, status dot,
# EVM (SPI/CPI) e Project Statistics.
# ---------------------------------------------------------------------------


def test_apply_effort_driven_duration_drives_work():
    task = Task(project_id="p", name="T", wbs_code="1")
    apply_effort_driven(task, duration_days=Decimal("2"), estimated_hours=None, capacity_hours_per_day=Decimal("8"))
    assert task.duration_days == Decimal("2")
    assert task.estimated_hours == Decimal("16")


def test_apply_effort_driven_work_drives_duration():
    task = Task(project_id="p", name="T", wbs_code="1")
    apply_effort_driven(task, duration_days=None, estimated_hours=Decimal("20"), capacity_hours_per_day=Decimal("8"))
    assert task.estimated_hours == Decimal("20")
    assert task.duration_days == Decimal("2.5")


def test_apply_effort_driven_no_field_recomputes_work_from_existing_duration():
    """Caminho usado por assign_resource/remove assignment: Duração fica
    fixa (Fixed Units), só o Trabalho muda com a nova capacidade total."""
    task = Task(project_id="p", name="T", wbs_code="1", duration_days=Decimal("3"))
    apply_effort_driven(task, duration_days=None, estimated_hours=None, capacity_hours_per_day=Decimal("16"))
    assert task.duration_days == Decimal("3")
    assert task.estimated_hours == Decimal("48")


def test_recalculate_wbs_renumbers_by_hierarchy_and_sort_order():
    db = session()
    project = _make_project(db, code="PRJ-WBS")
    parent = Task(project_id=project.id, name="Fase 1", wbs_code="9", sort_order=0)
    db.add(parent)
    db.flush()
    # Filhos cadastrados fora de ordem, mas com sort_order já refletindo a
    # ordem manual desejada (2º antes do 1º).
    child_a = Task(project_id=project.id, name="A", wbs_code="9.9", parent_task_id=parent.id, sort_order=10)
    child_b = Task(project_id=project.id, name="B", wbs_code="9.1", parent_task_id=parent.id, sort_order=0)
    other_root = Task(project_id=project.id, name="Fase 2", wbs_code="1", sort_order=10)
    db.add_all([child_a, child_b, other_root])
    db.commit()

    updated = recalculate_wbs(db, project.id)

    assert parent.wbs_code == "1"
    assert child_b.wbs_code == "1.1"  # sort_order=0, vem antes
    assert child_a.wbs_code == "1.2"  # sort_order=10, vem depois
    assert other_root.wbs_code == "2"
    # Todas as 4 tarefas tiveram o código alterado em relação ao original.
    assert {t.id for t in updated} == {parent.id, child_a.id, child_b.id, other_root.id}


def test_recalculate_wbs_is_idempotent_second_call_reports_no_changes():
    db = session()
    project = _make_project(db, code="PRJ-WBS-2")
    t1 = Task(project_id=project.id, name="A", wbs_code="5", sort_order=0)
    t2 = Task(project_id=project.id, name="B", wbs_code="6", sort_order=10)
    db.add_all([t1, t2])
    db.commit()

    first_pass = recalculate_wbs(db, project.id)
    assert {t.id for t in first_pass} == {t1.id, t2.id}
    second_pass = recalculate_wbs(db, project.id)
    assert second_pass == []


def test_move_task_reparents_and_reorders_siblings():
    db = session()
    project = _make_project(db, code="PRJ-MOVE")
    parent_a = Task(project_id=project.id, name="Pai A", wbs_code="1")
    parent_b = Task(project_id=project.id, name="Pai B", wbs_code="2")
    db.add_all([parent_a, parent_b])
    db.flush()
    child = Task(project_id=project.id, name="Filho", wbs_code="1.1", parent_task_id=parent_a.id, sort_order=0)
    existing_in_b = Task(project_id=project.id, name="Já em B", wbs_code="2.1", parent_task_id=parent_b.id, sort_order=0)
    db.add_all([child, existing_in_b])
    db.commit()

    moved = move_task(db, child.id, new_parent_id=parent_b.id, before_task_id=existing_in_b.id)

    assert moved.parent_task_id == parent_b.id
    # Movida para antes de "Já em B": sort_order menor que o dela.
    assert moved.sort_order < existing_in_b.sort_order


def test_move_task_rejects_moving_into_own_descendant():
    db = session()
    project = _make_project(db, code="PRJ-MOVE-CYCLE")
    parent = Task(project_id=project.id, name="Pai", wbs_code="1")
    db.add(parent)
    db.flush()
    child = Task(project_id=project.id, name="Filho", wbs_code="1.1", parent_task_id=parent.id)
    db.add(child)
    db.commit()

    with pytest.raises(ValueError, match="dentro dela mesma"):
        move_task(db, parent.id, new_parent_id=child.id, before_task_id=None)


def test_task_dot_colors_leaf_rules_and_parent_aggregation():
    db = session()
    project = _make_project(db, code="PRJ-DOT")
    status_date = date(2026, 9, 1)
    parent = Task(project_id=project.id, name="Fase", wbs_code="1")
    db.add(parent)
    db.flush()
    not_started = Task(project_id=project.id, name="Não iniciada", wbs_code="1.1", parent_task_id=parent.id, status=TaskStatus.NOT_STARTED)
    on_time = Task(
        project_id=project.id, name="No prazo", wbs_code="1.2", parent_task_id=parent.id,
        status=TaskStatus.IN_PROGRESS, planned_end_date=date(2026, 9, 10),
    )
    late = Task(
        project_id=project.id, name="Atrasada", wbs_code="1.3", parent_task_id=parent.id,
        status=TaskStatus.IN_PROGRESS, planned_end_date=date(2026, 8, 20),
    )
    db.add_all([not_started, on_time, late])
    db.commit()

    dots = task_dot_colors([parent, not_started, on_time, late], status_date)
    assert dots[not_started.id] == "white"
    assert dots[on_time.id] == "green"
    assert dots[late.id] == "red"
    # Pai com filhos de cores diferentes (branco/verde/vermelho): amarelo.
    assert dots[parent.id] == "yellow"


def test_task_dot_colors_parent_inherits_single_common_color():
    db = session()
    project = _make_project(db, code="PRJ-DOT-2")
    parent = Task(project_id=project.id, name="Fase", wbs_code="1")
    db.add(parent)
    db.flush()
    child_1 = Task(
        project_id=project.id, name="C1", wbs_code="1.1", parent_task_id=parent.id,
        status=TaskStatus.COMPLETED, planned_end_date=date(2026, 8, 1),
    )
    child_2 = Task(
        project_id=project.id, name="C2", wbs_code="1.2", parent_task_id=parent.id,
        status=TaskStatus.IN_PROGRESS, planned_end_date=date(2026, 9, 10),
    )
    db.add_all([child_1, child_2])
    db.commit()

    dots = task_dot_colors([parent, child_1, child_2], date(2026, 9, 1))
    # Ambos os filhos ficam "green" (concluída e no prazo) -> pai herda verde.
    assert dots[child_1.id] == "green"
    assert dots[child_2.id] == "green"
    assert dots[parent.id] == "green"


def test_recalculate_schedule_updates_only_tasks_with_predecessors():
    db = session()
    project = _make_project(db, code="PRJ-RECALC")
    pred = Task(project_id=project.id, name="A", wbs_code="1", planned_start_date=date(2026, 8, 24), planned_end_date=date(2026, 8, 25), duration_days=Decimal("2"))
    succ = Task(project_id=project.id, name="B", wbs_code="2", planned_start_date=date(2026, 9, 1), planned_end_date=date(2026, 9, 2), duration_days=Decimal("2"))
    manual = Task(project_id=project.id, name="C sem predecessora", wbs_code="3", planned_start_date=date(2026, 9, 15), planned_end_date=date(2026, 9, 16))
    db.add_all([pred, succ, manual])
    db.flush()
    db.add(TaskDependency(predecessor_task_id=pred.id, successor_task_id=succ.id))
    db.commit()

    updated = recalculate_schedule(db, project.id, BusinessCalendar())

    assert {t.id for t in updated} == {succ.id}
    assert succ.planned_start_date == date(2026, 8, 26)
    # Tarefa sem predecessora nunca é tocada: início continua manual.
    assert manual.planned_start_date == date(2026, 9, 15)


def test_project_evm_uses_baseline_hours_when_available():
    db = session()
    project = _make_project(db, code="PRJ-EVM")
    project.status_date = date(2026, 9, 1)
    task = Task(
        project_id=project.id, name="T", wbs_code="1",
        estimated_hours=Decimal("20"), progress_percentage=Decimal("50"),
        actual_hours=Decimal("8"), planned_end_date=date(2026, 8, 20),
    )
    db.add(task)
    db.flush()
    # Baseline "congela" um plano diferente do atual (10h em vez de 20h) —
    # PV/EV precisam usar o baseline, não o estimated_hours corrente.
    db.add(
        Baseline(
            project_id=project.id,
            version_name="v1",
            snapshot_data={
                "tasks": [
                    {
                        "id": task.id,
                        "wbs_code": "1",
                        "name": "T",
                        "planned_start_date": None,
                        "planned_end_date": "2026-08-20",
                        "estimated_hours": "10",
                        "status": "IN_PROGRESS",
                    }
                ]
            },
        )
    )
    db.commit()

    result = project_evm(db, project.id)
    assert result["planned_value_hours"] == Decimal("10.00")  # baseline, não os 20h atuais
    assert result["earned_value_hours"] == Decimal("5.00")  # 10h baseline * 50%
    assert result["actual_hours"] == Decimal("8.00")
    assert result["spi"] == Decimal("0.50")  # 5/10
    assert result["cpi"] == Decimal("0.62")  # 5/8 arredondado


def test_project_evm_indices_none_when_denominator_zero():
    db = session()
    project = _make_project(db, code="PRJ-EVM-0")
    task = Task(project_id=project.id, name="T", wbs_code="1", estimated_hours=Decimal("10"))
    db.add(task)
    db.commit()

    result = project_evm(db, project.id, status_date=date(2026, 1, 1))
    assert result["spi"] is None  # nenhuma tarefa com fim <= status_date -> PV=0
    assert result["cpi"] is None  # nenhuma hora apontada ainda -> AC=0


def test_project_statistics_current_baseline_actual_and_variance():
    db = session()
    project = _make_project(db, code="PRJ-STATS")
    task = Task(
        project_id=project.id, name="T", wbs_code="1",
        estimated_hours=Decimal("16"),
        planned_start_date=date(2026, 8, 3), planned_end_date=date(2026, 8, 4),
        actual_start_date=date(2026, 8, 3), actual_end_date=date(2026, 8, 5),
        actual_hours=Decimal("20"), status=TaskStatus.COMPLETED,
    )
    db.add(task)
    db.flush()
    db.add(
        Baseline(
            project_id=project.id,
            version_name="v1",
            snapshot_data={
                "tasks": [
                    {
                        "id": task.id,
                        "wbs_code": "1",
                        "name": "T",
                        "planned_start_date": "2026-08-03",
                        "planned_end_date": "2026-08-03",
                        "estimated_hours": "16",
                        "status": "NOT_STARTED",
                    }
                ]
            },
        )
    )
    db.commit()

    stats = project_statistics(db, project.id)
    assert stats["current"]["finish_date"] == date(2026, 8, 4)
    assert stats["baseline"]["finish_date"] == date(2026, 8, 3)
    assert stats["actual"]["finish_date"] == date(2026, 8, 5)
    assert stats["actual"]["work_hours"] == Decimal("20")
    # current terminou 1 dia útil depois do baseline -> variância positiva.
    assert stats["variance_finish_days"] > 0
    assert stats["percent_complete_work"] == Decimal("125.00")  # 20 real / 16 atual


def test_task_schedule_rows_computes_per_task_spi_cpi():
    """SPI/CPI por tarefa (não só o agregado do projeto) — mesma fórmula de
    project_evm, aplicada a uma tarefa isolada."""
    db = session()
    project = _make_project(db, code="PRJ-ROW-EVM")
    project.status_date = date(2026, 9, 1)
    task = Task(
        project_id=project.id, name="T", wbs_code="1",
        estimated_hours=Decimal("10"), progress_percentage=Decimal("50"),
        actual_hours=Decimal("4"), planned_end_date=date(2026, 8, 1),
    )
    db.add(task)
    db.commit()

    result = task_schedule_rows(db, project)
    row = result["rows"][0]
    # PV = 10h (fim planejado já passou da status_date); EV = 10*50% = 5h.
    assert row["spi"] == Decimal("0.50")  # 5/10
    assert row["cpi"] == Decimal("1.25")  # 5/4
