from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import date, datetime, timedelta, timezone
from datetime import date as Date
from decimal import Decimal, ROUND_CEILING
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from .models import Baseline, Base, Calendar, Client, Holiday, Project, ProjectCurrency, ProjectStatus, Resource, Task, TaskAssignment, TaskDependency, TaskPriority, TaskStatus, TaskType, Timesheet, User, UserRole, UserStatus
from .services import BusinessCalendar, _duration_days, calendar_from_db, normalize_task_hierarchy, project_financials, task_evm, reschedule_cascade

RAW_DATABASE_URL = os.getenv("DATABASE_URL")
if RAW_DATABASE_URL:
    DATABASE_URL = RAW_DATABASE_URL
elif os.getenv("POSTGRES_PASSWORD"):
    DATABASE_URL = URL.create(
        "postgresql+psycopg",
        username=os.getenv("POSTGRES_USER", "projmanager"),
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        database=os.getenv("POSTGRES_DB", "projmanager"),
    )
else:
    DATABASE_URL = "sqlite:///./controle_projetos.db"

engine_kwargs: dict[str, Any] = {"pool_pre_ping": True}
if str(DATABASE_URL).startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)

app = FastAPI(title="Controle de Projetos Corporativo", version="0.2.0")
origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-this-secret-before-production").encode()
JWT_TTL_MINUTES = int(os.getenv("JWT_TTL_MINUTES", "480"))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_access_token(user: User) -> str:
    now = int(time.time())
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({"sub": user.id, "role": user.role.value, "client_id": user.client_id, "iat": now, "exp": now + JWT_TTL_MINUTES * 60}, separators=(",", ":")).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _b64(hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        expected = _b64(hmac.new(JWT_SECRET, f"{header}.{payload}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        claims = json.loads(_unb64(payload))
        if int(claims.get("exp", 0)) < int(time.time()):
            raise ValueError("expired")
        return claims
    except (ValueError, KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Token JWT inválido ou expirado") from exc


def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    iterations = 310000
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        derived = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(derived.hex(), expected)
    except (ValueError, TypeError):
        return False


def require_internal(user: User) -> None:
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        raise HTTPException(status_code=403, detail="Perfil externo não possui esta permissão")


def require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Apenas administradores podem gerenciar usuários")


def get_current_user(authorization: Annotated[str | None, Header()] = None, x_user_id: Annotated[str | None, Header()] = None, db: Session = Depends(get_db)) -> User:
    user_id: str | None = None
    if authorization and authorization.lower().startswith("bearer "):
        claims = decode_access_token(authorization.split(" ", 1)[1])
        user_id = str(claims.get("sub"))
    elif x_user_id:
        # Compatibilidade transitória com o contrato anterior; remova após a migração do cliente.
        user_id = x_user_id
    if not user_id:
        raise HTTPException(status_code=401, detail="Credencial ausente")
    user = db.get(User, user_id)
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="Usuário inválido ou inativo")
    return user


def require_project_access(project: Project, user: User, write: bool = False) -> None:
    external = user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}
    if external and project.client_id != user.client_id:
        raise HTTPException(status_code=403, detail="Projeto fora do escopo do cliente")
    if write and external and user.role not in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        raise HTTPException(status_code=403, detail="Perfil sem permissão de escrita")


def client_scope(query: Any, user: User, column: Any) -> Any:
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        if not user.client_id:
            raise HTTPException(status_code=403, detail="Usuário externo sem cliente associado")
        return query.where(column == user.client_id)
    return query


class LoginRequest(BaseModel):
    email: str
    password: str


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = UserRole.CONSULTANT
    status: UserStatus = UserStatus.ACTIVE
    client_id: str | None = None


class ClientCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    legal_name: str = Field(min_length=2, max_length=255)
    trade_name: str | None = None
    tax_id: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: str | None = None
    primary_contact_phone: str | None = None


class ClientPatch(BaseModel):
    legal_name: str | None = None
    trade_name: str | None = None
    tax_id: str | None = None
    primary_contact_name: str | None = None
    primary_contact_email: str | None = None
    primary_contact_phone: str | None = None


class ProjectCreate(BaseModel):
    client_id: str
    manager_id: str
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=255)
    status: ProjectStatus = ProjectStatus.PLANNING
    currency: ProjectCurrency = ProjectCurrency.USD
    sold_value: Decimal = Field(default=0, ge=0)
    start_date: date | None = None
    end_date: date | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    manager_id: str | None = None
    status: ProjectStatus | None = None
    currency: ProjectCurrency | None = None
    sold_value: Decimal | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None


class TaskCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    wbs_code: str | None = Field(default=None, min_length=1, max_length=50)
    estimated_hours: Decimal = Field(default=0, ge=0)
    duration_days: int = Field(default=1, ge=1, le=3650)
    priority: TaskPriority = TaskPriority.MED
    task_type: TaskType = TaskType.IMPLEMENTATION
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    status: TaskStatus = TaskStatus.NOT_STARTED
    progress_percentage: Decimal = Field(default=0, ge=0, le=100)
    parent_task_id: str | None = None
    baseline_id: str | None = None
    observation: str | None = None
    predecessor_task_id: str | None = None
    dependency_type: str = Field(default="FS", pattern="^(FS|FF|SS|SF)$")
    lag_days: int = Field(default=0, ge=-366, le=366)


class TaskPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = None
    wbs_code: str | None = Field(default=None, min_length=1, max_length=50)
    status: TaskStatus | None = None
    estimated_hours: Decimal | None = Field(default=None, ge=0)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    priority: TaskPriority | None = None
    task_type: TaskType | None = None
    planned_start_date: date | None = None
    planned_end_date: date | None = None
    progress_percentage: Decimal | None = Field(default=None, ge=0, le=100)
    parent_task_id: str | None = None
    baseline_id: str | None = None
    observation: str | None = None
    predecessor_task_id: str | None = None
    dependency_type: str | None = Field(default=None, pattern="^(FS|FF|SS|SF)$")
    lag_days: int | None = Field(default=None, ge=-366, le=366)


class TimesheetCreate(BaseModel):
    task_id: str
    date: Date
    hours_spent: Decimal = Field(gt=0, le=24)
    description: str | None = None


class TimesheetPatch(BaseModel):
    date: Date | None = None
    hours_spent: Decimal | None = Field(default=None, gt=0, le=24)
    description: str | None = None


class CalendarCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    working_days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])


class CalendarPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    working_days: list[int] | None = None


class HolidayCreate(BaseModel):
    date: Date
    description: str = Field(min_length=2, max_length=255)


class ResourceCreate(BaseModel):
    user_id: str
    calendar_id: str | None = None
    role_title: str = Field(min_length=2, max_length=120)
    internal_cost_per_hour: Decimal = Field(ge=0)
    billing_rate_per_hour: Decimal = Field(ge=0)
    daily_capacity_hours: Decimal = Field(gt=0, le=24, default=8)


class ResourcePatch(BaseModel):
    calendar_id: str | None = None
    role_title: str | None = Field(default=None, min_length=2, max_length=120)
    internal_cost_per_hour: Decimal | None = Field(default=None, ge=0)
    billing_rate_per_hour: Decimal | None = Field(default=None, ge=0)
    daily_capacity_hours: Decimal | None = Field(default=None, gt=0, le=24)


class TaskAssignmentCreate(BaseModel):
    resource_id: str
    allocated_hours: Decimal = Field(gt=0)
class TaskAssignmentPatch(BaseModel):
    allocated_hours: Decimal = Field(gt=0)
class TaskDependencyCreate(BaseModel):

    successor_task_id: str
    dependency_type: str = Field(default="FS", pattern="^(FS|FF|SS|SF)$")
    lag_days: int = Field(default=0, ge=-366, le=366)


def validate_working_days(days: list[int]) -> list[int]:
    normalized = sorted(set(days))
    if any(day < 0 or day > 6 for day in normalized):
        raise HTTPException(status_code=422, detail="Dias úteis devem usar valores de 0 (segunda) a 6 (domingo)")
    if not normalized:
        raise HTTPException(status_code=422, detail="O calendário precisa ter ao menos um dia útil")
    return normalized


def validate_calendar(db: Session, calendar_id: str | None) -> Calendar | None:
    if calendar_id is None:
        return None
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=422, detail="Calendário não encontrado")
    return calendar


def serialize_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.value, "status": user.status.value, "client_id": user.client_id}


def serialize_client(client: Client) -> dict[str, Any]:
    return {"id": client.id, "code": client.code, "legal_name": client.legal_name, "trade_name": client.trade_name, "tax_id": client.tax_id, "primary_contact_name": client.primary_contact_name, "primary_contact_email": client.primary_contact_email, "primary_contact_phone": client.primary_contact_phone}


def serialize_project(project: Project, user: User, db: Session) -> dict[str, Any]:
    manager = db.get(User, project.manager_id)
    payload = {"id": project.id, "code": project.code, "name": project.name, "client_id": project.client_id, "manager_id": project.manager_id, "manager_name": manager.name if manager else None, "status": project.status.value, "currency": project.currency.value, "start_date": project.start_date, "end_date": project.end_date}
    if user.role not in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        payload["sold_value"] = project.sold_value
        payload["financials"] = project_financials(db, project.id)
    return payload


def serialize_task(task: Task, db: Session) -> dict[str, Any]:
    calendar = calendar_for_task(db, task)
    evm = task_evm(db, task, calendar)
    assignments = db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task.id).order_by(TaskAssignment.id)).all()
    assignment_payload = []
    for assignment in assignments:
        resource = db.get(Resource, assignment.resource_id)
        assigned_user = db.get(User, resource.user_id) if resource else None
        assignment_payload.append({"id": assignment.id, "resource_id": assignment.resource_id, "resource_name": assigned_user.name if assigned_user else None, "allocated_hours": assignment.allocated_hours, "calendar_id": resource.calendar_id if resource else None})
    predecessors = db.scalars(select(TaskDependency).where(TaskDependency.successor_task_id == task.id).order_by(TaskDependency.id)).all()
    timesheet_count = db.scalar(select(func.count(Timesheet.id)).where(Timesheet.task_id == task.id)) or 0
    baseline = db.get(Baseline, task.baseline_id) if task.baseline_id else None
    return {
        "id": task.id,
        "project_id": task.project_id,
        "name": task.name,
        "description": task.description,
        "wbs_code": task.wbs_code,
        "parent_task_id": task.parent_task_id,
        "estimated_hours": task.estimated_hours,
        "actual_hours": evm["actual_hours"],
        "timesheet_count": timesheet_count,
        "duration_days": task.duration_days,
        "priority": task.priority.value,
        "task_type": task.task_type.value,
        "planned_start_date": task.planned_start_date,
        "planned_end_date": task.planned_end_date,
        "actual_start_date": evm["actual_start_date"],
        "actual_end_date": evm["actual_end_date"],
        "status": task.status.value,
        "progress_percentage": task.progress_percentage,
        "planned_percentage": evm["planned_percentage"],
        "spi": evm["spi"],
        "cpi": evm["cpi"],
        "earned_value": evm["earned_value"],
        "planned_value": evm["planned_value"],
        "actual_cost": evm["actual_cost"],
        "baseline_id": task.baseline_id,
        "baseline_name": baseline.version_name if baseline else None,
        "observation": task.observation,
        "assignments": assignment_payload,
        "predecessors": [{"id": item.id, "task_id": item.predecessor_task_id, "dependency_type": item.dependency_type.value, "lag_days": item.lag_days} for item in predecessors],
        "calendar_id": next((item["calendar_id"] for item in assignment_payload if item["calendar_id"]), None),
    }


def serialize_calendar(calendar: Calendar, db: Session) -> dict[str, Any]:
    holidays = db.scalars(select(Holiday).where(Holiday.calendar_id == calendar.id).order_by(Holiday.date)).all()
    return {
        "id": calendar.id,
        "name": calendar.name,
        "working_days": sorted(calendar.working_days),
        "working_day_labels": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"],
        "holidays": [{"id": holiday.id, "date": holiday.date, "description": holiday.description} for holiday in holidays],
    }


def calendar_for_task(db: Session, task: Task) -> BusinessCalendar:
    assignments = db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task.id).order_by(TaskAssignment.id)).all()
    for assignment in assignments:
        resource = db.get(Resource, assignment.resource_id)
        if resource and resource.calendar_id:
            try:
                return calendar_from_db(db, resource.calendar_id)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail="O calendário do recurso não foi encontrado") from exc
    return BusinessCalendar()


def task_daily_capacity(db: Session, task: Task) -> Decimal:
    assignments = db.scalars(select(TaskAssignment).where(TaskAssignment.task_id == task.id).order_by(TaskAssignment.id)).all()
    capacities: list[Decimal] = []
    for assignment in assignments:
        resource = db.get(Resource, assignment.resource_id)
        if resource:
            capacities.append(Decimal(resource.daily_capacity_hours or 0))
    total_capacity = sum(capacities, Decimal("0"))
    return total_capacity if total_capacity > 0 else Decimal("8")


def calculated_task_duration(db: Session, task: Task) -> int:
    hours = Decimal(task.estimated_hours or 0)
    capacity = task_daily_capacity(db, task)
    return max(1, int((hours / capacity).to_integral_value(rounding=ROUND_CEILING)))


def schedule_task_dates(db: Session, task: Task) -> None:
    task.duration_days = calculated_task_duration(db, task)
    if not task.planned_start_date:
        return
    calendar = calendar_for_task(db, task)
    task.planned_start_date = calendar.next_working_day(task.planned_start_date)
    task.planned_end_date = calendar.add_working_days(task.planned_start_date, task.duration_days - 1)


def next_wbs_code(db: Session, project_id: str, parent_task_id: str | None) -> str:
    siblings = db.scalars(select(Task).where(Task.project_id == project_id, Task.parent_task_id == parent_task_id)).all()
    if parent_task_id:
        parent = db.get(Task, parent_task_id)
        prefix = parent.wbs_code if parent else "1"
        return f"{prefix}.{len(siblings) + 1}"
    return str(len(siblings) + 1)


def validate_task_parent(db: Session, task: Task, parent_task_id: str | None) -> None:
    if parent_task_id is None:
        return
    parent = db.get(Task, parent_task_id)
    if not parent:
        raise HTTPException(status_code=422, detail="Tarefa pai não encontrada")
    if parent.project_id != task.project_id:
        raise HTTPException(status_code=422, detail="A tarefa pai deve pertencer ao mesmo projeto")
    if parent.id == task.id:
        raise HTTPException(status_code=422, detail="Uma tarefa não pode ser pai dela mesma")
    ancestor = parent
    visited: set[str] = set()
    while ancestor.parent_task_id:
        if ancestor.id in visited or ancestor.parent_task_id == task.id:
            raise HTTPException(status_code=422, detail="A hierarquia criaria um ciclo")
        visited.add(ancestor.id)
        ancestor = db.get(Task, ancestor.parent_task_id)
        if not ancestor:
            break


def serialize_resource(resource: Resource, db: Session) -> dict[str, Any]:
    user = db.get(User, resource.user_id)
    calendar = db.get(Calendar, resource.calendar_id) if resource.calendar_id else None
    return {
        "id": resource.id,
        "user_id": resource.user_id,
        "user_name": user.name if user else None,
        "role_title": resource.role_title,
        "calendar_id": resource.calendar_id,
        "calendar_name": calendar.name if calendar else None,
        "internal_cost_per_hour": resource.internal_cost_per_hour,
        "billing_rate_per_hour": resource.billing_rate_per_hour,
        "daily_capacity_hours": resource.daily_capacity_hours,
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower().strip()))
    if not user or user.status != UserStatus.ACTIVE or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")
    return {"access_token": create_access_token(user), "token_type": "bearer", "expires_in": JWT_TTL_MINUTES * 60, "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role.value, "client_id": user.client_id}}


@app.get("/auth/me")
def auth_me(user: User = Depends(get_current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.value, "client_id": user.client_id}


@app.get("/users")
def list_users(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(user)
    return [serialize_user(row) for row in db.scalars(select(User).order_by(User.name)).all()]


@app.get("/users/managers")
def list_project_managers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    manager_roles = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT}
    query = select(User).where(User.status == UserStatus.ACTIVE, User.role.in_(manager_roles)).order_by(User.name)
    return [serialize_user(row) for row in db.scalars(query).all()]


@app.get("/users/resource-candidates")
def list_resource_candidates(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    eligible_roles = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT, UserRole.CLIENT_PM, UserRole.CLIENT_USER}
    query = select(User).where(User.status == UserStatus.ACTIVE, User.role.in_(eligible_roles)).order_by(User.name)
    return [serialize_user(row) for row in db.scalars(query).all()]


@app.post("/users", status_code=201)
def create_user(data: UserCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_admin(user)
    email = data.email.lower().strip()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Já existe um usuário com este e-mail")
    external_roles = {UserRole.CLIENT_PM, UserRole.CLIENT_USER}
    internal_roles = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT}
    client_id = data.client_id if data.role in external_roles else None
    if data.role in external_roles and not client_id:
        raise HTTPException(status_code=422, detail="Usuários externos precisam estar vinculados a um cliente")
    if client_id and not db.get(Client, client_id):
        raise HTTPException(status_code=422, detail="Cliente não encontrado")
    if data.role not in internal_roles | external_roles:
        raise HTTPException(status_code=422, detail="Perfil de usuário inválido")
    new_user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password), role=data.role, status=data.status, client_id=client_id)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return serialize_user(new_user)


@app.get("/calendars")
def list_calendars(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    return [serialize_calendar(row, db) for row in db.scalars(select(Calendar).order_by(Calendar.name)).all()]


@app.post("/calendars", status_code=201)
def create_calendar(data: CalendarCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    calendar = Calendar(name=data.name.strip(), working_days=validate_working_days(data.working_days))
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    return serialize_calendar(calendar, db)


@app.patch("/calendars/{calendar_id}")
def update_calendar(calendar_id: str, data: CalendarPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
    updates = data.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        updates["name"] = updates["name"].strip()
    if "working_days" in updates and updates["working_days"] is not None:
        updates["working_days"] = validate_working_days(updates["working_days"])
    for field, value in updates.items():
        setattr(calendar, field, value)
    db.commit()
    db.refresh(calendar)
    return serialize_calendar(calendar, db)


@app.delete("/calendars/{calendar_id}", status_code=204)
def delete_calendar(calendar_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
    db.delete(calendar)
    db.commit()


@app.post("/calendars/{calendar_id}/holidays", status_code=201)
def create_holiday(calendar_id: str, data: HolidayCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    if not db.get(Calendar, calendar_id):
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
    if db.scalar(select(Holiday).where(Holiday.calendar_id == calendar_id, Holiday.date == data.date)):
        raise HTTPException(status_code=409, detail="Já existe um feriado nessa data para este calendário")
    holiday = Holiday(calendar_id=calendar_id, date=data.date, description=data.description.strip())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return {"id": holiday.id, "calendar_id": holiday.calendar_id, "date": holiday.date, "description": holiday.description}


@app.delete("/holidays/{holiday_id}", status_code=204)
def delete_holiday(holiday_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    holiday = db.get(Holiday, holiday_id)
    if not holiday:
        raise HTTPException(status_code=404, detail="Feriado não encontrado")
    db.delete(holiday)
    db.commit()


@app.get("/resources")
def list_resources(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    return [serialize_resource(row, db) for row in db.scalars(select(Resource).order_by(Resource.role_title, Resource.id)).all()]


@app.post("/resources", status_code=201)
def create_resource(data: ResourceCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    resource_user = db.get(User, data.user_id)
    if not resource_user or resource_user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=422, detail="O recurso deve estar vinculado a um usuário ativo")
    eligible_roles = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT, UserRole.CLIENT_PM, UserRole.CLIENT_USER}
    if resource_user.role not in eligible_roles:
        raise HTTPException(status_code=422, detail="O perfil do usuário não pode ser alocado como recurso")
    if db.scalar(select(Resource).where(Resource.user_id == data.user_id)):
        raise HTTPException(status_code=409, detail="Este usuário já possui um recurso cadastrado")
    validate_calendar(db, data.calendar_id)
    resource = Resource(id=str(uuid.uuid4()), **data.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return serialize_resource(resource, db)


@app.patch("/resources/{resource_id}")
def update_resource(resource_id: str, data: ResourcePatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    updates = data.model_dump(exclude_unset=True)
    if "calendar_id" in updates:
        validate_calendar(db, updates["calendar_id"])
    if "role_title" in updates and updates["role_title"] is not None:
        updates["role_title"] = updates["role_title"].strip()
    for field, value in updates.items():
        setattr(resource, field, value)
    db.commit()
    db.refresh(resource)
    return serialize_resource(resource, db)


@app.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    db.delete(resource)
    db.commit()


@app.get("/resources/{resource_id}/availability")
def resource_availability(resource_id: str, start_date: Date | None = Query(default=None), end_date: Date | None = Query(default=None), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    start = start_date or date.today()
    end = end_date or (start + timedelta(days=30))
    if end < start:
        raise HTTPException(status_code=422, detail="A data final deve ser igual ou posterior à data inicial")
    if (end - start).days > 366:
        raise HTTPException(status_code=422, detail="O intervalo máximo de disponibilidade é de 366 dias")
    calendar = calendar_from_db(db, resource.calendar_id) if resource.calendar_id else BusinessCalendar()
    working_dates: list[date] = []
    current = start
    while current <= end:
        if calendar.is_working_day(current):
            working_dates.append(current)
        current += timedelta(days=1)
    return {"resource_id": resource.id, "calendar_id": resource.calendar_id, "calendar_name": db.get(Calendar, resource.calendar_id).name if resource.calendar_id else "Padrão seg-sex", "daily_capacity_hours": resource.daily_capacity_hours, "start_date": start, "end_date": end, "working_dates": working_dates, "working_days_count": len(working_dates), "capacity_hours": resource.daily_capacity_hours * len(working_dates)}


@app.get("/clients")
def list_clients(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Client).order_by(Client.trade_name, Client.legal_name)
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        query = query.where(Client.id == user.client_id)
    return [serialize_client(row) for row in db.scalars(query).all()]


@app.post("/clients", status_code=201)
def create_client(data: ClientCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return serialize_client(client)


@app.patch("/clients/{client_id}")
def update_client(client_id: str, data: ClientPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return serialize_client(client)


@app.get("/projects")
def list_projects(status_filter: Annotated[ProjectStatus | None, Query(alias="status")] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Project).order_by(Project.updated_at.desc(), Project.name)
    query = client_scope(query, user, Project.client_id)
    if status_filter:
        query = query.where(Project.status == status_filter)
    return [serialize_project(row, user, db) for row in db.scalars(query).all()]


@app.get("/projects/{project_id}")
def read_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user)
    return serialize_project(project, user, db)


@app.post("/projects", status_code=201)
def create_project(data: ProjectCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    if not db.get(Client, data.client_id):
        raise HTTPException(status_code=422, detail="Cliente não encontrado")
    manager = db.get(User, data.manager_id)
    if not manager:
        raise HTTPException(status_code=422, detail="Gerente não encontrado")
    if manager.status != UserStatus.ACTIVE or manager.role not in {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT}:
        raise HTTPException(status_code=422, detail="O gerente deve ser um usuário interno ativo")
    project = Project(id=str(uuid.uuid4()), **data.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return serialize_project(project, user, db)


@app.patch("/projects/{project_id}")
def update_project(project_id: str, data: ProjectPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        raise HTTPException(status_code=403, detail="Clientes podem consultar e apontar horas, mas não editar o projeto")
    if data.manager_id is not None:
        manager = db.get(User, data.manager_id)
        if not manager or manager.status != UserStatus.ACTIVE or manager.role not in {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT}:
            raise HTTPException(status_code=422, detail="O gerente deve ser um usuário interno ativo")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return serialize_project(project, user, db)


@app.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    db.delete(project)
    db.commit()


@app.get("/projects/{project_id}/tasks")
def list_tasks(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user)
    return [serialize_task(row, db) for row in db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.wbs_code)).all()]


@app.post("/tasks", status_code=201)
def create_task(data: TaskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user, write=True)
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        raise HTTPException(status_code=403, detail="Clientes não podem criar tarefas")
    values = data.model_dump()
    predecessor_task_id = values.pop("predecessor_task_id", None)
    dependency_type = values.pop("dependency_type", "FS")
    lag_days = values.pop("lag_days", 0)
    if "duration_days" not in data.model_fields_set and data.planned_start_date and data.planned_end_date:
        values["duration_days"] = _duration_days(BusinessCalendar(), data.planned_start_date, data.planned_end_date)
    # WBS é derivado da posição; o valor recebido por compatibilidade é ignorado.
    values["wbs_code"] = ""
    task = Task(id=str(uuid.uuid4()), **values)
    validate_task_parent(db, task, task.parent_task_id)
    if task.baseline_id:
        baseline = db.get(Baseline, task.baseline_id)
        if not baseline or baseline.project_id != task.project_id:
            raise HTTPException(status_code=422, detail="A linha de base deve pertencer ao mesmo projeto")
    db.add(task)
    db.flush()
    schedule_task_dates(db, task)
    if predecessor_task_id:
        predecessor = db.get(Task, predecessor_task_id)
        if not predecessor:
            raise HTTPException(status_code=422, detail="Tarefa predecessora não encontrada")
        if predecessor.project_id != task.project_id:
            raise HTTPException(status_code=422, detail="As tarefas da dependência devem pertencer ao mesmo projeto")
        if predecessor.id == task.id:
            raise HTTPException(status_code=422, detail="Uma tarefa não pode depender dela mesma")
        dependency = TaskDependency(predecessor_task_id=predecessor.id, successor_task_id=task.id, dependency_type=dependency_type, lag_days=lag_days)
        db.add(dependency)
        db.flush()
        if predecessor.planned_start_date or predecessor.planned_end_date:
            try:
                reschedule_cascade(db, predecessor.id, calendar_for_task(db, predecessor), lambda successor: calendar_for_task(db, successor))
            except ValueError as exc:
                db.rollback()
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        normalize_task_hierarchy(db, task.project_id, lambda row: calendar_for_task(db, row), lambda row: task_daily_capacity(db, row))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(task)
    return serialize_task(task, db)


@app.patch("/tasks/{task_id}")
def update_task(task_id: str, data: TaskPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    project = db.get(Project, task.project_id)
    require_project_access(project, user, write=True)
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        raise HTTPException(status_code=403, detail="Clientes não podem editar tarefas")

    updates = data.model_dump(exclude_unset=True)
    dependency_fields = {"predecessor_task_id", "dependency_type", "lag_days"}
    dependency_requested = bool(data.model_fields_set & dependency_fields)
    predecessor_field_set = "predecessor_task_id" in data.model_fields_set
    dependency_type_field_set = "dependency_type" in data.model_fields_set
    lag_field_set = "lag_days" in data.model_fields_set
    requested_predecessor_id = updates.pop("predecessor_task_id", None)
    requested_dependency_type = updates.pop("dependency_type", None)
    requested_lag_days = updates.pop("lag_days", None)

    # WBS é sempre derivado. Horas só são derivadas quando a tarefa possui filhos.
    updates.pop("wbs_code", None)
    requested_estimated_hours = updates.pop("estimated_hours", None)
    if requested_estimated_hours is not None and not db.scalar(select(Task.id).where(Task.parent_task_id == task.id)):
        updates["estimated_hours"] = requested_estimated_hours
    for field, value in updates.items():
        setattr(task, field, value)
    if "parent_task_id" in updates:
        task.wbs_code = ""
    validate_task_parent(db, task, task.parent_task_id)
    if task.baseline_id:
        baseline = db.get(Baseline, task.baseline_id)
        if not baseline or baseline.project_id != task.project_id:
            raise HTTPException(status_code=422, detail="A linha de base deve pertencer ao mesmo projeto")

    existing_dependencies = db.scalars(select(TaskDependency).where(TaskDependency.successor_task_id == task.id).order_by(TaskDependency.id)).all()
    predecessor_for_reschedule: Task | None = None
    if dependency_requested:
        current_dependency = existing_dependencies[0] if existing_dependencies else None
        predecessor_id = requested_predecessor_id if predecessor_field_set else (current_dependency.predecessor_task_id if current_dependency else None)
        dependency_type = requested_dependency_type if dependency_type_field_set else (current_dependency.dependency_type.value if current_dependency else "FS")
        lag_days = requested_lag_days if lag_field_set else (current_dependency.lag_days if current_dependency else 0)
        for dependency in existing_dependencies:
            db.delete(dependency)
        db.flush()
        if predecessor_id:
            predecessor = db.get(Task, predecessor_id)
            if not predecessor:
                raise HTTPException(status_code=422, detail="Tarefa predecessora não encontrada")
            if predecessor.project_id != task.project_id:
                raise HTTPException(status_code=422, detail="As tarefas da dependência devem pertencer ao mesmo projeto")
            if predecessor.id == task.id:
                raise HTTPException(status_code=422, detail="Uma tarefa não pode depender dela mesma")
            db.add(TaskDependency(predecessor_task_id=predecessor.id, successor_task_id=task.id, dependency_type=dependency_type or "FS", lag_days=lag_days or 0))
            db.flush()
            predecessor_for_reschedule = predecessor
    elif existing_dependencies:
        predecessor_for_reschedule = db.get(Task, existing_dependencies[0].predecessor_task_id)

    if "planned_end_date" in updates and "duration_days" not in updates and task.planned_start_date and task.planned_end_date:
        task.duration_days = _duration_days(calendar_for_task(db, task), task.planned_start_date, task.planned_end_date)
    schedule_changed = bool({"estimated_hours", "planned_start_date", "duration_days", "planned_end_date"} & updates.keys())
    cascaded_ids: list[str] = []
    if schedule_changed or dependency_requested:
        schedule_task_dates(db, task)
        cascade_root = predecessor_for_reschedule or task
        if cascade_root.planned_start_date or cascade_root.planned_end_date:
            try:
                cascaded_ids = [row.id for row in reschedule_cascade(db, cascade_root.id, calendar_for_task(db, cascade_root), lambda successor: calendar_for_task(db, successor))]
            except ValueError as exc:
                db.rollback()
                raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        normalize_task_hierarchy(db, task.project_id, lambda row: calendar_for_task(db, row), lambda row: task_daily_capacity(db, row))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(task)
    payload = serialize_task(task, db)
    payload["cascaded_task_ids"] = cascaded_ids
    return payload


@app.post("/tasks/{task_id}/assignments", status_code=201)
def assign_resource_to_task(task_id: str, data: TaskAssignmentCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    resource = db.get(Resource, data.resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    if db.scalar(select(TaskAssignment).where(TaskAssignment.task_id == task_id, TaskAssignment.resource_id == data.resource_id)):
        raise HTTPException(status_code=409, detail="Recurso já atribuído a esta tarefa")
    assignment = TaskAssignment(task_id=task_id, resource_id=data.resource_id, allocated_hours=data.allocated_hours)
    db.add(assignment)
    db.flush()
    if task.planned_start_date:
        schedule_task_dates(db, task)
    try:
        normalize_task_hierarchy(db, task.project_id, lambda row: calendar_for_task(db, row), lambda row: task_daily_capacity(db, row))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(assignment)
    return {"id": assignment.id, "task_id": assignment.task_id, "resource_id": assignment.resource_id, "allocated_hours": assignment.allocated_hours, "calendar_id": resource.calendar_id}


@app.patch("/tasks/{task_id}/assignments/{assignment_id}")
def update_task_assignment(task_id: str, assignment_id: str, data: TaskAssignmentPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    task = db.get(Task, task_id)
    assignment = db.get(TaskAssignment, assignment_id)
    if not task or not assignment or assignment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Atribuição não encontrada")
    assignment.allocated_hours = data.allocated_hours
    if task.planned_start_date:
        schedule_task_dates(db, task)
    try:
        normalize_task_hierarchy(db, task.project_id, lambda row: calendar_for_task(db, row), lambda row: task_daily_capacity(db, row))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(assignment)
    resource = db.get(Resource, assignment.resource_id)
    return {"id": assignment.id, "task_id": assignment.task_id, "resource_id": assignment.resource_id, "allocated_hours": assignment.allocated_hours, "calendar_id": resource.calendar_id if resource else None}


@app.delete("/tasks/{task_id}/assignments/{assignment_id}", status_code=204)
def delete_task_assignment(task_id: str, assignment_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    task = db.get(Task, task_id)
    assignment = db.get(TaskAssignment, assignment_id)
    if not task or not assignment or assignment.task_id != task_id:
        raise HTTPException(status_code=404, detail="Atribuição não encontrada")
    db.delete(assignment)
    db.flush()
    try:
        normalize_task_hierarchy(db, task.project_id, lambda row: calendar_for_task(db, row), lambda row: task_daily_capacity(db, row))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()


@app.post("/tasks/{task_id}/dependencies", status_code=201)
def create_task_dependency(task_id: str, data: TaskDependencyCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    predecessor = db.get(Task, task_id)
    successor = db.get(Task, data.successor_task_id)
    if not predecessor or not successor:
        raise HTTPException(status_code=404, detail="Tarefa predecessora ou sucessora não encontrada")
    if predecessor.project_id != successor.project_id:
        raise HTTPException(status_code=422, detail="As tarefas da dependência devem pertencer ao mesmo projeto")
    if predecessor.id == successor.id:
        raise HTTPException(status_code=422, detail="Uma tarefa não pode depender dela mesma")
    if db.scalar(select(TaskDependency).where(TaskDependency.predecessor_task_id == task_id, TaskDependency.successor_task_id == successor.id)):
        raise HTTPException(status_code=409, detail="A dependência entre as tarefas já existe")
    dependency = TaskDependency(predecessor_task_id=task_id, successor_task_id=successor.id, dependency_type=data.dependency_type, lag_days=data.lag_days)
    db.add(dependency)
    db.flush()
    cascaded_ids: list[str] = []
    if predecessor.planned_start_date or predecessor.planned_end_date:
        try:
            cascaded_ids = [row.id for row in reschedule_cascade(db, predecessor.id, calendar_for_task(db, predecessor), lambda successor: calendar_for_task(db, successor))]
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()
    db.refresh(dependency)
    return {"id": dependency.id, "predecessor_task_id": dependency.predecessor_task_id, "successor_task_id": successor.id, "dependency_type": dependency.dependency_type.value, "lag_days": dependency.lag_days, "cascaded_task_ids": cascaded_ids}


@app.delete("/tasks/{task_id}/dependencies/{dependency_id}", status_code=204)
def delete_task_dependency(task_id: str, dependency_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    dependency = db.get(TaskDependency, dependency_id)
    if not dependency or dependency.predecessor_task_id != task_id:
        raise HTTPException(status_code=404, detail="Dependência não encontrada")
    db.delete(dependency)
    db.commit()


@app.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    project = db.get(Project, task.project_id)
    require_project_access(project, user, write=True)
    if db.scalar(select(Timesheet.id).where(Timesheet.task_id == task.id)):
        raise HTTPException(status_code=409, detail="A tarefa não pode ser excluída porque possui apontamentos. Remova ou corrija os apontamentos antes.")
    if db.scalar(select(Task.id).where(Task.parent_task_id == task.id)):
        raise HTTPException(status_code=409, detail="A tarefa não pode ser excluída porque possui atividades filhas. Exclua ou mova as filhas primeiro.")
    project_id = task.project_id
    db.delete(task)
    db.flush()
    try:
        normalize_task_hierarchy(db, project_id, lambda row: calendar_for_task(db, row), lambda row: task_daily_capacity(db, row))
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    db.commit()


@app.post("/timesheets", status_code=201)
def create_timesheet(data: TimesheetCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = db.get(Task, data.task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")
    project = db.get(Project, task.project_id)
    require_project_access(project, user, write=True)
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource:
        raise HTTPException(status_code=422, detail="Usuário não possui recurso habilitado")
    entry = Timesheet(task_id=task.id, resource_id=resource.id, date=data.date, hours_spent=data.hours_spent, description=data.description)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "task_id": entry.task_id, "date": entry.date, "hours_spent": entry.hours_spent, "status": entry.status.value}


@app.patch("/timesheets/{timesheet_id}")
def update_timesheet(timesheet_id: str, data: TimesheetPatch, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Apontamento não encontrado")
    task = db.get(Task, entry.task_id)
    project = db.get(Project, task.project_id)
    require_project_access(project, user, write=True)
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource or entry.resource_id != resource.id:
        require_internal(user)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return {"id": entry.id, "task_id": entry.task_id, "date": entry.date, "hours_spent": entry.hours_spent, "description": entry.description, "status": entry.status.value}


@app.delete("/timesheets/{timesheet_id}", status_code=204)
def delete_timesheet(timesheet_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    entry = db.get(Timesheet, timesheet_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Apontamento não encontrado")
    task = db.get(Task, entry.task_id)
    project = db.get(Project, task.project_id)
    require_project_access(project, user, write=True)
    resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
    if not resource or entry.resource_id != resource.id:
        require_internal(user)
    db.delete(entry)
    db.commit()


@app.delete("/clients/{client_id}", status_code=204)
def delete_client(client_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_internal(user)
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    db.delete(client)
    db.commit()


@app.get("/timesheets")
def list_timesheets(project_id: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = select(Timesheet).join(Task, Timesheet.task_id == Task.id).join(Project, Task.project_id == Project.id).order_by(Timesheet.date.desc())
    if user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        query = query.where(Project.client_id == user.client_id)
    if project_id:
        query = query.where(Project.id == project_id)
    return [{"id": row.id, "task_id": row.task_id, "date": row.date, "hours_spent": row.hours_spent, "description": row.description, "status": row.status.value} for row in db.scalars(query).all()]
