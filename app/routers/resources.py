from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..i18n import t as translate
from ..models import Calendar, Resource, TaskAssignment, Timesheet, User, UserRole
from ..schemas import ResourceCreate, ResourceRead, ResourceUpdate, ResourceUtilizationRow
from ..services import resource_utilization

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    data: ResourceCreate,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> Resource:
    target_user = db.get(User, data.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", user.language))
    if db.scalar(select(Resource).where(Resource.user_id == data.user_id)):
        raise HTTPException(status_code=409, detail=translate("Este usuário já possui um recurso cadastrado", user.language))
    if data.calendar_id and not db.get(Calendar, data.calendar_id):
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    resource = Resource(**data.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("", response_model=list[ResourceRead])
def list_resources(
    user_id: str | None = None,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)),
    db: Session = Depends(get_db),
) -> list[Resource]:
    """Só existia leitura por `resource_id`; sem listagem não dá para montar
    uma tela de equipe/recursos nem checar se um usuário já tem um recurso
    cadastrado (o que `POST /resources` já impede, mas o frontend precisa
    saber com antecedência para não deixar o formulário falhar com 409)."""
    stmt = select(Resource)
    if user_id:
        stmt = stmt.where(Resource.user_id == user_id)
    return list(db.scalars(stmt.order_by(Resource.role_title)).all())


@router.get("/utilization", response_model=list[ResourceUtilizationRow])
def utilization(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    resource_id: str | None = None,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Workload/capacidade × demanda por recurso — sem `start`/`end`, usa o
    mês corrente. Restrito a perfis internos, no mesmo padrão de GET
    /resources/{id} (dado sensível de custo/capacidade da equipe).

    Precisa vir ANTES de "/{resource_id}" nesta mesma rota: como as duas
    convivem sob o prefixo "/resources" e o FastAPI casa rotas na ordem em
    que foram declaradas, "/{resource_id}" (path param) casaria primeiro com
    "/resources/utilization" — tratando "utilization" como um resource_id e
    devolvendo 404. Esta rota já existiu em reports.py sem esse problema
    (routers diferentes, mas resources.router era incluído antes de
    reports.router em app/main.py), então movida pra cá junto com o path
    param que ela precisa evitar."""
    today = date.today()
    period_start = start or today.replace(day=1)
    if end:
        period_end = end
    else:
        next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        period_end = next_month - timedelta(days=1)
    if period_start > period_end:
        raise HTTPException(status_code=422, detail=translate("start precisa ser anterior ou igual a end", user.language))
    return resource_utilization(db, start=period_start, end=period_end, resource_id=resource_id)


@router.get("/{resource_id}", response_model=ResourceRead)
def read_resource(
    resource_id: str,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)),
    db: Session = Depends(get_db),
) -> Resource:
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail=translate("Recurso não encontrado", user.language))
    return resource


@router.patch("/{resource_id}", response_model=ResourceRead)
def update_resource(
    resource_id: str,
    data: ResourceUpdate,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> Resource:
    """Corrige o cadastro de um recurso já vinculado (função/custo interno/
    valor de faturamento/capacidade diária/calendário pessoal) — antes só
    dava pra definir esses campos na hora de vincular (POST /resources);
    não havia como ajustar depois sem apagar e recriar o vínculo."""
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail=translate("Recurso não encontrado", user.language))
    changes = data.model_dump(exclude_unset=True)
    if "calendar_id" in changes and changes["calendar_id"] and not db.get(Calendar, changes["calendar_id"]):
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    for field, value in changes.items():
        setattr(resource, field, value)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(
    resource_id: str,
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> None:
    """Só permite apagar um recurso que nunca foi alocado em nenhuma tarefa
    nem tem apontamento de horas registrado. As duas FKs que apontam pra cá
    (TaskAssignment.resource_id, Timesheet.resource_id) são
    ondelete="CASCADE" — sem esta checagem, apagar o recurso apagaria
    silenciosamente alocações em tarefas e horas já lançadas (inclusive de
    projetos fechados), então a checagem vem antes do DELETE em vez de
    confiar só na constraint do banco."""
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail=translate("Recurso não encontrado", user.language))
    # O recurso do Administrador nunca pode ser excluído por aqui — regra de
    # negócio própria, além (não em vez) da checagem de alocação abaixo. O
    # frontend já esconde o botão pra esse caso; checa de novo aqui porque
    # uma regra de negócio nunca deve depender só do que a tela esconde.
    owner = db.get(User, resource.user_id)
    if owner and owner.role == UserRole.ADMIN:
        raise HTTPException(status_code=409, detail=translate("O recurso do Administrador não pode ser excluído", user.language))
    if db.scalar(select(TaskAssignment).where(TaskAssignment.resource_id == resource_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Recurso está alocado em uma ou mais tarefas — remova as alocações antes de excluir", user.language),
        )
    if db.scalar(select(Timesheet).where(Timesheet.resource_id == resource_id)):
        raise HTTPException(
            status_code=409,
            detail=translate("Recurso tem apontamento de horas em projetos/tarefas — não pode ser excluído", user.language),
        )
    db.delete(resource)
    db.commit()
