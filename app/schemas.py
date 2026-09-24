from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    AuditAction,
    ChangeStatus,
    DependencyType,
    IntakeStatus,
    ProjectStatus,
    RiskLevel,
    RiskStatus,
    TaskApprovalStatus,
    TaskStatus,
    TaskType,
    TimesheetStatus,
    UserRole,
    UserStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth / Users
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: UserRole


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    client_id: str | None = None


class UserRead(ORMModel):
    id: str
    client_id: str | None
    name: str
    email: str
    role: UserRole
    status: UserStatus
    created_at: datetime


class UserUpdate(BaseModel):
    """Edição de usuário (só ADMIN — ver require_roles no router). Trocar
    `status` para BLOCKED impede login imediatamente (checado em
    `POST /auth/login`); a senha não é editável por aqui — ver
    `POST /users/{id}/reset-password`, que gera um hash novo sem expor a
    senha atual."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: UserRole | None = None
    client_id: str | None = None
    status: UserStatus | None = None


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------


class ClientCreate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    legal_name: str = Field(min_length=1, max_length=255)
    trade_name: str | None = None
    tax_id: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = Field(default=None, max_length=2)
    zip_code: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: EmailStr | None = None
    primary_contact_phone: str | None = None


class ClientRead(ORMModel):
    id: str
    code: str
    legal_name: str
    trade_name: str | None
    tax_id: str | None
    city: str | None
    state: str | None
    primary_contact_name: str | None
    primary_contact_email: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Project intakes
# ---------------------------------------------------------------------------


class ProjectIntakeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    estimated_budget: Decimal | None = Field(default=None, ge=0)
    estimated_hours: Decimal | None = Field(default=None, ge=0)


class ProjectIntakeStatusUpdate(BaseModel):
    status: IntakeStatus


class ProjectIntakeRead(ORMModel):
    id: str
    client_id: str
    title: str
    description: str | None
    estimated_budget: Decimal | None
    estimated_hours: Decimal | None
    status: IntakeStatus
    created_at: datetime


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    client_id: str
    manager_id: str
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=255)
    # sold_value NÃO é mais um campo de entrada: é calculado no backend a
    # partir das horas × taxa de gestão e de consultoria (ver
    # app/routers/projects.py), para o valor vendido nunca ficar
    # dessincronizado da composição real do pacote contratado.
    management_hours: Decimal = Field(default=Decimal("0"), ge=0)
    management_rate: Decimal = Field(default=Decimal("0"), ge=0)
    consulting_hours: Decimal = Field(default=Decimal("0"), ge=0)
    consulting_rate: Decimal = Field(default=Decimal("0"), ge=0)
    start_date: date | None = None
    end_date: date | None = None
    calendar_id: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    manager_id: str | None = None
    status: ProjectStatus | None = None
    management_hours: Decimal | None = Field(default=None, ge=0)
    management_rate: Decimal | None = Field(default=None, ge=0)
    consulting_hours: Decimal | None = Field(default=None, ge=0)
    consulting_rate: Decimal | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    calendar_id: str | None = None
    # "Data de status" do projeto — ver Project.status_date em app/models.py
    # e services.project_evm/task_dot_color. Enviar null explicitamente
    # volta a usar a data de hoje como data-base.
    status_date: date | None = None


class ProjectSummary(ORMModel):
    id: str
    client_id: str
    manager_id: str
    code: str
    name: str
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    calendar_id: str | None
    status_date: date | None


class ProjectDetail(ProjectSummary):
    sold_value: Decimal | None = None
    management_hours: Decimal | None = None
    management_rate: Decimal | None = None
    consulting_hours: Decimal | None = None
    consulting_rate: Decimal | None = None
    financials: dict[str, Decimal] | None = None


# ---------------------------------------------------------------------------
# Tasks / dependencies / assignments
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    wbs_code: str = Field(min_length=1, max_length=50)
    task_type: TaskType = TaskType.CONSULTING
    parent_task_id: str | None = None
    # Effort-driven (estilo MS Project) — ver services.apply_effort_driven:
    # "Duração" é o campo primário; "Trabalho" (estimated_hours) é derivado
    # dela (duração × capacidade diária dos recursos alocados, ou 8h/dia
    # sem nenhum recurso ainda). Informar estimated_hours explicitamente
    # (sem informar duration_days) faz o cálculo inverso — deriva a duração
    # a partir do trabalho informado.
    duration_days: Decimal | None = Field(default=None, gt=0)
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    is_milestone: bool = False
    notes: str | None = None


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    task_type: TaskType | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    duration_days: Decimal | None = Field(default=None, gt=0)
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    progress_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    status: TaskStatus | None = None
    is_critical_path: bool | None = None
    is_milestone: bool | None = None
    notes: str | None = None


class TaskClientApprovalUpdate(BaseModel):
    status: TaskApprovalStatus
    comment: str | None = None


class TaskRead(ORMModel):
    id: str
    project_id: str
    parent_task_id: str | None
    name: str
    wbs_code: str
    task_type: TaskType
    duration_days: Decimal
    estimated_hours: Decimal
    actual_hours: Decimal
    sort_order: int
    planned_start_date: date | None
    planned_end_date: date | None
    actual_start_date: date | None
    actual_end_date: date | None
    is_critical_path: bool
    is_milestone: bool
    progress_percentage: Decimal
    status: TaskStatus
    client_approval_status: TaskApprovalStatus
    notes: str | None = None


class TaskMoveRequest(BaseModel):
    """Move uma tarefa para outro pai e/ou outra posição entre as irmãs —
    ver services.move_task. `new_parent_id=None` explícito move para a raiz
    do projeto (mesmo nível das fases de topo). `before_task_id=None`
    (padrão) coloca a tarefa no final da lista de irmãs; para "colocar
    antes de uma tarefa já existente", informe o id dela (precisa já ser
    irmã no `new_parent_id` de destino)."""

    new_parent_id: str | None = None
    before_task_id: str | None = None


class WbsRecalculateResponse(BaseModel):
    tasks: list[TaskRead]


class TaskScheduleRow(TaskRead):
    """Linha enriquecida para a grade de cronograma/Gantt — os campos que
    dependem da `status_date` do projeto ou do último baseline, calculados
    sob demanda (nunca armazenados) por `services.task_schedule_rows`."""

    status_dot: str
    baseline_start_date: date | None = None
    baseline_end_date: date | None = None
    baseline_estimated_hours: Decimal | None = None
    planned_percent_complete: Decimal
    # SPI/CPI calculados por TAREFA (mesma base de horas de EvmMetrics,
    # nunca monetária) — None quando o denominador é zero, mesma regra do
    # cálculo em nível de projeto. Ver services.task_schedule_rows.
    spi: Decimal | None = None
    cpi: Decimal | None = None


class TaskDependencyCreate(BaseModel):
    predecessor_task_id: str
    successor_task_id: str
    dependency_type: DependencyType = DependencyType.FS
    lag_days: int = 0


class TaskDependencyRead(ORMModel):
    id: str
    predecessor_task_id: str
    successor_task_id: str
    dependency_type: DependencyType
    lag_days: int


class RescheduleRequest(BaseModel):
    # Opcional agora que o projeto pode ter seu próprio calendário
    # (Project.calendar_id): sem informar, usa o calendário do projeto (ou
    # o padrão segunda-sexta, se o projeto também não tiver um definido).
    calendar_id: str | None = None


class TaskAssignmentCreate(BaseModel):
    resource_id: str
    allocated_hours: Decimal = Field(gt=0)


class TaskAssignmentRead(ORMModel):
    id: str
    task_id: str
    resource_id: str
    allocated_hours: Decimal


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class ResourceCreate(BaseModel):
    user_id: str
    role_title: str = Field(min_length=1, max_length=120)
    internal_cost_per_hour: Decimal = Field(gt=0)
    billing_rate_per_hour: Decimal = Field(gt=0)
    daily_capacity_hours: Decimal = Field(default=Decimal("8"), gt=0, le=24)
    calendar_id: str | None = None


class ResourceRead(ORMModel):
    id: str
    user_id: str
    role_title: str
    internal_cost_per_hour: Decimal
    billing_rate_per_hour: Decimal
    daily_capacity_hours: Decimal
    calendar_id: str | None


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


class TimesheetCreate(BaseModel):
    # Apontamento "avulso" (padrão Clockify/Toggl): omita task_id para um
    # lançamento sem tarefa pré-definida na EAP. project_id é opcional e só
    # faz sentido quando task_id é omitido — aloca a hora avulsa a um
    # projeto sem exigir WBS; os dois nulos = hora administrativa interna.
    task_id: str | None = None
    project_id: str | None = None
    date: date
    hours_spent: Decimal = Field(gt=0, le=24)
    description: str | None = None


class TimesheetStatusUpdate(BaseModel):
    status: TimesheetStatus


class TimesheetRead(ORMModel):
    id: str
    task_id: str | None
    project_id: str | None
    resource_id: str
    date: date
    hours_spent: Decimal
    description: str | None
    status: TimesheetStatus


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------


class ProjectExpenseCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0)
    expense_date: date


class ProjectExpenseRead(ORMModel):
    id: str
    project_id: str
    description: str
    category: str
    amount: Decimal
    expense_date: date


# ---------------------------------------------------------------------------
# Calendars / holidays
# ---------------------------------------------------------------------------


class CalendarCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    working_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class CalendarRead(ORMModel):
    id: str
    name: str
    working_days: list[int]


class HolidayCreate(BaseModel):
    date: date
    description: str = Field(min_length=1, max_length=255)


class HolidayRead(ORMModel):
    id: str
    calendar_id: str
    date: date
    description: str


# ---------------------------------------------------------------------------
# Risks
# ---------------------------------------------------------------------------


class RiskCreate(BaseModel):
    description: str = Field(min_length=1)
    probability: RiskLevel
    impact: RiskLevel
    mitigation_plan: str | None = None


class RiskUpdate(BaseModel):
    description: str | None = None
    probability: RiskLevel | None = None
    impact: RiskLevel | None = None
    mitigation_plan: str | None = None
    status: RiskStatus | None = None


class RiskRead(ORMModel):
    id: str
    project_id: str
    description: str
    probability: RiskLevel
    impact: RiskLevel
    mitigation_plan: str | None
    status: RiskStatus


# ---------------------------------------------------------------------------
# Change requests
# ---------------------------------------------------------------------------


class ChangeRequestCreate(BaseModel):
    description: str = Field(min_length=1)
    cost_impact: Decimal = Decimal("0")
    schedule_impact_days: int = 0


class ChangeRequestStatusUpdate(BaseModel):
    status: ChangeStatus


class ChangeRequestRead(ORMModel):
    id: str
    project_id: str
    requested_by: str
    description: str
    cost_impact: Decimal
    schedule_impact_days: int
    status: ChangeStatus


# ---------------------------------------------------------------------------
# Baselines
# ---------------------------------------------------------------------------


class BaselineCreate(BaseModel):
    version_name: str = Field(min_length=1, max_length=100)


class BaselineRead(ORMModel):
    id: str
    project_id: str
    version_name: str
    snapshot_data: dict
    created_at: datetime


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------


class AuditLogRead(ORMModel):
    id: str
    entity_type: str
    entity_id: str
    action: AuditAction
    user_id: str | None
    details: dict | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Relatórios / dashboard (Fase 2)
# ---------------------------------------------------------------------------


class ProjectPortfolioRow(BaseModel):
    """Uma linha por projeto — usada tanto em GET /reports/portfolio quanto
    dentro de GET /dashboard. `margin` e vem None para perfis externos (o
    mesmo tratamento de ocultação de dado financeiro usado em
    ProjectDetail)."""

    id: str
    code: str
    name: str
    status: ProjectStatus
    percent_complete: Decimal
    tasks_total: int
    tasks_remaining: int
    margin: Decimal | None = None
    next_milestone_name: str | None = None
    next_milestone_date: date | None = None


class DashboardResponse(BaseModel):
    projects_total: int
    projects_by_status: dict[str, int]
    tasks_total: int
    tasks_by_status: dict[str, int]
    tasks_by_type: dict[str, int]
    tasks_overdue: int
    avg_progress_percentage: Decimal
    portfolio: list[ProjectPortfolioRow]


class BurndownPoint(BaseModel):
    date: date
    planned_remaining_hours: Decimal
    actual_remaining_hours: Decimal


class ProjectReportResponse(BaseModel):
    project_id: str
    percent_complete: Decimal
    tasks_total: int
    tasks_remaining: int
    tasks_by_status: dict[str, int]
    financials: dict[str, Decimal] | None = None
    financials_by_task_type: dict[str, dict[str, Decimal]] | None = None
    burndown: list[BurndownPoint]


class ResourceUtilizationRow(BaseModel):
    resource_id: str
    user_id: str
    role_title: str
    period_start: date
    period_end: date
    capacity_hours: Decimal
    allocated_hours: Decimal
    actual_hours: Decimal
    utilization_percentage: Decimal | None


class RiskMatrixResponse(BaseModel):
    project_id: str
    grid: dict[str, dict[str, int]]
    high_priority: list[RiskRead]


class VelocityPoint(BaseModel):
    period_start: date
    hours_delivered: Decimal


class RoiRow(BaseModel):
    project_id: str
    code: str
    sold_value: Decimal
    real_cost: Decimal
    roi_percentage: Decimal | None


class GanttResponse(BaseModel):
    tasks: list[TaskRead]
    dependencies: list[TaskDependencyRead]


class ProjectScheduleResponse(BaseModel):
    """Cronograma enriquecido para a grade de tarefas (bolinha de status,
    linha base, % previsto) — usado pela tela de tarefas/Gantt do
    frontend. Separado de GanttResponse (que fica só com os campos "crus"
    de Task/TaskDependency, sem depender de status_date/baseline)."""

    status_date: date
    tasks: list[TaskScheduleRow]
    dependencies: list[TaskDependencyRead]


class EvmMetrics(BaseModel):
    """Earned Value em base de HORAS (estimated_hours), não monetária — ver
    decisão registrada em services.project_evm. planned_value/earned_value/
    actual_hours são somas de horas de tarefa; os índices SPI/CPI ficam
    None quando o denominador é zero (projeto sem horas planejadas até a
    status_date, ou sem nenhuma hora ainda apontada)."""

    status_date: date
    planned_value_hours: Decimal
    earned_value_hours: Decimal
    actual_hours: Decimal
    spi: Decimal | None
    cpi: Decimal | None
    planned_percent_complete: Decimal
    percent_complete: Decimal


class ProjectStatisticsRange(BaseModel):
    start_date: date | None
    finish_date: date | None
    duration_days: Decimal
    work_hours: Decimal
    cost: Decimal | None


class ProjectStatisticsResponse(BaseModel):
    """Espelha a caixa "Project Statistics" do MS Project (Current/Baseline/
    Actual/Variance × Start/Finish/Duration/Work/Cost + % complete) — ver
    services.project_statistics."""

    current: ProjectStatisticsRange
    baseline: ProjectStatisticsRange | None
    actual: ProjectStatisticsRange
    variance_finish_days: Decimal | None
    percent_complete_duration: Decimal
    percent_complete_work: Decimal
