from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import EXTERNAL_ROLES, get_current_user, require_project_access, require_roles
from ..models import Project, Task, TaskDependency, TaskStatus, User, UserRole
from ..schemas import (
    DashboardResponse,
    GanttResponse,
    ProjectPortfolioRow,
    ProjectReportResponse,
    ResourceUtilizationRow,
    RiskMatrixResponse,
    RoiRow,
    VelocityPoint,
)
from ..services import (
    financials_by_task_type,
    portfolio_rows,
    project_burndown,
    project_financials,
    project_progress,
    project_roi,
    resource_utilization,
    risk_matrix,
    velocity_series,
)

router = APIRouter(tags=["reports"])


def _get_project_or_404(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Projeto não encontrado")
    return project


def _scoped_projects(db: Session, user: User) -> list[Project]:
    stmt = select(Project)
    if user.role in EXTERNAL_ROLES:
        stmt = stmt.where(Project.client_id == user.client_id)
    return list(db.scalars(stmt).all())


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Visão geral do portfólio: contagens por status, tarefas por tipo,
    tarefas atrasadas e a listagem "portfolio" (uma linha por projeto).
    Perfis externos enxergam só os projetos do próprio cliente, e sem
    margem (mesmo tratamento de ProjectDetail/GET /reports/portfolio)."""
    projects = _scoped_projects(db, user)
    project_ids = [p.id for p in projects]
    tasks = list(db.scalars(select(Task).where(Task.project_id.in_(project_ids))).all()) if project_ids else []

    projects_by_status: dict[str, int] = {}
    for project in projects:
        projects_by_status[project.status.value] = projects_by_status.get(project.status.value, 0) + 1

    tasks_by_status: dict[str, int] = {}
    tasks_by_type: dict[str, int] = {}
    tasks_overdue = 0
    today = date.today()
    for task in tasks:
        tasks_by_status[task.status.value] = tasks_by_status.get(task.status.value, 0) + 1
        tasks_by_type[task.task_type.value] = tasks_by_type.get(task.task_type.value, 0) + 1
        if task.planned_end_date and task.planned_end_date < today and task.status != TaskStatus.COMPLETED:
            tasks_overdue += 1

    avg_progress = (sum((Decimal(t.progress_percentage or 0) for t in tasks), Decimal("0")) / len(tasks)) if tasks else Decimal("0")

    return {
        "projects_total": len(projects),
        "projects_by_status": projects_by_status,
        "tasks_total": len(tasks),
        "tasks_by_status": tasks_by_status,
        "tasks_by_type": tasks_by_type,
        "tasks_overdue": tasks_overdue,
        "avg_progress_percentage": avg_progress.quantize(Decimal("0.01")),
        "portfolio": portfolio_rows(db, projects, include_financials=user.role not in EXTERNAL_ROLES),
    }


@router.get("/reports/portfolio", response_model=list[ProjectPortfolioRow])
def portfolio(
    client_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Uma linha por projeto no escopo do usuário — o "portfolio view"
    referenciado nas ferramentas de mercado (Monday.com, MS Project)."""
    projects = _scoped_projects(db, user)
    if client_id and user.role not in EXTERNAL_ROLES:
        projects = [p for p in projects if p.client_id == client_id]
    return portfolio_rows(db, projects, include_financials=user.role not in EXTERNAL_ROLES)


@router.get("/projects/{project_id}/report", response_model=ProjectReportResponse)
def project_report(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Relatório consolidado do projeto: progresso, tarefas restantes,
    financeiro (Budget vs Actual, com quebra por task_type quando o perfil
    tem acesso a dado financeiro) e burndown."""
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user)
    progress = project_progress(db, project_id)
    financials = None
    financials_by_type = None
    if user.role not in EXTERNAL_ROLES:
        financials = project_financials(db, project_id)
        financials_by_type = financials_by_task_type(db, project_id)
    return {
        "project_id": project_id,
        "percent_complete": progress["percent_complete"],
        "tasks_total": progress["tasks_total"],
        "tasks_remaining": progress["tasks_remaining"],
        "tasks_by_status": progress["tasks_by_status"],
        "financials": financials,
        "financials_by_task_type": financials_by_type,
        "burndown": project_burndown(db, project_id),
    }


@router.get("/resources/utilization", response_model=list[ResourceUtilizationRow])
def utilization(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    resource_id: str | None = None,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Workload/capacidade × demanda por recurso — sem `start`/`end`, usa o
    mês corrente. Restrito a perfis internos, no mesmo padrão de GET
    /resources/{id} (dado sensível de custo/capacidade da equipe)."""
    today = date.today()
    period_start = start or today.replace(day=1)
    if end:
        period_end = end
    else:
        next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        period_end = next_month - timedelta(days=1)
    if period_start > period_end:
        raise HTTPException(status_code=422, detail="start precisa ser anterior ou igual a end")
    return resource_utilization(db, start=period_start, end=period_end, resource_id=resource_id)


@router.get("/projects/{project_id}/risks/matrix", response_model=RiskMatrixResponse)
def project_risk_matrix(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user)
    return risk_matrix(db, project_id)


@router.get("/reports/velocity", response_model=list[VelocityPoint])
def velocity(
    project_id: str | None = None,
    resource_id: str | None = None,
    granularity: str = Query(default="week", pattern="^(week|month)$"),
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Horas entregues por semana/mês (definição confirmada pelo usuário:
    não é velocidade de Scrum). Sem `project_id`, é uma métrica de
    portfólio — só perfis internos podem pedir nesse escopo; perfis
    externos precisam informar um `project_id` do próprio cliente."""
    if project_id:
        project = _get_project_or_404(db, project_id)
        require_project_access(project, user)
    elif user.role in EXTERNAL_ROLES:
        raise HTTPException(status_code=422, detail="Cliente precisa informar project_id")
    period_end = end or date.today()
    period_start = start or (period_end - timedelta(days=90))
    if period_start > period_end:
        raise HTTPException(status_code=422, detail="start precisa ser anterior ou igual a end")
    return velocity_series(db, start=period_start, end=period_end, granularity=granularity, project_id=project_id, resource_id=resource_id)


@router.get("/reports/roi", response_model=list[RoiRow])
def roi(
    project_id: str | None = None,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """ROI (margem ÷ custo real — ver docstring de project_roi) por
    projeto. Dado financeiro: restrito a ADMIN/INTERNAL_PM, como o resto
    dos campos financeiros da API."""
    if project_id:
        _get_project_or_404(db, project_id)
        return [project_roi(db, project_id)]
    projects = list(db.scalars(select(Project)).all())
    return [project_roi(db, project.id) for project in projects]


@router.get("/projects/{project_id}/gantt", response_model=GanttResponse)
def gantt(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Tarefas (ordenadas por WBS) + dependências do projeto num único
    payload, no formato que um Gantt (estilo MS Project) espera para
    desenhar barras e setas sem N chamadas separadas."""
    project = _get_project_or_404(db, project_id)
    require_project_access(project, user)
    tasks = list(db.scalars(select(Task).where(Task.project_id == project_id).order_by(Task.wbs_code)).all())
    task_ids = [t.id for t in tasks]
    dependencies = (
        list(
            db.scalars(
                select(TaskDependency).where(
                    or_(TaskDependency.predecessor_task_id.in_(task_ids), TaskDependency.successor_task_id.in_(task_ids))
                )
            ).all()
        )
        if task_ids
        else []
    )
    return {"tasks": tasks, "dependencies": dependencies}
