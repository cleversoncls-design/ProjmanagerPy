from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import (
    Calendar,
    DependencyType,
    Holiday,
    Project,
    Resource,
    ProjectExpense,
    Risk,
    RiskLevel,
    RiskStatus,
    Task,
    TaskAssignment,
    TaskDependency,
    TaskStatus,
    TaskType,
    Timesheet,
    TimesheetStatus,
)

# Duas casas decimais para percentuais e valores monetários calculados nos
# relatórios — mesma precisão das colunas Numeric(*, 2) do banco.
_TWOPLACES = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(_TWOPLACES)


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
    # outerjoin (não join) porque um apontamento avulso (Timesheet.task_id
    # nulo) pode mesmo assim estar alocado a este projeto via
    # Timesheet.project_id — sem isso, hora avulsa nunca entraria no custo
    # real do projeto.
    rows = session.execute(
        select(Timesheet.hours_spent, Resource.internal_cost_per_hour)
        .join(Resource, Resource.id == Timesheet.resource_id)
        .outerjoin(Task, Task.id == Timesheet.task_id)
        .where(
            or_(Task.project_id == project_id, Timesheet.project_id == project_id),
            Timesheet.status != TimesheetStatus.REJECTED,
        )
    ).all()
    timesheet_cost = sum((Decimal(hours) * Decimal(rate) for hours, rate in rows), Decimal("0"))
    expense_cost = sum((Decimal(x) for x in session.scalars(select(ProjectExpense.amount).where(ProjectExpense.project_id == project_id)).all()), Decimal("0"))
    real_cost = timesheet_cost + expense_cost
    sold = Decimal(project.sold_value or 0)
    return {"sold_value": sold, "timesheet_cost": timesheet_cost, "expense_cost": expense_cost, "real_cost": real_cost, "profit_margin": sold - real_cost}


def _progress_from_tasks(tasks: list[Task]) -> dict:
    """% concluído ponderado pelas estimated_hours de cada tarefa (uma
    tarefa maior pesa mais no percentual do que uma pequena); cai para
    média simples quando nenhuma tarefa tem horas estimadas. Recebe a
    lista de tarefas já carregada para permitir reaproveitamento (ver
    `portfolio_rows`, que evita reconsultar o banco por projeto)."""
    tasks_total = len(tasks)
    tasks_remaining = sum(1 for t in tasks if t.status != TaskStatus.COMPLETED)
    tasks_by_status: dict[str, int] = defaultdict(int)
    for t in tasks:
        tasks_by_status[t.status.value] += 1
    total_hours = sum((Decimal(t.estimated_hours or 0) for t in tasks), Decimal("0"))
    if total_hours > 0:
        weighted = sum((Decimal(t.estimated_hours or 0) * Decimal(t.progress_percentage or 0) for t in tasks), Decimal("0"))
        percent_complete = weighted / total_hours
    elif tasks_total:
        percent_complete = sum((Decimal(t.progress_percentage or 0) for t in tasks), Decimal("0")) / tasks_total
    else:
        percent_complete = Decimal("0")
    return {
        "tasks_total": tasks_total,
        "tasks_remaining": tasks_remaining,
        "tasks_by_status": dict(tasks_by_status),
        "percent_complete": _q(percent_complete),
    }


def project_progress(session: Session, project_id: str) -> dict:
    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)).all())
    return _progress_from_tasks(tasks)


def _next_milestone(tasks: list[Task]) -> tuple[str | None, date | None]:
    today = date.today()
    upcoming = [t for t in tasks if t.is_milestone and t.planned_end_date and t.planned_end_date >= today]
    if not upcoming:
        return None, None
    nxt = min(upcoming, key=lambda t: t.planned_end_date)
    return nxt.name, nxt.planned_end_date


def portfolio_rows(session: Session, projects: list[Project], *, include_financials: bool) -> list[dict]:
    """Uma linha por projeto (status, % concluído, margem, próximo marco) —
    usada tanto por GET /reports/portfolio quanto pela seção `portfolio` de
    GET /dashboard. `include_financials=False` (perfis externos) omite a
    margem, no mesmo padrão de ocultação usado em ProjectDetail."""
    rows: list[dict] = []
    for project in projects:
        tasks = list(session.scalars(select(Task).where(Task.project_id == project.id)).all())
        progress = _progress_from_tasks(tasks)
        milestone_name, milestone_date = _next_milestone(tasks)
        margin = None
        if include_financials:
            margin = project_financials(session, project.id)["profit_margin"]
        rows.append(
            {
                "id": project.id,
                "code": project.code,
                "name": project.name,
                "status": project.status,
                "percent_complete": progress["percent_complete"],
                "tasks_total": progress["tasks_total"],
                "tasks_remaining": progress["tasks_remaining"],
                "margin": margin,
                "next_milestone_name": milestone_name,
                "next_milestone_date": milestone_date,
            }
        )
    return rows


def financials_by_task_type(session: Session, project_id: str) -> dict[str, dict[str, Decimal]]:
    """Quebra do custo real do projeto entre horas de GESTÃO e de
    CONSULTORIA (Task.task_type). Um apontamento avulso vinculado só ao
    projeto (Timesheet.task_id nulo) não tem task_type — entra no bucket
    "ADHOC" em vez de ser descartado ou atribuído arbitrariamente a uma das
    duas bolsas contratadas."""
    rows = session.execute(
        select(Timesheet.hours_spent, Resource.internal_cost_per_hour, Task.task_type)
        .join(Resource, Resource.id == Timesheet.resource_id)
        .outerjoin(Task, Task.id == Timesheet.task_id)
        .where(
            or_(Task.project_id == project_id, Timesheet.project_id == project_id),
            Timesheet.status != TimesheetStatus.REJECTED,
        )
    ).all()
    buckets: dict[str, dict[str, Decimal]] = {
        TaskType.MANAGEMENT.value: {"hours": Decimal("0"), "cost": Decimal("0")},
        TaskType.CONSULTING.value: {"hours": Decimal("0"), "cost": Decimal("0")},
        "ADHOC": {"hours": Decimal("0"), "cost": Decimal("0")},
    }
    for hours, rate, task_type in rows:
        key = task_type.value if task_type is not None else "ADHOC"
        buckets[key]["hours"] += Decimal(hours)
        buckets[key]["cost"] += Decimal(hours) * Decimal(rate)
    for bucket in buckets.values():
        bucket["hours"] = _q(bucket["hours"])
        bucket["cost"] = _q(bucket["cost"])
    return buckets


def project_burndown(session: Session, project_id: str) -> list[dict]:
    """Burndown calculado sob demanda a partir dos dados atuais — sem
    snapshot diário armazenado (decisão de design: mais simples e nunca
    fica dessincronizado dos dados reais; um snapshot fica disponível via
    Baseline se algum dia for preciso "congelar" um burndown histórico).

    - "Planejado": assume que cada tarefa consome 100% da sua
      estimated_hours exatamente em planned_end_date.
    - "Realizado": acumulado de horas apontadas (Timesheet.hours_spent,
      excluindo REJECTED) até cada data amostrada.

    Amostragem semanal entre o início e o fim do projeto (datas do próprio
    projeto se informadas; senão o menor planned_start_date / maior
    planned_end_date entre as tarefas). Sem essas datas, ou sem nenhuma
    hora estimada, retorna lista vazia — não há uma linha de base para
    desenhar o gráfico.
    """
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("Projeto não encontrado")
    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)).all())
    total_hours = sum((Decimal(t.estimated_hours or 0) for t in tasks), Decimal("0"))
    starts = [t.planned_start_date for t in tasks if t.planned_start_date]
    ends = [t.planned_end_date for t in tasks if t.planned_end_date]
    start = project.start_date or (min(starts) if starts else None)
    end = project.end_date or (max(ends) if ends else None)
    if not start or not end or start > end or total_hours <= 0:
        return []

    timesheet_rows = session.execute(
        select(Timesheet.date, Timesheet.hours_spent)
        .outerjoin(Task, Task.id == Timesheet.task_id)
        .where(
            or_(Task.project_id == project_id, Timesheet.project_id == project_id),
            Timesheet.status != TimesheetStatus.REJECTED,
        )
    ).all()

    def planned_remaining(as_of: date) -> Decimal:
        done = sum((Decimal(t.estimated_hours or 0) for t in tasks if t.planned_end_date and t.planned_end_date <= as_of), Decimal("0"))
        return _q(total_hours - done)

    def actual_remaining(as_of: date) -> Decimal:
        done = sum((Decimal(hours) for ts_date, hours in timesheet_rows if ts_date <= as_of), Decimal("0"))
        return _q(total_hours - done)

    points: list[dict] = []
    current = start
    while current < end:
        points.append(
            {"date": current, "planned_remaining_hours": planned_remaining(current), "actual_remaining_hours": actual_remaining(current)}
        )
        current += timedelta(days=7)
    points.append({"date": end, "planned_remaining_hours": planned_remaining(end), "actual_remaining_hours": actual_remaining(end)})
    return points


def resource_utilization(session: Session, *, start: date, end: date, resource_id: str | None = None) -> list[dict]:
    """Carga de trabalho por recurso no período [start, end]:

    - `capacity_hours`: dias úteis do período (pelo calendário pessoal do
      recurso, se houver; senão segunda a sexta sem feriados) ×
      daily_capacity_hours.
    - `actual_hours`: soma de todos os timesheets do recurso no período
      (vinculados a tarefa, avulsos com projeto, ou horas administrativas),
      excluindo REJECTED.
    - `allocated_hours`: soma de TaskAssignment.allocated_hours em TODAS as
      tarefas do recurso — não é filtrada pelo período porque
      TaskAssignment não tem data própria neste modelo; é o total alocado
      no momento, não o alocado especificamente dentro de [start, end].
    """
    stmt = select(Resource)
    if resource_id:
        stmt = stmt.where(Resource.id == resource_id)
    resources = list(session.scalars(stmt).all())

    rows: list[dict] = []
    for resource in resources:
        cal = calendar_from_db(session, resource.calendar_id) if resource.calendar_id else BusinessCalendar()
        working_days = 0
        current = start
        while current <= end:
            if cal.is_working_day(current):
                working_days += 1
            current += timedelta(days=1)
        capacity_hours = _q(Decimal(resource.daily_capacity_hours or 0) * working_days)

        actual_hours = sum(
            (
                Decimal(h)
                for h in session.scalars(
                    select(Timesheet.hours_spent).where(
                        Timesheet.resource_id == resource.id,
                        Timesheet.date >= start,
                        Timesheet.date <= end,
                        Timesheet.status != TimesheetStatus.REJECTED,
                    )
                ).all()
            ),
            Decimal("0"),
        )
        allocated_hours = sum(
            (Decimal(h) for h in session.scalars(select(TaskAssignment.allocated_hours).where(TaskAssignment.resource_id == resource.id)).all()),
            Decimal("0"),
        )
        utilization_percentage = _q((actual_hours / capacity_hours) * 100) if capacity_hours > 0 else None
        rows.append(
            {
                "resource_id": resource.id,
                "user_id": resource.user_id,
                "role_title": resource.role_title,
                "period_start": start,
                "period_end": end,
                "capacity_hours": capacity_hours,
                "allocated_hours": _q(allocated_hours),
                "actual_hours": _q(actual_hours),
                "utilization_percentage": utilization_percentage,
            }
        )
    return rows


def risk_matrix(session: Session, project_id: str) -> dict:
    """Grade probabilidade × impacto (contagem por célula) e a lista de
    riscos HIGH/HIGH ainda não fechados, para priorização rápida."""
    risks = list(session.scalars(select(Risk).where(Risk.project_id == project_id)).all())
    grid: dict[str, dict[str, int]] = {p.value: {i.value: 0 for i in RiskLevel} for p in RiskLevel}
    high_priority: list[Risk] = []
    for risk in risks:
        grid[risk.probability.value][risk.impact.value] += 1
        if risk.probability == RiskLevel.HIGH and risk.impact == RiskLevel.HIGH and risk.status != RiskStatus.CLOSED:
            high_priority.append(risk)
    return {"project_id": project_id, "grid": grid, "high_priority": high_priority}


def velocity_series(
    session: Session,
    *,
    start: date,
    end: date,
    granularity: str = "week",
    project_id: str | None = None,
    resource_id: str | None = None,
) -> list[dict]:
    """"Velocity" aqui é literal, conforme decisão do usuário: horas
    entregues por semana ou mês — não é velocidade de Scrum/story points e
    não depende de nenhuma entidade de sprint (que este sistema não
    modela)."""
    stmt = (
        select(Timesheet.date, Timesheet.hours_spent)
        .outerjoin(Task, Task.id == Timesheet.task_id)
        .where(Timesheet.date >= start, Timesheet.date <= end, Timesheet.status != TimesheetStatus.REJECTED)
    )
    if project_id:
        stmt = stmt.where(or_(Task.project_id == project_id, Timesheet.project_id == project_id))
    if resource_id:
        stmt = stmt.where(Timesheet.resource_id == resource_id)
    rows = session.execute(stmt).all()

    buckets: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
    for ts_date, hours in rows:
        if granularity == "month":
            period_start = ts_date.replace(day=1)
        else:
            period_start = ts_date - timedelta(days=ts_date.weekday())  # segunda-feira da semana
        buckets[period_start] += Decimal(hours)

    return [{"period_start": period_start, "hours_delivered": _q(hours)} for period_start, hours in sorted(buckets.items())]


def project_roi(session: Session, project_id: str) -> dict:
    """ROI = margem ÷ custo real (retorno sobre o custo efetivamente
    incorrido no projeto). Não há uma receita externa própria a medir além
    do valor vendido do pacote (sold_value), então esta é a leitura de ROI
    mais direta com os dados hoje modelados — assumida explicitamente aqui
    porque a definição de "ROI" para consultoria de projetos não é única.
    None quando ainda não há custo real lançado (divisão por zero)."""
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("Projeto não encontrado")
    fin = project_financials(session, project_id)
    real_cost = fin["real_cost"]
    roi_percentage = _q((fin["profit_margin"] / real_cost) * 100) if real_cost > 0 else None
    return {"project_id": project_id, "code": project.code, "sold_value": fin["sold_value"], "real_cost": real_cost, "roi_percentage": roi_percentage}
