from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import INTERNAL_ROLES, MANAGEMENT_ROLES, get_current_user, require_roles
from ..email_service import get_email_settings
from ..i18n import t as translate
from ..models import Calendar, Resource, User
from ..notifications import send_calendar_invite_test
from ..schemas import CalendarInviteSettingsRead, CalendarInviteSettingsUpdate, ResourceCreate, ResourceRead, ResourceUpdate, ResourceUtilizationRow
from ..services import resource_utilization

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    data: ResourceCreate,
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
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
    _: User = Depends(require_roles(*INTERNAL_ROLES)),
    db: Session = Depends(get_db),
) -> list[Resource]:
    """Só existia leitura por `resource_id`; sem listagem não dá para montar
    uma tela de equipe/recursos nem checar se um usuário já tem um recurso
    cadastrado (o que `POST /resources` já impede, mas o frontend precisa
    saber com antecedência para não deixar o formulário falhar com 409)."""
    stmt = select(Resource)
    if user_id:
        stmt = stmt.where(Resource.user_id == user_id)
    return list(db.scalars(stmt.order_by(Resource.function, Resource.level)).all())


@router.get("/utilization", response_model=list[ResourceUtilizationRow])
def utilization(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    resource_id: str | None = None,
    user: User = Depends(require_roles(*INTERNAL_ROLES)),
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


def _own_resource(user: User) -> Resource:
    resource = user.resource
    if not resource:
        raise HTTPException(status_code=404, detail=translate("Usuário sem recurso vinculado", user.language))
    return resource


def _invite_settings_read(db: Session, user: User, resource: Resource) -> CalendarInviteSettingsRead:
    email_settings = get_email_settings(db)
    return CalendarInviteSettingsRead(
        enabled=resource.calendar_invite_enabled,
        email=resource.calendar_invite_email,
        default_email=user.email,
        email_service_ready=bool(email_settings and email_settings.enabled),
    )


@router.get("/me/calendar-invite", response_model=CalendarInviteSettingsRead)
def read_my_calendar_invite(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CalendarInviteSettingsRead:
    """Autoatendimento (menu do avatar → "Meu Google Calendar"): o próprio
    consultor vê/liga/desliga o convite de calendário dos SEUS agendamentos.
    404 pra quem não tem recurso vinculado — a tela esconde o item."""
    return _invite_settings_read(db, user, _own_resource(user))


@router.put("/me/calendar-invite", response_model=CalendarInviteSettingsRead)
def update_my_calendar_invite(
    data: CalendarInviteSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CalendarInviteSettingsRead:
    resource = _own_resource(user)
    resource.calendar_invite_enabled = data.enabled
    # Vazio ou igual ao e-mail de login = sem endereço próprio (usa o de login).
    resource.calendar_invite_email = data.email if data.email and data.email.lower() != user.email.lower() else None
    db.commit()
    db.refresh(resource)
    return _invite_settings_read(db, user, resource)


@router.post("/me/calendar-invite/test", status_code=status.HTTP_204_NO_CONTENT)
def send_my_calendar_invite_test(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> None:
    """Manda um convite de teste (amanhã 09:00) pro endereço configurado,
    pra conferir se o Google aceita os convites do remetente do sistema."""
    resource = _own_resource(user)
    ok, error = send_calendar_invite_test(db, resource, user)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error or translate("Não foi possível enviar o convite de teste", user.language),
        )


@router.get("/{resource_id}", response_model=ResourceRead)
def read_resource(
    resource_id: str,
    user: User = Depends(require_roles(*INTERNAL_ROLES)),
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
    user: User = Depends(require_roles(*MANAGEMENT_ROLES)),
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
