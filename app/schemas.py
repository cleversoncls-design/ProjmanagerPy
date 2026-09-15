from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import (
    ChangeStatus,
    DependencyType,
    IntakeStatus,
    ProjectStatus,
    RiskLevel,
    RiskStatus,
    TaskStatus,
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
    sold_value: Decimal = Field(default=Decimal("0"), ge=0)
    start_date: date | None = None
    end_date: date | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    manager_id: str | None = None
    status: ProjectStatus | None = None
    sold_value: Decimal | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None


class ProjectSummary(ORMModel):
    id: str
    client_id: str
    manager_id: str
    code: str
    name: str
    status: ProjectStatus
    start_date: date | None
    end_date: date | None


class ProjectDetail(ProjectSummary):
    sold_value: Decimal | None = None
    financials: dict[str, Decimal] | None = None


# ---------------------------------------------------------------------------
# Tasks / dependencies / assignments
# ---------------------------------------------------------------------------


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    wbs_code: str = Field(min_length=1, max_length=50)
    parent_task_id: str | None = None
    estimated_hours: Decimal = Field(default=Decimal("0"), ge=0)
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    is_milestone: bool = False


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    actual_start_date: date | None = None
    actual_end_date: date | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    progress_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    status: TaskStatus | None = None
    is_critical_path: bool | None = None
    is_milestone: bool | None = None


class TaskRead(ORMModel):
    id: str
    project_id: str
    parent_task_id: str | None
    name: str
    wbs_code: str
    estimated_hours: Decimal
    actual_hours: Decimal
    planned_start_date: date | None
    planned_end_date: date | None
    actual_start_date: date | None
    actual_end_date: date | None
    is_critical_path: bool
    is_milestone: bool
    progress_percentage: Decimal
    status: TaskStatus


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
    calendar_id: str


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


class ResourceRead(ORMModel):
    id: str
    user_id: str
    role_title: str
    internal_cost_per_hour: Decimal
    billing_rate_per_hour: Decimal
    daily_capacity_hours: Decimal


# ---------------------------------------------------------------------------
# Timesheets
# ---------------------------------------------------------------------------


class TimesheetCreate(BaseModel):
    task_id: str
    date: date
    hours_spent: Decimal = Field(gt=0, le=24)
    description: str | None = None


class TimesheetStatusUpdate(BaseModel):
    status: TimesheetStatus


class TimesheetRead(ORMModel):
    id: str
    task_id: str
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
