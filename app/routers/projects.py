from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..color_palette import PROJECT_COLOR_HEXES
from ..database import get_db
from ..deps import EXTERNAL_ROLES, MANAGEMENT_ROLES, get_current_user, require_project_access, require_roles
from ..i18n import t as translate
from ..models import (
    AuditAction,
    Baseline,
    Calendar,
    ChangeRequest,
    Client,
    Project,
    ProjectExpense,
    ProjectResource,
    ProjectStatus,
    Resource,
    ResourceFunction,
    Risk,
    Task,
    Timesheet,
    User,
    UserRole,
)
from ..schemas import ProjectCreate, ProjectManagerOption, ProjectDetail, ProjectResourceCreate, ProjectResourceRead, ProjectSummary, ProjectUpdate
from ..services import project_financials, sync_task_statuses

router = APIRouter(prefix="/projects", tags=["projects"])

_MANAGER_ERROR = "manager_id precisa ser Administrador, Gerente de Projetos ou Gerente de Serviços com função Gerente de Projetos"


def _is_eligible_project_manager(db: Session, candidate: User | None) -> bool:
    """Quem pode ser Project.manager_id: Administrador e Gerente de Projetos
    sempre; Gerente de Serviços (SERVICE_MANAGER) quando o Recurso dele está
    com a Função "Gerente de Projetos" (pedido do usuário — ele passa a poder
    gerenciar projetos também). Diretor Geral continua de fora, e o acesso
    dele/do Gerente de Serviços aos projetos em si não muda (já veem todos)."""
    if candidate is None:
        return False
    if candidate.role in {UserRole.ADMIN, UserRole.INTERNAL_PM}:
        return True
    if candidate.role == UserRole.SERVICE_MANAGER:
        return (
            db.scalar(
                select(Resource.id).where(Resource.user_id == candidate.id, Resource.function == ResourceFunction.PROJECT_MANAGER)
            )
            is not None
        )
    return False


_FINANCIAL_FIELDS = ("management_hours", "management_rate", "consulting_hours", "consulting_rate")
# Campos financeiros escondidos de perfil externo (CLIENT_PM/CLIENT_USER) —
# os 4 de cima (que também disparam _recompute_sold_value quando mudam) mais
# "% de Margem vendida" (margin_percentage), que não entra no recálculo do
# valor vendido mas é informação financeira da mesma forma.
_EXTERNAL_HIDDEN_FIELDS = _FINANCIAL_FIELDS + ("margin_percentage",)

# Projeto nesses status não disputa exclusividade de cor: MODELO nunca é um
# projeto "de verdade" (ver comentário em ProjectStatus, models.py) e
# COMPLETED/CANCELLED já perderam a cor pro padrão listrado
# (Project.color_striped) — ver pedido do usuário: cor exclusiva "enquanto
# não estiver finalizado", liberando em Concluído e Cancelado, escopo
# global entre todos os clientes.
_COLOR_POOL_EXCLUDED_STATUSES = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED, ProjectStatus.MODELO}
_STRIPED_STATUSES = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}
# Projetos cujas tarefas NÃO acompanham a Data de status (ver sync_task_statuses).
_STATUS_SYNC_EXCLUDED = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED, ProjectStatus.MODELO}


def _ensure_color_available(db: Session, color: str, language: str, *, exclude_project_id: str | None = None) -> None:
    """Levanta 409 se `color` já estiver em uso por outro projeto que ainda
    disputa a exclusividade (fora de COMPLETED/CANCELLED/MODELO). Chamado só
    quando o projeto em questão (o que está sendo criado, ou o resultado da
    atualização) também vai ficar fora desse grupo — um projeto finalizado
    ou Modelo pode ter qualquer cor guardada, ela só não aparece disputando
    a tela enquanto ele estiver nesse estado."""
    stmt = select(Project.id).where(
        Project.color == color,
        Project.status.not_in(_COLOR_POOL_EXCLUDED_STATUSES),
    )
    if exclude_project_id:
        stmt = stmt.where(Project.id != exclude_project_id)
    if db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail=translate("Esta cor já está em uso por outro projeto ativo", language))


def _recompute_sold_value(project: Project) -> None:
    """`sold_value` nunca é digitado diretamente: é sempre horas × taxa de
    cada bolsa (gestão + consultoria), recalculado aqui sempre que qualquer
    um dos quatro campos muda — para nunca ficar dessincronizado do pacote
    realmente vendido."""
    project.sold_value = (project.management_hours * project.management_rate) + (
        project.consulting_hours * project.consulting_rate
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    data: ProjectCreate,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> Project:
    if not db.get(Client, data.client_id):
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", user.language))
    # "Quem pode ser gerente de projeto" é regra à parte de "quem tem acesso
    # equivalente ao Administrador" — ver _is_eligible_project_manager.
    if not _is_eligible_project_manager(db, db.get(User, data.manager_id)):
        raise HTTPException(status_code=422, detail=translate(_MANAGER_ERROR, user.language))
    if db.scalar(select(Project).where(Project.code == data.code)):
        raise HTTPException(status_code=409, detail=translate("Já existe um projeto com este código", user.language))
    if data.calendar_id and not db.get(Calendar, data.calendar_id):
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    if data.color.upper() not in PROJECT_COLOR_HEXES:
        raise HTTPException(status_code=422, detail=translate("Cor do projeto inválida", user.language))
    color = data.color.upper()
    # Projeto novo sempre nasce em PLANNING (ProjectCreate não aceita
    # `status`) — fora do grupo COMPLETED/CANCELLED/MODELO, então sempre
    # disputa a exclusividade de cor.
    _ensure_color_available(db, color, user.language)
    project_data = data.model_dump()
    project_data["color"] = color
    project = Project(**project_data)
    _recompute_sold_value(project)
    db.add(project)
    db.flush()
    record_audit(db, entity_type="project", entity_id=project.id, action=AuditAction.CREATE, user_id=user.id)
    db.commit()
    db.refresh(project)
    return project


@router.get("/eligible-managers", response_model=list[ProjectManagerOption])
def list_eligible_managers(
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> list[User]:
    """Usuários que podem ser escolhidos como gerente de projeto (seletor de
    "Novo projeto"/"Editar projeto" e filtro "Gerente") — ver
    _is_eligible_project_manager. Rota estática: precisa vir ANTES de
    GET /projects/{project_id}."""
    pm_function_user_ids = select(Resource.user_id).where(Resource.function == ResourceFunction.PROJECT_MANAGER)
    stmt = (
        select(User)
        .where(
            or_(
                User.role.in_([UserRole.ADMIN, UserRole.INTERNAL_PM]),
                (User.role == UserRole.SERVICE_MANAGER) & User.id.in_(pm_function_user_ids),
            )
        )
        .order_by(User.name)
    )
    return list(db.scalars(stmt).all())


@router.get("", response_model=list[ProjectSummary])
def list_projects(
    client_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Project]:
    stmt = select(Project)
    if user.role in EXTERNAL_ROLES:
        stmt = stmt.where(Project.client_id == user.client_id)
    elif client_id:
        stmt = stmt.where(Project.client_id == client_id)
    return list(db.scalars(stmt.order_by(Project.created_at.desc())).all())


@router.get("/{project_id}", response_model=ProjectDetail)
def read_project(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user)
    payload = ProjectDetail.model_validate(project).model_dump()
    if user.role in EXTERNAL_ROLES:
        payload["sold_value"] = None
        payload["financials"] = None
        for field in _EXTERNAL_HIDDEN_FIELDS:
            payload[field] = None
    else:
        payload["financials"] = project_financials(db, project.id)
    return payload


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    # "Administrar projetos" ficou só com Admin/Gerente de Projetos —
    # Consultor não edita projeto mesmo via API direta (ver
    # allow_consultant_write em require_project_access).
    require_project_access(project, user, write=True, allow_consultant_write=False)
    changes = data.model_dump(exclude_unset=True)
    if "manager_id" in changes:
        if not _is_eligible_project_manager(db, db.get(User, changes["manager_id"])):
            raise HTTPException(status_code=422, detail=translate(_MANAGER_ERROR, user.language))
    if changes.get("calendar_id") and not db.get(Calendar, changes["calendar_id"]):
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    if "color" in changes:
        if changes["color"].upper() not in PROJECT_COLOR_HEXES:
            raise HTTPException(status_code=422, detail=translate("Cor do projeto inválida", user.language))
        changes["color"] = changes["color"].upper()
    # Status efetivo/cor efetiva depois desta atualização (change parcial —
    # o que não vier em `changes` continua valendo o que já está salvo).
    effective_status = changes.get("status", project.status)
    effective_color = changes.get("color", project.color)
    was_excluded = project.status in _COLOR_POOL_EXCLUDED_STATUSES
    now_excluded = effective_status in _COLOR_POOL_EXCLUDED_STATUSES
    if not now_excluded and ("color" in changes or (was_excluded and not now_excluded)):
        # Dispara a checagem de exclusividade quando: a cor está mudando, ou
        # o projeto está saindo do grupo finalizado/modelo (reativação) —
        # nesse caso a cor original pode já ter sido tomada por outro
        # projeto enquanto este estava parado.
        _ensure_color_available(db, effective_color, user.language, exclude_project_id=project_id)
    if "status" in changes:
        if effective_status in _STRIPED_STATUSES:
            changes["color_striped"] = True
        elif was_excluded:
            # Reativação (saiu de COMPLETED/CANCELLED/MODELO): volta a
            # mostrar a cor real — já revalidada acima quando aplicável.
            changes["color_striped"] = False
    if user.role in EXTERNAL_ROLES:
        for field in _EXTERNAL_HIDDEN_FIELDS:
            changes.pop(field, None)
    for field, value in changes.items():
        setattr(project, field, value)
    if any(field in changes for field in _FINANCIAL_FIELDS):
        _recompute_sold_value(project)
    audit_details: dict = {"fields": sorted(changes.keys())}
    if changes.get("status_date") and project.status not in _STATUS_SYNC_EXCLUDED:
        # Nova Data de status: o Status gravado das tarefas acompanha a data
        # (Não iniciada → Em andamento/Atrasada etc., ver services.
        # derive_leaf_status). Projeto Modelo/finalizado não é mexido.
        audit_details["task_statuses_synced"] = sync_task_statuses(db, project, changes["status_date"])
    if changes:
        record_audit(db, entity_type="project", entity_id=project.id, action=AuditAction.UPDATE, user_id=user.id, details=audit_details)
    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    """Cobre o caso de um projeto cadastrado por engano: só permite apagar
    enquanto ele ainda não tem nenhuma tarefa (a regra que foi pedida — o
    projeto "recém-criado" típico não tem mais nada além disso). Mas
    Task.project_id não é a única FK que aponta pra cá (todas
    ondelete="CASCADE" — ver app/models.py): Baseline, ProjectExpense,
    Risk, ChangeRequest e Timesheet avulso (sem task_id, só project_id)
    também apontam direto pro projeto e podiam existir mesmo sem nenhuma
    tarefa ainda (ex.: uma despesa ou um risco lançado antes de montar o
    cronograma, ou uma linha de base tirada de um cronograma ainda vazio).
    Sem checar esses também, o DELETE apagaria esse dado em cascata
    silenciosamente — então cada um vira uma mensagem 409 específica em
    vez de só travar em "tem tarefa"."""
    # Sem require_project_access aqui: já é restrito a ADMIN/INTERNAL_PM
    # (require_roles acima), que sempre têm acesso de escrita a qualquer
    # projeto — perfil externo nunca chega neste endpoint.
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    if db.scalar(select(Task).where(Task.project_id == project_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Projeto já tem tarefas cadastradas — não pode ser excluído", user.language),
        )
    if db.scalar(select(Baseline).where(Baseline.project_id == project_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Projeto já tem linha(s) de base salva(s) — não pode ser excluído", user.language),
        )
    if db.scalar(select(ProjectExpense).where(ProjectExpense.project_id == project_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Projeto já tem despesas lançadas — não pode ser excluído", user.language),
        )
    if db.scalar(select(Risk).where(Risk.project_id == project_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Projeto já tem riscos cadastrados — não pode ser excluído", user.language),
        )
    if db.scalar(select(ChangeRequest).where(ChangeRequest.project_id == project_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Projeto já tem solicitações de mudança — não pode ser excluído", user.language),
        )
    if db.scalar(select(Timesheet).where(Timesheet.project_id == project_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Projeto já tem apontamento de horas avulso — não pode ser excluído", user.language),
        )
    record_audit(db, entity_type="project", entity_id=project.id, action=AuditAction.DELETE, user_id=user.id, details={"code": project.code})
    db.delete(project)  # passou por todas as checagens acima — não sobra filho nenhum pra cascata apagar
    db.commit()


# ---------------------------------------------------------------------------
# Recursos do projeto — vínculo direto recurso↔projeto (pedido do usuário:
# "vincular os usuários ao projeto principal" pra não alocar tarefa por
# tarefa em projetos pequenos, conduzidos por 1-2 consultores). Ver
# ProjectResource em app/models.py e a busca em cascata (tarefa → projeto)
# em `_resolve_task_and_project` (app/routers/timesheets.py).
# ---------------------------------------------------------------------------


@router.get("/{project_id}/resources", response_model=list[ProjectResourceRead])
def list_project_resources(project_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ProjectResource]:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user)
    return list(db.scalars(select(ProjectResource).where(ProjectResource.project_id == project_id)).all())


@router.post("/{project_id}/resources", response_model=ProjectResourceRead, status_code=status.HTTP_201_CREATED)
def add_project_resource(
    project_id: str,
    data: ProjectResourceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectResource:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    # Parte de "Administrar projetos" — mesma regra de update_project
    # (Consultor não vincula recurso a projeto, nem via API direta).
    require_project_access(project, user, write=True, allow_consultant_write=False)
    if not db.get(Resource, data.resource_id):
        raise HTTPException(status_code=404, detail=translate("Recurso não encontrado", user.language))
    if db.scalar(select(ProjectResource).where(ProjectResource.project_id == project_id, ProjectResource.resource_id == data.resource_id)):
        raise HTTPException(status_code=409, detail=translate("Recurso já vinculado a este projeto", user.language))
    link = ProjectResource(project_id=project_id, resource_id=data.resource_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.delete("/{project_id}/resources/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_project_resource(
    project_id: str,
    resource_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail=translate("Projeto não encontrado", user.language))
    require_project_access(project, user, write=True, allow_consultant_write=False)
    link = db.scalar(select(ProjectResource).where(ProjectResource.project_id == project_id, ProjectResource.resource_id == resource_id))
    if not link:
        raise HTTPException(status_code=404, detail=translate("Vínculo não encontrado", user.language))
    db.delete(link)
    db.commit()
