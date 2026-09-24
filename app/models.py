from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class StrEnum(str, enum.Enum):
    pass


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    INTERNAL_PM = "INTERNAL_PM"
    CONSULTANT = "CONSULTANT"
    CLIENT_PM = "CLIENT_PM"
    CLIENT_USER = "CLIENT_USER"


class UserStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    BLOCKED = "BLOCKED"


class IntakeStatus(StrEnum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ProjectStatus(StrEnum):
    PLANNING = "PLANNING"
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class DependencyType(StrEnum):
    FS = "FS"
    FF = "FF"
    SS = "SS"
    SF = "SF"


class TaskStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    DELAYED = "DELAYED"


class TaskType(StrEnum):
    MANAGEMENT = "MANAGEMENT"
    CONSULTING = "CONSULTING"


class TaskApprovalStatus(StrEnum):
    """Aprovação da tarefa pelo lado do cliente (gerente de projeto do
    cliente ou usuário-chave), independente do TaskStatus de execução —
    uma tarefa pode estar COMPLETED e ainda não ter sido validada pelo
    cliente."""

    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class TimesheetStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RiskLevel(StrEnum):
    LOW = "LOW"
    MED = "MED"
    HIGH = "HIGH"


class RiskStatus(StrEnum):
    OPEN = "OPEN"
    MITIGATED = "MITIGATED"
    CLOSED = "CLOSED"


class ChangeStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class Client(Base):
    __tablename__ = "clients"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(30), unique=True)
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(15))
    primary_contact_name: Mapped[str | None] = mapped_column(String(255))
    primary_contact_email: Mapped[str | None] = mapped_column(String(255))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    users: Mapped[list[User]] = relationship(back_populates="client")
    projects: Mapped[list[Project]] = relationship(back_populates="client")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str | None] = mapped_column(ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(nullable=False)
    status: Mapped[UserStatus] = mapped_column(nullable=False, default=UserStatus.ACTIVE)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    client: Mapped[Client | None] = relationship(back_populates="users")
    resource: Mapped[Resource | None] = relationship(back_populates="user", uselist=False)


class ProjectIntake(Base):
    __tablename__ = "project_intakes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[IntakeStatus] = mapped_column(nullable=False, default=IntakeStatus.SUBMITTED)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False, index=True)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(nullable=False, default=ProjectStatus.PLANNING)
    sold_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    # Quebra do valor vendido entre horas de gestão e de consultoria — cada
    # bolsa tem sua própria quantidade de horas contratadas e seu próprio
    # valor/hora. `sold_value` continua existindo como coluna (usado direto
    # por project_financials), mas passa a ser CALCULADO a partir destes 4
    # campos no momento de criar/atualizar o projeto (ver app/routers/projects.py),
    # em vez de ser digitado diretamente.
    management_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    management_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    consulting_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    consulting_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    # Calendário aplicado ao projeto (dias úteis/feriados usados para
    # calcular datas finais e o motor de reagendamento). Opcional: sem ele,
    # o recálculo cai no calendário padrão (segunda a sexta, sem feriados) —
    # ver `services.calendar_for_project`. Pode ser comparado/validado
    # contra o calendário pessoal do consultor (Resource.calendar_id) na
    # tela de recursos.
    calendar_id: Mapped[str | None] = mapped_column(ForeignKey("calendars.id", ondelete="SET NULL"))
    # "Data de status"/data-base: a partir dela, o sistema calcula o %
    # previsto e o status (no prazo/atrasada) de cada tarefa — ver
    # `services.project_evm` e `services.task_dot_color`. None = usa a data
    # de hoje como data-base (comportamento antes de existir este campo).
    status_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    client: Mapped[Client] = relationship(back_populates="projects")
    calendar: Mapped[Calendar | None] = relationship()
    tasks: Mapped[list[Task]] = relationship(back_populates="project", cascade="all, delete-orphan")
    expenses: Mapped[list[ProjectExpense]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Baseline(Base):
    __tablename__ = "baselines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    version_name: Mapped[str] = mapped_column(String(100), nullable=False)
    snapshot_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    wbs_code: Mapped[str] = mapped_column(String(50), nullable=False)
    task_type: Mapped[TaskType] = mapped_column(nullable=False, default=TaskType.CONSULTING)
    # "Duração" (dias) — campo primário do agendamento effort-driven (estilo
    # MS Project): estimated_hours ("Trabalho") é derivado dela × a
    # capacidade diária dos recursos alocados (ou 8h/dia sem nenhum recurso
    # alocado ainda). Editar estimated_hours diretamente faz o cálculo
    # inverso. Ver `services.apply_effort_driven`.
    duration_days: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=1)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    actual_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    # Posição manual entre as tarefas-irmãs (mesmo parent_task_id) — usada
    # por "mover tarefa" (reordenar/reparentar) e por `recalculate_wbs` para
    # decidir a ordem final do WBS, já que a ordenação alfabética de
    # wbs_code não reflete mais a ordem depois de um recálculo. Não é único
    # nem denso (gaps são normais); só a ordem relativa importa.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    planned_start_date: Mapped[date | None] = mapped_column(Date)
    planned_end_date: Mapped[date | None] = mapped_column(Date)
    actual_start_date: Mapped[date | None] = mapped_column(Date)
    actual_end_date: Mapped[date | None] = mapped_column(Date)
    dependency_type: Mapped[DependencyType] = mapped_column(nullable=False, default=DependencyType.FS)
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_critical_path: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_milestone: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    progress_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    status: Mapped[TaskStatus] = mapped_column(nullable=False, default=TaskStatus.NOT_STARTED)
    client_approval_status: Mapped[TaskApprovalStatus] = mapped_column(nullable=False, default=TaskApprovalStatus.NOT_REQUIRED)
    # Campo de observações livre (item 16 do pedido de revisão da tela de
    # tarefas) — texto sem estrutura, nunca usado em cálculo nenhum.
    notes: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("project_id", "wbs_code", name="uq_task_project_wbs"),)
    project: Mapped[Project] = relationship(back_populates="tasks")
    parent: Mapped[Task | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Task]] = relationship(back_populates="parent")
    assignments: Mapped[list[TaskAssignment]] = relationship(back_populates="task", cascade="all, delete-orphan")
    timesheets: Mapped[list[Timesheet]] = relationship(back_populates="task", cascade="all, delete-orphan")


class Resource(Base):
    __tablename__ = "resources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    role_title: Mapped[str] = mapped_column(String(120), nullable=False)
    internal_cost_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    billing_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    daily_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=8)
    # Calendário pessoal (dias úteis/feriados) usado para nivelar a agenda
    # deste recurso — opcional; sem ele, o recálculo de cronograma usa o
    # calendário do projeto/calendar_id informado explicitamente na chamada.
    calendar_id: Mapped[str | None] = mapped_column(ForeignKey("calendars.id", ondelete="SET NULL"))
    user: Mapped[User] = relationship(back_populates="resource")
    calendar: Mapped[Calendar | None] = relationship()


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    allocated_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    __table_args__ = (UniqueConstraint("task_id", "resource_id", name="uq_task_resource"),)
    task: Mapped[Task] = relationship(back_populates="assignments")


class Timesheet(Base):
    __tablename__ = "timesheets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Apontamento "avulso" (sem tarefa pré-definida na EAP, padrão
    # Clockify/Toggl): task_id fica nulo e project_id opcionalmente aloca o
    # custo a um projeto sem exigir WBS. Os dois nulos = hora administrativa
    # interna, sem alocação a nenhum projeto.
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    hours_spent: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TimesheetStatus] = mapped_column(nullable=False, default=TimesheetStatus.PENDING)
    task: Mapped[Task | None] = relationship(back_populates="timesheets")
    project: Mapped[Project | None] = relationship()


class ProjectExpense(Base):
    __tablename__ = "project_expenses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    project: Mapped[Project] = relationship(back_populates="expenses")


class Calendar(Base):
    __tablename__ = "calendars"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    working_days: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4])
    holidays: Mapped[list[Holiday]] = relationship(back_populates="calendar", cascade="all, delete-orphan")


class Holiday(Base):
    __tablename__ = "holidays"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    calendar_id: Mapped[str] = mapped_column(ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    __table_args__ = (UniqueConstraint("calendar_id", "date", name="uq_calendar_holiday"),)
    calendar: Mapped[Calendar] = relationship(back_populates="holidays")


class Risk(Base):
    __tablename__ = "risks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    probability: Mapped[RiskLevel] = mapped_column(nullable=False)
    impact: Mapped[RiskLevel] = mapped_column(nullable=False)
    mitigation_plan: Mapped[str | None] = mapped_column(Text)
    status: Mapped[RiskStatus] = mapped_column(nullable=False, default=RiskStatus.OPEN)
    project: Mapped[Project] = relationship()


class ChangeRequest(Base):
    __tablename__ = "change_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cost_impact: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    schedule_impact_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    project: Mapped[Project] = relationship()
    status: Mapped[ChangeStatus] = mapped_column(nullable=False, default=ChangeStatus.PENDING)


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    predecessor_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    successor_task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    dependency_type: Mapped[DependencyType] = mapped_column(nullable=False, default=DependencyType.FS)
    lag_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint("predecessor_task_id", "successor_task_id", name="uq_dependency_pair"),)


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"


class AuditLog(Base):
    """Registro mínimo de auditoria: quem criou/alterou qual registro e
    quando. Não é um log de todas as leituras nem um diff campo-a-campo
    completo — apenas o suficiente para responder "quem mexeu nisso e
    quando" nas entidades de negócio mais sensíveis (projetos, tarefas,
    timesheets, mudanças)."""

    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[AuditAction] = mapped_column(nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    details: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
