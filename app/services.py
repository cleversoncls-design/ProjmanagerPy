from __future__ import annotations

import math
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import (
    Baseline,
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

# "Trabalho" (estimated_hours) sem nenhum recurso alocado ainda assume uma
# única FTE genérica de 8h/dia — mesmo padrão do daily_capacity_hours
# default em Resource. Ver apply_effort_driven/capacity_hours_per_day_for_task.
DEFAULT_CAPACITY_HOURS_PER_DAY = Decimal("8")

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


def _whole_days(duration_days: Decimal) -> int:
    """`duration_days` pode ser fracionário (ex.: 0,15 dia = ~1,2h, visto em
    cronogramas importados do MS Project) — para POSICIONAR datas no
    calendário de dias úteis, arredonda pra cima com mínimo de 1 dia. O
    valor fracionário original continua guardado em Task.duration_days
    (usado tal e qual no cálculo de horas de `apply_effort_driven`); só o
    posicionamento no calendário é inteiro."""
    return max(1, math.ceil(float(duration_days)))


def _end_date_from_duration(cal: BusinessCalendar, start: date, duration_days: Decimal) -> date:
    """Data final = início + duração (dias úteis), usando Task.duration_days
    como fonte da verdade — em vez de re-derivar a duração a partir de
    datas planejadas antigas, como a versão anterior deste motor fazia
    antes de duration_days existir como campo."""
    aligned_start = cal.next_working_day(start)
    return cal.add_working_days(aligned_start, _whole_days(duration_days) - 1)


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
        return cal.add_working_days(lagged_end, -(_whole_days(successor.duration_days) - 1))
    # SF: sucessora termina quando a predecessora inicia; derive início pela duração atual.
    return cal.add_working_days(lagged_start, -(_whole_days(successor.duration_days) - 1))


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
        successor.planned_start_date = new_start
        successor.planned_end_date = _end_date_from_duration(cal, new_start, successor.duration_days)
        if successor.planned_start_date != old_start:
            updated.append(successor)

    session.flush()
    return updated


def recalculate_schedule(session: Session, project_id: str, cal: BusinessCalendar) -> list[Task]:
    """Recalcula as datas de TODAS as tarefas do projeto que têm alguma
    predecessora, varrendo o grafo de dependências inteiro de uma vez —
    para usar como botão "recalcular tudo" depois de várias edições em
    lote (mover tarefas, trocar predecessoras, mudar durações), em vez de
    depender de chamar `reschedule_cascade` tarefa por tarefa.

    Tarefas SEM nenhuma predecessora nunca são tocadas aqui: a data de
    início delas é sempre informação manual (mesma regra de
    `reschedule_cascade`, só que aplicada ao projeto inteiro de uma vez).
    """
    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)).all())
    task_ids = {t.id for t in tasks}
    tasks_by_id = {t.id: t for t in tasks}
    if not task_ids:
        return []

    deps = list(
        session.scalars(
            select(TaskDependency).where(
                TaskDependency.predecessor_task_id.in_(task_ids),
                TaskDependency.successor_task_id.in_(task_ids),
            )
        ).all()
    )
    deps_by_successor: dict[str, list[TaskDependency]] = defaultdict(list)
    in_degree: dict[str, int] = {tid: 0 for tid in task_ids}
    successors_by_predecessor: dict[str, list[str]] = defaultdict(list)
    for dep in deps:
        deps_by_successor[dep.successor_task_id].append(dep)
        in_degree[dep.successor_task_id] += 1
        successors_by_predecessor[dep.predecessor_task_id].append(dep.successor_task_id)

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
    if len(order) != len(task_ids):
        raise ValueError("Ciclo detectado nas dependências")

    updated: list[Task] = []
    for tid in order:
        deps_here = deps_by_successor.get(tid)
        if not deps_here:
            continue  # sem predecessora: início manual, não recalcula
        successor = tasks_by_id[tid]
        candidate_starts: list[date] = []
        for dep in deps_here:
            predecessor = tasks_by_id.get(dep.predecessor_task_id)
            if not predecessor or not predecessor.planned_start_date or not predecessor.planned_end_date:
                continue
            candidate_starts.append(_successor_start(cal, predecessor, successor, dep))
        if not candidate_starts:
            continue
        new_start = max(candidate_starts)
        old_start = successor.planned_start_date
        successor.planned_start_date = new_start
        successor.planned_end_date = _end_date_from_duration(cal, new_start, successor.duration_days)
        if successor.planned_start_date != old_start:
            updated.append(successor)

    session.flush()
    return updated


def calendar_for_project(session: Session, project: Project) -> BusinessCalendar:
    """Calendário efetivo do projeto: o que estiver em Project.calendar_id,
    ou o padrão (segunda a sexta, sem feriados) se nenhum foi atribuído."""
    if project.calendar_id:
        return calendar_from_db(session, project.calendar_id)
    return BusinessCalendar()


def capacity_hours_per_day_for_task(session: Session, task_id: str) -> Decimal:
    """Soma da capacidade diária dos recursos alocados na tarefa — usada
    como o "×horas/dia×nº de recursos" do modelo effort-driven. Sem nenhum
    recurso alocado ainda, assume uma FTE genérica (DEFAULT_CAPACITY_HOURS_PER_DAY),
    para Duração×Trabalho continuarem fazendo sentido antes de qualquer
    alocação."""
    rows = session.execute(
        select(Resource.daily_capacity_hours)
        .join(TaskAssignment, TaskAssignment.resource_id == Resource.id)
        .where(TaskAssignment.task_id == task_id)
    ).all()
    total = sum((Decimal(r[0]) for r in rows), Decimal("0"))
    return total if total > 0 else DEFAULT_CAPACITY_HOURS_PER_DAY


def apply_effort_driven(
    task: Task,
    *,
    duration_days: Decimal | None,
    estimated_hours: Decimal | None,
    capacity_hours_per_day: Decimal,
) -> None:
    """Agendamento effort-driven (estilo MS Project, "Fixed Units"):
    Trabalho = Duração × capacidade diária somada dos recursos alocados.

    - Informar `duration_days` (com ou sem `estimated_hours` junto): Duração
      manda, Trabalho é recalculado a partir dela — precedência documentada
      em TaskCreate/TaskUpdate.
    - Informar só `estimated_hours`: Trabalho manda, Duração é recalculada
      pelo caminho inverso (Trabalho ÷ capacidade).
    - Nenhum dos dois: no-op — usado quando quem mudou foi a ALOCAÇÃO de
      recurso (ver assign_resource/remove assignment em routers/tasks.py),
      que mantém a Duração fixa e recalcula só o Trabalho com a nova
      capacidade total (equivalente ao "Fixed Units": mais gente no mesmo
      prazo = mais trabalho total, não prazo menor).
    """
    if duration_days is not None:
        task.duration_days = duration_days
        task.estimated_hours = duration_days * capacity_hours_per_day
    elif estimated_hours is not None:
        task.estimated_hours = estimated_hours
        if capacity_hours_per_day > 0:
            task.duration_days = estimated_hours / capacity_hours_per_day
    else:
        task.estimated_hours = task.duration_days * capacity_hours_per_day


def recalculate_wbs(session: Session, project_id: str) -> list[Task]:
    """Renumera o WBS/EAP de todas as tarefas do projeto a partir da
    hierarquia (parent_task_id) e da ordem manual (sort_order, com o
    wbs_code atual como desempate estável na primeira vez que isso roda).

    Passa por um código temporário único (`_tmp_<id>`) antes de gravar os
    códigos finais: como wbs_code tem uma constraint de unicidade por
    projeto, renumerar "in-place" arriscaria uma trocar temporariamente
    para o código que outra tarefa ainda não trocou — o passo intermediário
    evita essa colisão.
    """
    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)).all())
    if not tasks:
        return []
    original_code = {t.id: t.wbs_code for t in tasks}
    by_parent: dict[str | None, list[Task]] = defaultdict(list)
    for t in tasks:
        by_parent[t.parent_task_id].append(t)
    for siblings in by_parent.values():
        siblings.sort(key=lambda t: (t.sort_order, original_code[t.id]))

    for t in tasks:
        t.wbs_code = f"_tmp_{t.id}"
    session.flush()

    updated: list[Task] = []

    def assign(parent_id: str | None, prefix_parts: list[int]) -> None:
        for idx, t in enumerate(by_parent.get(parent_id, []), start=1):
            parts = prefix_parts + [idx]
            code = ".".join(str(p) for p in parts)
            if original_code[t.id] != code:
                updated.append(t)
            t.wbs_code = code
            assign(t.id, parts)

    assign(None, [])
    session.flush()
    return updated


def move_task(session: Session, task_id: str, *, new_parent_id: str | None, before_task_id: str | None) -> Task:
    """Move uma tarefa para outro pai e/ou reordena entre as irmãs no
    destino. Não mexe em wbs_code (chame `recalculate_wbs` depois) nem em
    datas planejadas (chame `reschedule_cascade`/`recalculate_schedule`
    depois, se a tarefa tiver predecessoras/sucessoras)."""
    task = session.get(Task, task_id)
    if not task:
        raise ValueError("Tarefa não encontrada")

    if new_parent_id:
        parent = session.get(Task, new_parent_id)
        if not parent or parent.project_id != task.project_id:
            raise ValueError("new_parent_id precisa ser uma tarefa do mesmo projeto")
        cursor: Task | None = parent
        while cursor:
            if cursor.id == task.id:
                raise ValueError("Não é possível mover uma tarefa para dentro dela mesma (ou de uma descendente)")
            cursor = session.get(Task, cursor.parent_task_id) if cursor.parent_task_id else None

    siblings = [
        s
        for s in session.scalars(
            select(Task)
            .where(Task.project_id == task.project_id, Task.parent_task_id == new_parent_id)
            .order_by(Task.sort_order)
        ).all()
        if s.id != task.id
    ]

    if before_task_id:
        before = session.get(Task, before_task_id)
        if not before or before.parent_task_id != new_parent_id or before.project_id != task.project_id:
            raise ValueError("before_task_id precisa ser uma tarefa-irmã já existente no destino")
        index = next(i for i, s in enumerate(siblings) if s.id == before_task_id)
    else:
        index = len(siblings)

    siblings.insert(index, task)
    task.parent_task_id = new_parent_id
    for i, s in enumerate(siblings):
        s.sort_order = i * 10
    session.flush()
    return task


def _leaf_status_dot(task: Task, status_date: date) -> str:
    """Bolinha de status de uma tarefa FOLHA (sem filhas) — regras
    combinadas com o usuário: branca=por iniciar, vermelha=atrasada
    (marcada DELAYED, ou planned_end_date já passou da status_date e ainda
    não está 100% concluída), verde=dentro do prazo (inclui concluída)."""
    if task.status == TaskStatus.NOT_STARTED:
        return "white"
    if task.status == TaskStatus.DELAYED:
        return "red"
    if task.status != TaskStatus.COMPLETED and task.planned_end_date and task.planned_end_date < status_date:
        return "red"
    return "green"


def task_dot_colors(tasks: list[Task], status_date: date) -> dict[str, str]:
    """Bolinha de status por tarefa, já resolvendo a agregação de
    tarefas-pai: amarela sempre que as filhas (recursivamente, usando a
    bolinha JÁ agregada de cada uma) tiverem mais de uma cor diferente
    entre si; senão, herda a cor única comum."""
    children_by_parent: dict[str | None, list[Task]] = defaultdict(list)
    for t in tasks:
        children_by_parent[t.parent_task_id].append(t)

    colors: dict[str, str] = {}

    def resolve(task: Task) -> str:
        if task.id in colors:
            return colors[task.id]
        children = children_by_parent.get(task.id, [])
        if not children:
            color = _leaf_status_dot(task, status_date)
        else:
            child_colors = {resolve(child) for child in children}
            color = child_colors.pop() if len(child_colors) == 1 else "yellow"
        colors[task.id] = color
        return color

    for t in tasks:
        resolve(t)
    return colors


def _latest_baseline_task_map(session: Session, project_id: str) -> dict[str, dict] | None:
    baseline = session.scalar(
        select(Baseline).where(Baseline.project_id == project_id).order_by(Baseline.created_at.desc())
    )
    if not baseline:
        return None
    return {row["id"]: row for row in baseline.snapshot_data.get("tasks", [])}


def _task_rollups(tasks: list[Task], cal: BusinessCalendar) -> dict[str, dict]:
    """Agrega Duração/Trabalho/Início/Fim para tarefas-pai (WBS) a partir das
    descendentes — mesmo padrão de agregação recursiva de `task_dot_colors`
    (memoização por id, uma passada), só que para os campos de cronograma em
    vez da bolinha de status.

    Uma tarefa-pai nunca teve essas colunas próprias preenchidas de forma
    útil (o próprio motor de agendamento nunca escreve nelas: cascata e
    recálculo de EAP só mexem em tarefas-folha) — daí aparecerem em branco/
    0h na grade sem isto. O valor "de verdade" mora nas folhas; o pai só
    reflete o agregado, calculado sob demanda (nunca gravado em coluna,
    mesmo espírito de status_dot/planned_percent_complete).

    Início = menor planned_start_date entre as folhas descendentes.
    Fim = maior planned_end_date entre as folhas descendentes.
    Trabalho = soma de estimated_hours das folhas descendentes.
    Duração = dias úteis (calendário do projeto) entre Início e Fim — não é
    soma das durações das filhas (que podem rodar em paralelo).

    Retorna só as entradas com pelo menos uma filha; o chamador usa os
    campos próprios da tarefa para as demais (folhas)."""
    children_by_parent: dict[str | None, list[Task]] = defaultdict(list)
    for t in tasks:
        children_by_parent[t.parent_task_id].append(t)

    memo: dict[str, tuple[date | None, date | None, Decimal]] = {}

    def resolve(task: Task) -> tuple[date | None, date | None, Decimal]:
        if task.id in memo:
            return memo[task.id]
        children = children_by_parent.get(task.id, [])
        if not children:
            result = (task.planned_start_date, task.planned_end_date, Decimal(task.estimated_hours or 0))
        else:
            starts: list[date] = []
            ends: list[date] = []
            hours = Decimal("0")
            for child in children:
                c_start, c_end, c_hours = resolve(child)
                if c_start:
                    starts.append(c_start)
                if c_end:
                    ends.append(c_end)
                hours += c_hours
            result = (min(starts) if starts else None, max(ends) if ends else None, hours)
        memo[task.id] = result
        return result

    rollups: dict[str, dict] = {}
    for t in tasks:
        start, end, hours = resolve(t)
        if children_by_parent.get(t.id):
            duration = Decimal(_duration_days(cal, start, end)) if start and end else None
            rollups[t.id] = {"start": start, "end": end, "hours": hours, "duration": duration}
    return rollups


def _natural_sort_key(text: str) -> tuple:
    """Chave de comparação "numérica por trecho" pra strings tipo WBS
    (ex.: "1.2" < "1.10", não o contrário como daria a comparação de string
    pura) — mesmo critério do `localeCompare(..., {numeric: true})` usado
    em `buildOrderedTasks` no frontend (ver ProjectDetailPage.jsx)."""
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", text or ""))


def order_tasks_hierarchically(tasks: list[Task]) -> list[Task]:
    """Ordena tarefas na ordem "natural" da EAP/WBS: hierarquia
    (parent_task_id) + ordem manual entre irmãs (sort_order, com wbs_code
    como desempate) — igual ao `recalculate_wbs` usa pra renumerar e ao
    `buildOrderedTasks` do frontend usa pra montar a grade de Tarefas.
    Usada em qualquer lugar que precise listar tarefas nessa ordem sem
    depender de `ORDER BY wbs_code` do banco (que é só comparação de
    string — quebra a partir de 10 tarefas-irmãs, ex.: "1.10" antes de
    "1.2"), como o Gantt e a exportação para Excel (ambos consomem
    `task_schedule_rows`, ver abaixo)."""
    by_parent: dict[str | None, list[Task]] = defaultdict(list)
    for t in tasks:
        by_parent[t.parent_task_id].append(t)
    for siblings in by_parent.values():
        siblings.sort(key=lambda t: (t.sort_order, _natural_sort_key(t.wbs_code)))

    ordered: list[Task] = []

    def visit(parent_id: str | None) -> None:
        for t in by_parent.get(parent_id, []):
            ordered.append(t)
            visit(t.id)

    visit(None)
    # Defensivo: se alguma tarefa tiver parent_task_id "órfão" (não deveria
    # acontecer — FK é sempre para outra tarefa do mesmo projeto — mas não
    # pode sumir silenciosamente do Gantt/exportação se acontecer).
    if len(ordered) != len(tasks):
        seen = {t.id for t in ordered}
        ordered.extend(t for t in tasks if t.id not in seen)
    return ordered


def task_schedule_rows(session: Session, project: Project) -> dict:
    """Monta a grade de cronograma (bolinha de status + linha base + %
    previsto por tarefa) usada por GET /projects/{id}/schedule — junta o
    que já existe em Task com o que precisa ser calculado sob demanda
    (nunca fica guardado em coluna, porque muda conforme status_date e o
    baseline mais recente).

    As tarefas voltam na ordem hierárquica da EAP/WBS (ver
    order_tasks_hierarchically) — GET /schedule alimenta tanto o Gantt
    quanto a exportação para Excel (app/exports.py), e nenhum dos dois
    reordena por conta própria."""
    status_date = project.status_date or date.today()
    tasks = list(session.scalars(select(Task).where(Task.project_id == project.id)).all())
    tasks = order_tasks_hierarchically(tasks)
    dots = task_dot_colors(tasks, status_date)
    baseline_map = _latest_baseline_task_map(session, project.id)
    cal = calendar_for_project(session, project)
    rollups = _task_rollups(tasks, cal)

    def _baseline_field(row: dict | None, direct_key: str, rollup_key: str):
        """Tarefa-folha usa o campo direto do snapshot; tarefa-pai (sem
        planned_start_date/end_date/estimated_hours próprios, ver
        _task_rollups) cai pro agregado que create_baseline também gravou
        no snapshot (rollup_start_date/rollup_end_date/rollup_estimated_hours)
        — mesma regra de fallback rollup ?? campo próprio usada em toda a
        grade "ao vivo", só que lendo de um snapshot congelado em vez das
        tarefas atuais. Baselines salvos antes desta rollup existir no
        snapshot simplesmente não têm a chave — cai pra None, não quebra."""
        if not row:
            return None
        return row.get(direct_key) or row.get(rollup_key)

    rows = []
    for t in tasks:
        baseline_row = baseline_map.get(t.id) if baseline_map else None
        rollup = rollups.get(t.id)
        # Pra % previsto, uma tarefa-pai usa o intervalo agregado das
        # descendentes (rollup) — sem isso, ficaria sempre em 0% porque
        # planned_start_date/end_date da própria linha-pai são nulos.
        effective_start = rollup["start"] if rollup else t.planned_start_date
        effective_end = rollup["end"] if rollup else t.planned_end_date
        planned_percent = Decimal("100") if (effective_end and effective_end <= status_date) else Decimal("0")
        if effective_start and effective_end and effective_start <= status_date < effective_end:
            total_span = max((effective_end - effective_start).days, 1)
            elapsed = (status_date - effective_start).days
            planned_percent = _q(Decimal(max(elapsed, 0)) / Decimal(total_span) * 100)

        # SPI/CPI POR TAREFA — mesma lógica de project_evm (base de horas,
        # usando o baseline mais recente quando existe), só que aplicada a
        # uma única tarefa em vez de somada no projeto inteiro.
        baseline_hours = Decimal(baseline_row["estimated_hours"]) if baseline_row and baseline_row.get("estimated_hours") else None
        task_planned_hours = baseline_hours if baseline_hours is not None else Decimal(t.estimated_hours or 0)
        task_planned_end = (
            date.fromisoformat(baseline_row["planned_end_date"])
            if baseline_row and baseline_row.get("planned_end_date")
            else t.planned_end_date
        )
        task_pv = task_planned_hours if (task_planned_end and task_planned_end <= status_date) else Decimal("0")
        task_ev = task_planned_hours * Decimal(t.progress_percentage or 0) / 100
        task_ac = Decimal(t.actual_hours or 0)
        task_spi = _q(task_ev / task_pv) if task_pv > 0 else None
        task_cpi = _q(task_ev / task_ac) if task_ac > 0 else None

        rows.append(
            {
                "task": t,
                "status_dot": dots.get(t.id, "white"),
                "rollup_start_date": rollup["start"] if rollup else None,
                "rollup_end_date": rollup["end"] if rollup else None,
                "rollup_duration_days": rollup["duration"] if rollup else None,
                "rollup_estimated_hours": rollup["hours"] if rollup else None,
                "baseline_start_date": (
                    date.fromisoformat(_baseline_field(baseline_row, "planned_start_date", "rollup_start_date"))
                    if _baseline_field(baseline_row, "planned_start_date", "rollup_start_date")
                    else None
                ),
                "baseline_end_date": (
                    date.fromisoformat(_baseline_field(baseline_row, "planned_end_date", "rollup_end_date"))
                    if _baseline_field(baseline_row, "planned_end_date", "rollup_end_date")
                    else None
                ),
                "baseline_estimated_hours": (
                    Decimal(_baseline_field(baseline_row, "estimated_hours", "rollup_estimated_hours"))
                    if _baseline_field(baseline_row, "estimated_hours", "rollup_estimated_hours")
                    else None
                ),
                "planned_percent_complete": planned_percent,
                "spi": task_spi,
                "cpi": task_cpi,
            }
        )
    return {"status_date": status_date, "rows": rows}


def project_evm(session: Session, project_id: str, status_date: date | None = None) -> dict:
    """SPI/CPI e % previsto em base de HORAS (estimated_hours), não
    monetária — decisão registrada com o usuário. PV e EV usam as horas do
    baseline mais recente quando existe (prática padrão de EVM: o "budget"
    é o plano congelado, não o plano que continua sendo replanejado); sem
    nenhum baseline ainda, caem para as horas/datas planejadas atuais.

    - PV (planned value): soma das horas orçadas das tarefas cujo fim
      planejado (baseline ou atual) já passou da status_date — "quanto
      trabalho deveria ter sido concluído até aqui".
    - EV (earned value): soma das horas orçadas × % concluído de CADA
      tarefa, na mesma base de horas do PV.
    - AC (actual cost, em horas): soma de Task.actual_hours.
    - SPI = EV/PV, CPI = EV/AC — None quando o denominador é zero.
    """
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("Projeto não encontrado")
    status_date = status_date or project.status_date or date.today()
    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)).all())
    baseline_map = _latest_baseline_task_map(session, project_id)

    def planned_hours(t: Task) -> Decimal:
        row = baseline_map.get(t.id) if baseline_map else None
        if row and row.get("estimated_hours"):
            return Decimal(row["estimated_hours"])
        return Decimal(t.estimated_hours or 0)

    def planned_end(t: Task) -> date | None:
        row = baseline_map.get(t.id) if baseline_map else None
        if row and row.get("planned_end_date"):
            return date.fromisoformat(row["planned_end_date"])
        return t.planned_end_date

    total_planned_hours = sum((planned_hours(t) for t in tasks), Decimal("0"))
    pv = sum((planned_hours(t) for t in tasks if planned_end(t) and planned_end(t) <= status_date), Decimal("0"))
    ev = sum((planned_hours(t) * Decimal(t.progress_percentage or 0) / 100 for t in tasks), Decimal("0"))
    ac = sum((Decimal(t.actual_hours or 0) for t in tasks), Decimal("0"))

    spi = _q(ev / pv) if pv > 0 else None
    cpi = _q(ev / ac) if ac > 0 else None
    planned_percent_complete = _q((pv / total_planned_hours) * 100) if total_planned_hours > 0 else Decimal("0")
    percent_complete = _progress_from_tasks(tasks)["percent_complete"]

    return {
        "status_date": status_date,
        "planned_value_hours": _q(pv),
        "earned_value_hours": _q(ev),
        "actual_hours": _q(ac),
        "spi": spi,
        "cpi": cpi,
        "planned_percent_complete": planned_percent_complete,
        "percent_complete": percent_complete,
    }


def project_statistics(session: Session, project_id: str) -> dict:
    """Espelha a caixa "Project Statistics" do MS Project. Uma simplificação
    honesta: este sistema não faz custeio completo por recurso/tarefa como
    o MS Project, então a coluna "Cost" só é preenchida em `actual` (usando
    o mesmo custo real de `project_financials`) — em `current`/`baseline`
    fica None em vez de inventar um número."""
    project = session.get(Project, project_id)
    if not project:
        raise ValueError("Projeto não encontrado")
    cal = calendar_for_project(session, project)
    tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)).all())

    starts = [t.planned_start_date for t in tasks if t.planned_start_date]
    ends = [t.planned_end_date for t in tasks if t.planned_end_date]
    current_start = project.start_date or (min(starts) if starts else None)
    current_finish = project.end_date or (max(ends) if ends else None)
    current_duration = Decimal(_duration_days(cal, current_start, current_finish)) if current_start and current_finish else Decimal("0")
    current_work = sum((Decimal(t.estimated_hours or 0) for t in tasks), Decimal("0"))
    current = {
        "start_date": current_start,
        "finish_date": current_finish,
        "duration_days": current_duration,
        "work_hours": current_work,
        "cost": None,
    }

    baseline_map = _latest_baseline_task_map(session, project_id)
    baseline = None
    if baseline_map:
        b_starts = [date.fromisoformat(r["planned_start_date"]) for r in baseline_map.values() if r.get("planned_start_date")]
        b_ends = [date.fromisoformat(r["planned_end_date"]) for r in baseline_map.values() if r.get("planned_end_date")]
        b_start = min(b_starts) if b_starts else None
        b_finish = max(b_ends) if b_ends else None
        baseline = {
            "start_date": b_start,
            "finish_date": b_finish,
            "duration_days": Decimal(_duration_days(cal, b_start, b_finish)) if b_start and b_finish else Decimal("0"),
            "work_hours": sum((Decimal(r["estimated_hours"]) for r in baseline_map.values() if r.get("estimated_hours")), Decimal("0")),
            "cost": None,
        }

    actual_starts = [t.actual_start_date for t in tasks if t.actual_start_date]
    all_finished = bool(tasks) and all(t.actual_end_date for t in tasks)
    actual_ends = [t.actual_end_date for t in tasks if t.actual_end_date]
    actual_start = min(actual_starts) if actual_starts else None
    actual_finish = max(actual_ends) if (all_finished and actual_ends) else None
    reference_end = actual_finish or date.today()
    actual_duration = Decimal(_duration_days(cal, actual_start, reference_end)) if actual_start else Decimal("0")
    actual_work = sum((Decimal(t.actual_hours or 0) for t in tasks), Decimal("0"))
    actual_cost = project_financials(session, project_id)["real_cost"]
    actual = {
        "start_date": actual_start,
        "finish_date": actual_finish,
        "duration_days": actual_duration,
        "work_hours": actual_work,
        "cost": actual_cost,
    }

    variance_finish_days = None
    if baseline and baseline["finish_date"] and current["finish_date"]:
        sign = 1 if current["finish_date"] >= baseline["finish_date"] else -1
        variance_finish_days = Decimal(sign * _duration_days(cal, min(current["finish_date"], baseline["finish_date"]), max(current["finish_date"], baseline["finish_date"])))

    percent_complete_duration = _q((actual_duration / current_duration) * 100) if current_duration > 0 else Decimal("0")
    percent_complete_work = _q((actual_work / current_work) * 100) if current_work > 0 else Decimal("0")

    return {
        "current": current,
        "baseline": baseline,
        "actual": actual,
        "variance_finish_days": variance_finish_days,
        "percent_complete_duration": percent_complete_duration,
        "percent_complete_work": percent_complete_work,
    }


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
