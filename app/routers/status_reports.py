from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import EXTERNAL_ROLES, MANAGEMENT_ROLES, get_current_user, require_project_access, require_roles
from ..i18n import t as translate
from ..models import Project, ProjectStatusReport, User
from ..schemas import StatusReportCreate, StatusReportRagSuggestion, StatusReportRead, StatusReportUpdate
from ..services import build_status_report_snapshot, suggest_status_report_rag

router = APIRouter(tags=["status-reports"])


def _get_project_or_404(db: Session, project_id: str, lang: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", lang))
    return project


def _get_report_or_404(db: Session, project_id: str, report_id: str, lang: str) -> ProjectStatusReport:
    report = db.get(ProjectStatusReport, report_id)
    if not report or report.project_id != project_id:
        raise HTTPException(status_code=404, detail=translate("Status report não encontrado", lang))
    return report


def _serialize(report: ProjectStatusReport, user: User) -> StatusReportRead:
    """Mesmo critério de GET /projects/{id}/report (ver `financials` em
    routers/reports.py): EXTERNAL_ROLES (CLIENT_PM/CLIENT_USER) recebem os
    campos financeiros e `next_steps_internal` como `None`, e `burndown`
    como lista vazia — nunca um valor "zerado" fajuto, que seria
    indistinguível de um resultado real. `tasks_done`/`tasks_next`/
    `risks_snapshot` aparecem para os dois perfis (os dois mockups —
    Interno e Cliente — mostram "semana anterior × próxima semana" e a
    tabela de riscos)."""
    external = user.role in EXTERNAL_ROLES
    return StatusReportRead.model_validate(
        {
            "id": report.id,
            "project_id": report.project_id,
            "period_start": report.period_start,
            "period_end": report.period_end,
            "prepared_by_id": report.prepared_by_id,
            "created_at": report.created_at,
            "rag_schedule": report.rag_schedule,
            "rag_cost": report.rag_cost,
            "rag_margin": report.rag_margin,
            "rag_scope": report.rag_scope,
            "rag_risk": report.rag_risk,
            "executive_summary": report.executive_summary,
            "next_steps_client": report.next_steps_client,
            "next_steps_internal": None if external else report.next_steps_internal,
            "schedule_actual_pct": report.schedule_actual_pct,
            "schedule_planned_pct": report.schedule_planned_pct,
            "hours_consumed": None if external else report.hours_consumed,
            "hours_budgeted": None if external else report.hours_budgeted,
            "cost_planned": None if external else report.cost_planned,
            "cost_actual": None if external else report.cost_actual,
            "margin_planned_pct": None if external else report.margin_planned_pct,
            "margin_actual_pct": None if external else report.margin_actual_pct,
            "tasks_done": report.tasks_done,
            "tasks_next": report.tasks_next,
            "risks_snapshot": report.risks_snapshot,
            "burndown": [] if external else report.burndown,
        }
    )


@router.post("/projects/{project_id}/status-reports", response_model=StatusReportRead, status_code=201)
def create_status_report(
    project_id: str,
    data: StatusReportCreate,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> StatusReportRead:
    """Cria o "fechamento" do período (pedido do usuário: "pode implementar
    os 2 modelos e colocar na opção de relatorios" — decisão confirmada:
    "Salvar por período"). Restrito a MANAGEMENT_ROLES — quem prepara o
    status report é a gerência/diretoria interna, nunca o cliente
    (EXTERNAL_ROLES é sempre somente leitura, igual ao resto da API — ver
    require_project_access). Os campos calculados (EVM/financeiro/
    burndown/tarefas/riscos) vêm de `build_status_report_snapshot`, nunca
    do corpo da requisição."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user, write=True, allow_consultant_write=False)
    if data.period_start > data.period_end:
        raise HTTPException(status_code=422, detail=translate("period_start precisa ser anterior ou igual a period_end", user.language))
    snapshot = build_status_report_snapshot(db, project_id, period_start=data.period_start, period_end=data.period_end)
    report = ProjectStatusReport(
        project_id=project_id,
        prepared_by_id=user.id,
        **data.model_dump(),
        **snapshot,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _serialize(report, user)


@router.get("/projects/{project_id}/status-reports/suggested-rag", response_model=StatusReportRagSuggestion)
def suggest_status_report_rag_endpoint(
    project_id: str, user: User = Depends(require_roles(*MANAGEMENT_ROLES)), db: Session = Depends(get_db)
) -> dict:
    """Pedido do usuário: "os indicadores [...] venham calculados pelo
    sistema, indicando de forma automática se tudo está dentro do prazo,
    mas que o gerente possa modificar" — sugestão pra pré-preencher o
    formulário de "Novo Status Report" no frontend (ver
    services.suggest_status_report_rag); nunca grava nada. Rota estática
    ("suggested-rag") precisa vir ANTES de GET /status-reports/{report_id}
    no arquivo — senão o FastAPI tentaria casar "suggested-rag" como um
    `report_id`."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    return suggest_status_report_rag(db, project_id)


@router.get("/projects/{project_id}/status-reports", response_model=list[StatusReportRead])
def list_status_reports(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[StatusReportRead]:
    """Histórico de status reports do projeto — mais recente primeiro.
    Acesso de leitura normal (`require_project_access` sem `write`):
    CLIENT_PM/CLIENT_USER do próprio cliente podem listar (pedido original
    do usuário: "onde o gerente do projeto do cliente possa ter acesso"),
    só que com os campos financeiros ocultados (ver `_serialize`)."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    reports = list(
        db.scalars(
            select(ProjectStatusReport).where(ProjectStatusReport.project_id == project_id).order_by(ProjectStatusReport.created_at.desc())
        ).all()
    )
    return [_serialize(report, user) for report in reports]


@router.get("/projects/{project_id}/status-reports/{report_id}", response_model=StatusReportRead)
def get_status_report(
    project_id: str, report_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StatusReportRead:
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user)
    report = _get_report_or_404(db, project_id, report_id, user.language)
    return _serialize(report, user)


@router.patch("/projects/{project_id}/status-reports/{report_id}", response_model=StatusReportRead)
def update_status_report(
    project_id: str,
    report_id: str,
    data: StatusReportUpdate,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> StatusReportRead:
    """Pedido do usuário: "ter opção de modificar". Só os campos
    editoriais/semáforo (ver docstring de StatusReportUpdate) — os dados
    "congelados" no momento da criação (EVM, financeiro, burndown,
    tarefas, riscos, e o próprio período) nunca são recalculados aqui,
    senão deixaria de ser um "fechamento"."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user, write=True, allow_consultant_write=False)
    report = _get_report_or_404(db, project_id, report_id, user.language)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    db.commit()
    db.refresh(report)
    return _serialize(report, user)


@router.delete("/projects/{project_id}/status-reports/{report_id}", status_code=204)
def delete_status_report(
    project_id: str,
    report_id: str,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    """Pedido do usuário: "ter opção de excluir"."""
    project = _get_project_or_404(db, project_id, user.language)
    require_project_access(project, user, write=True, allow_consultant_write=False)
    report = _get_report_or_404(db, project_id, report_id, user.language)
    db.delete(report)
    db.commit()
