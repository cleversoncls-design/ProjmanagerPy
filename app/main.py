from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
import os

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Project, Task, Timesheet, User, UserRole, UserStatus, Resource
from .services import project_financials

RAW_DATABASE_URL = os.getenv("DATABASE_URL")
if RAW_DATABASE_URL:
    DATABASE_URL = RAW_DATABASE_URL
elif os.getenv("POSTGRES_PASSWORD"):
    # URL.create escapa a senha corretamente; '@', ':', '/', '#', etc. não quebram o hostname.
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

engine_kwargs = {"pool_pre_ping": True}
if str(DATABASE_URL).startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)
app = FastAPI(title="Controle de Projetos Corporativo", version="0.1.0")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(x_user_id: Annotated[str | None, Header()] = None, db: Session = Depends(get_db)) -> User:
    # Em produção, substituir por validação de JWT/OIDC; o exemplo mantém a autorização explícita.
    if not x_user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credencial ausente")
    user = db.get(User, x_user_id)
    if not user or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido ou inativo")
    return user


def require_project_access(project: Project, user: User, write: bool = False) -> None:
    external = user.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}
    if external and project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Projeto fora do escopo do cliente")
    if write and external and user.role not in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Perfil sem permissão de escrita")


class TimesheetCreate(BaseModel):
    task_id: str
    date: date
    hours_spent: Decimal = Field(gt=0, le=24)
    description: str | None = None


@app.get("/projects/{project_id}")
def read_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    require_project_access(project, user)
    payload = {"id": project.id, "code": project.code, "name": project.name, "client_id": project.client_id, "status": project.status.value}
    if user.role not in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        payload["sold_value"] = project.sold_value
        payload["financials"] = project_financials(db, project.id)
    return payload


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
    return {"id": entry.id, "task_id": entry.task_id, "hours_spent": entry.hours_spent, "status": entry.status.value}
