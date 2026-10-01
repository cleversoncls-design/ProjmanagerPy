from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import EXTERNAL_ROLES, INTERNAL_ROLES, get_current_user, require_project_access, require_roles
from ..exports import build_service_orders_workbook, build_tasks_workbook
from ..i18n import t as translate
from ..models import Project, ProjectStatus, Resource, Task, TaskDependency, TaskStatus, User, UserRole
from ..schemas import (
    DashboardResponse,
    EvmMetrics,
    GanttResponse,
    ProjectPortfolioRow,
    ProjectReportResponse,
    ProjectScheduleResponse,
    ProjectStatisticsResponse,
    RiskMatrixResponse,
    RoiRow,
    ServiceOrderRow,
    VelocityPoint,
)
from ..services import (
    financials_by_task_type,
    portfolio_rows,
    project_burndown,
    project_evm,
    project_financials,
    project_progress,
    project_statistics,
    project_roi,
    risk_matrix,
    service_orders,
    task_schedule_rows,
    velocity_series,
)

router = APIRouter(tags=["reports"])


def _get_project_or_404(db: Session, project_id: str, lang: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", lang))
    return project


def _scoped_projects(db: Session, user: User, include_modelo: bool = False) -> list[Project]:
    # Projeto MODELO nunca entra em indicador/dashboard — ele só existe
    # como base de estrutura pro botão "Copiar estrutura de outro projeto"
    # (ver routers/projects.py copy_tasks_from), não é trabalho real em
    # andamento. `dashboard()` abaixo sempre chama isto com o padrão
    # (include_modelo=False, nenhum indicador nunca conta Modelo). Já a
    # tela de Projetos (GET /reports/portfolio) é só uma listagem — o
    # usuário pode querer ver o Modelo ali pra abrir e manter a estrutura
    # dele, daí o botão "Mostrar projetos Modelo" que liga include_modelo
    # nesse endpoint. Endpoints por project_id direto (report/evm/
    # statistics/schedule/gantt) continuam acessíveis normalmente sempre,
    # independente disto — é assim que o usuário abre e mantém a estrutura
    # do próprio Modelo mesmo sem passar por aqui.
    #
    # INTERNAL_PM só enxerga os projetos onde é o gerente (Project.
    # manager_id) — pedido do usuário: "ainda posso ver com meu acesso de
    # gerente de projetos, projetos de outros gerentes" na tela de
    # Projetos. Mesma ideia já aplicada em GET /timesheets (Aprovações
    # pendentes). ADMIN continua vendo tudo, sem essa restrição — é quem
    # precisa de visão completa do portfólio. O filtro manual "Gerente" em
    # GET /reports/portfolio (abaixo) segue existindo pra quem ainda
    # enxerga mais de um gerente (ADMIN).
    stmt = select(Project)
    if not include_modelo:
        stmt = stmt.where(Project.status != ProjectStatus.MODELO)
    if user.role in EXTERNAL_ROLES:
        stmt = stmt.where(Project.client_id == user.client_id)
    elif user.role == UserRole.INTERNAL_PM:
        stmt = stmt.where(Project.manager_id == user.id)
    return list(db.scalars(stmt).all())


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    # Dashboard ficou só com Admin e os perfis externos do cliente (revisão
    # de acessos do usuário) — Gerente de Projetos e Consultor perderam
    # esse item de menu; mesmos perfis de DASHBOARD_ROLES no frontend
    # (utils/labels.js), restrito aqui também pra não depender só da UI
    # esconder a rota.
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.CLIENT_PM, UserRole.CLIENT_USER)),
    db: Session = Depends(get_db),
) -> dict:
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
    manager_id: str | None = None,
    status: ProjectStatus | None = None,
    include_modelo: bool = False,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Uma linha por projeto no escopo do usuário — o "portfolio view"
    referenciado nas ferramentas de mercado (Monday.com, MS Project).
    `client_id` (filtro da tela de Projetos) só se aplica pra quem enxerga
    mais de um cliente — perfil externo já é travado num cliente só (ver
    _scoped_projects). `manager_id` (pedido do usuário: filtro por gerente
    do projeto na tela de Projetos) não precisa de tratamento especial por
    papel — o gerente é sempre ADMIN/INTERNAL_PM, então filtrar por ele
    nunca vaza projeto de fora do escopo já resolvido por
    _scoped_projects/client_id acima. `include_modelo` é o botão "Mostrar
    projetos Modelo" da tela de Projetos — sem ele (padrão) o Modelo fica
    de fora daqui igual no Dashboard; com ele, aparece misturado no
    resultado (pedir status=MODELO junto implica include_modelo, pra não
    devolver uma lista vazia por engano)."""
    if status == ProjectStatus.MODELO:
        include_modelo = True
    projects = _scoped_projects(db, user, include_modelo=include_modelo)
    if client_id and user.role not in EXTERNAL_ROLES:
        projects = [p for p in projects if p.client_id == client_id]
    if manager_id:
        projects = [p for p in projects if p.manager_id == manager_id]
    if status:
        projects = [p for p in projects if p.status == status]
    return portfolio_rows(db, projects, include_financials=user.role not in EXTERNAL_ROLES)


@router.get("/projects/{project_id}/report", response_model=ProjectReportResponse)
def project_report(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Relatório consolidado do projeto: progresso, tarefas restantes,
    financeiro (Budget vs Actual, com quebra por task_type quando o perfil
    tem acesso a dado financeiro) e burndown."""
    project = _get_project_or_404(db, project_id, user.language)
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


@router.get("/projects/{project_id}/risks/matrix", response_model=RiskMatrixResponse)
def project_risk_matrix(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    project = _get_project_or_404(db, project_id, user.language)
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
        project = _get_project_or_404(db, project_id, user.language)
        require_project_access(project, user)
    elif user.role in EXTERNAL_ROLES:
        raise HTTPException(status_code=422, detail=translate("Cliente precisa informar project_id", user.language))
    period_end = end or date.today()
    period_start = start or (period_end - timedelta(days=90))
    if period_start > period_end:
        raise HTTPException(status_code=422, detail=translate("start precisa ser anterior ou igual a end", user.language))
    return velocity_series(db, start=period_start, end=period_end, granularity=granularity, project_id=project_id, resource_id=resource_id)


@router.get("/reports/roi", response_model=list[RoiRow])
def roi(
    project_id: str | None = None,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """ROI (margem ÷ custo real — ver docstring de project_roi) por
    projeto. Dado financeiro: restrito a ADMIN/INTERNAL_PM, como o resto
    dos campos financeiros da API."""
    if project_id:
        _get_project_or_404(db, project_id, user.language)
        return [project_roi(db, project_id)]
    # Mesma regra de _scoped_projects: projeto MODELO fica fora do ROI
    # agregado (só é chamado direto por project_id, não como parte da
    # listagem "todos os projetos").
    projects = list(db.scalars(select(Project).where(Project.status != ProjectStatus.MODELO)).all())
    return [project_roi(db, project.id) for project in projects]


def _resolve_service_orders_scope(
    db: Session,
    user: User,
    *,
    project_id: str | None,
    resource_id: str | None,
    start: date | None,
    end: date | None,
) -> tuple[date, date, str | None]:
    """Escopo/validação compartilhados por GET /reports/service-orders e
    GET /reports/service-orders/export.xlsx: CONSULTANT só enxerga a
    própria OS (resource_id de terceiro é sempre substituído — mesma regra
    de escopo de GET /timesheets; sem recurso vinculado, um resource_id que
    não bate com nenhum registro real faz `service_orders` devolver lista
    vazia, sem precisar de um retorno antecipado aqui), período default de
    30 dias terminando hoje, start<=end, e acesso ao projeto quando
    informado."""
    if user.role == UserRole.CONSULTANT:
        own_resource = db.scalar(select(Resource).where(Resource.user_id == user.id))
        resource_id = own_resource.id if own_resource else "__sem_recurso__"
    period_end = end or date.today()
    period_start = start or (period_end - timedelta(days=30))
    if period_start > period_end:
        raise HTTPException(status_code=422, detail=translate("start precisa ser anterior ou igual a end", user.language))
    if project_id:
        project = _get_project_or_404(db, project_id, user.language)
        require_project_access(project, user)
    return period_start, period_end, resource_id


@router.get("/reports/service-orders", response_model=list[ServiceOrderRow])
def service_orders_report(
    project_id: str | None = None,
    resource_id: str | None = None,
    client_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*INTERNAL_ROLES)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Prévia da Ordem de Serviço (Fase 3 do apontamento) — 1 OS por dia +
    projeto + consultor, a partir dos apontamentos já lançados (ver
    `service_orders` em services.py). Documento interno (dados de horas e
    consultor por trás do serviço prestado) — restrito aos perfis internos,
    igual à Agenda de consultores; o frontend renderiza tanto a tabela
    quanto a impressão (individual e a lista agrupada por consultor, ver
    ServiceOrderPrintSheet.jsx/ServiceOrderListPrintSheet.jsx) a partir
    destes mesmos dados."""
    period_start, period_end, resource_id = _resolve_service_orders_scope(
        db, user, project_id=project_id, resource_id=resource_id, start=start, end=end
    )
    return service_orders(db, start=period_start, end=period_end, project_id=project_id, resource_id=resource_id, client_id=client_id)


@router.get("/reports/service-orders/export.xlsx")
def service_orders_export_xlsx(
    project_id: str | None = None,
    resource_id: str | None = None,
    client_id: str | None = None,
    start: date | None = None,
    end: date | None = None,
    user: User = Depends(require_roles(*INTERNAL_ROLES)),
    db: Session = Depends(get_db),
) -> Response:
    """Exporta as Ordens de Serviço do período filtrado pra .xlsx, uma linha
    por tarefa/atividade apontada (não mais um resumo por OS), organizada
    por dia, cliente e projeto — pedido do usuário — com subtotal por OS e
    total geral. Mesmo escopo/filtros de GET /reports/service-orders (ver
    `_resolve_service_orders_scope` acima), ver
    app/exports.build_service_orders_workbook."""
    period_start, period_end, resource_id = _resolve_service_orders_scope(
        db, user, project_id=project_id, resource_id=resource_id, start=start, end=end
    )
    content = build_service_orders_workbook(
        db, start=period_start, end=period_end, project_id=project_id, resource_id=resource_id, client_id=client_id
    )
    filename = f"ordens_de_servico_{period_start.isoformat()}_{period_end.isoformat()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/schedule", response_model=ProjectScheduleResponse)
def project_schedule(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Grade de cronograma enriquecida (bolinha de status, linha base, %
    previsto por tarefa) — igual a GET /gantt em conteúdo de tarefas, mas
    com os campos calculados que a tela de tarefas/Gantt do frontend
    precisa para pintar o status sem recalcular nada no cliente."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    schedule = task_schedule_rows(db, project)
    tasks_payload = []
    for row in schedule["rows"]:
        t = row["task"]
        tasks_payload.append(
            {
                **{c.name: getattr(t, c.name) for c in t.__table__.columns},
                "status_dot": row["status_dot"],
                "rollup_start_date": row["rollup_start_date"],
                "rollup_end_date": row["rollup_end_date"],
                "rollup_duration_days": row["rollup_duration_days"],
                "rollup_estimated_hours": row["rollup_estimated_hours"],
                "baseline_start_date": row["baseline_start_date"],
                "baseline_end_date": row["baseline_end_date"],
                "baseline_estimated_hours": row["baseline_estimated_hours"],
                "planned_percent_complete": row["planned_percent_complete"],
                "spi": row["spi"],
                "cpi": row["cpi"],
            }
        )
    task_ids = [row["task"].id for row in schedule["rows"]]
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
    return {"status_date": schedule["status_date"], "tasks": tasks_payload, "dependencies": dependencies}


@router.get("/projects/{project_id}/tasks/export.xlsx")
def export_tasks_xlsx(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    """Exporta a grade de tarefas pra .xlsx (Excel/LibreOffice/OpenOffice) —
    mesmos dados calculados de GET /schedule (rollup, linha de base, SPI/CPI
    por tarefa), ver app/exports.build_tasks_workbook."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    content = build_tasks_workbook(db, project)
    filename = f"{project.code}_tarefas.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/report.evm", response_model=EvmMetrics)
def project_evm_report(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """SPI/CPI e % previsto (Earned Value em base de horas — ver docstring
    de services.project_evm)."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    return project_evm(db, project_id)


@router.get("/projects/{project_id}/statistics", response_model=ProjectStatisticsResponse)
def project_statistics_report(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Equivalente a "Project Statistics" do MS Project (ver tela de
    referência do usuário). O custo de `actual` é ocultado para perfis
    externos, no mesmo padrão de ProjectDetail/financials."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    stats = project_statistics(db, project_id)
    if user.role in EXTERNAL_ROLES:
        stats["actual"]["cost"] = None
    return stats


@router.get("/projects/{project_id}/gantt", response_model=GanttResponse)
def gantt(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    """Tarefas (ordenadas por WBS) + dependências do projeto num único
    payload, no formato que um Gantt (estilo MS Project) espera para
    desenhar barras e setas sem N chamadas separadas."""
    project = _get_project_or_404(db, project_id, user.language)
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
