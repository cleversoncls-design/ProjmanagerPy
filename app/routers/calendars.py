from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..i18n import t as translate
from ..models import Calendar, Holiday, User, UserRole
from ..schemas import CalendarCreate, CalendarRead, CalendarUpdate, HolidayCreate, HolidayRead, HolidayUpdate

router = APIRouter(tags=["calendars"])

_MANAGE_ROLES = (UserRole.ADMIN, UserRole.INTERNAL_PM)


def _set_as_default(db: Session, calendar: Calendar) -> None:
    """Só um calendário pode ser o padrão (usado pra mostrar feriados na
    Agenda, que não é de um projeto só — ver Calendar.is_default em
    models.py). Desliga qualquer outro que já estivesse marcado antes de
    ligar este, numa única instrução (sem round-trip extra por calendário)."""
    db.execute(update(Calendar).where(Calendar.id != calendar.id).values(is_default=False))
    calendar.is_default = True


@router.post("/calendars", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
def create_calendar(data: CalendarCreate, _: User = Depends(require_roles(*_MANAGE_ROLES)), db: Session = Depends(get_db)) -> Calendar:
    payload = data.model_dump()
    make_default = payload.pop("is_default")
    calendar = Calendar(**payload)
    db.add(calendar)
    if make_default:
        db.flush()
        _set_as_default(db, calendar)
    db.commit()
    db.refresh(calendar)
    return calendar


@router.get("/calendars", response_model=list[CalendarRead])
def list_calendars(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Calendar]:
    """Só existia leitura por `calendar_id` — sem listagem, um formulário
    não tem como oferecer os calendários já cadastrados como opção
    (precisaria que o usuário soubesse o id de cor). Aberta pra qualquer
    perfil autenticado (não só ADMIN/INTERNAL_PM) desde que a Agenda
    passou a mostrar os feriados do calendário padrão pra todo mundo —
    criar/editar calendário continua restrito a _MANAGE_ROLES."""
    return list(db.scalars(select(Calendar).order_by(Calendar.name)).all())


@router.get("/calendars/{calendar_id}", response_model=CalendarRead)
def read_calendar(calendar_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Calendar:
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    return calendar


@router.patch("/calendars/{calendar_id}", response_model=CalendarRead)
def update_calendar(
    calendar_id: str,
    data: CalendarUpdate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> Calendar:
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    changes = data.model_dump(exclude_unset=True)
    make_default = changes.pop("is_default", None)
    for field, value in changes.items():
        setattr(calendar, field, value)
    if make_default is True:
        _set_as_default(db, calendar)
    elif make_default is False:
        # Só desliga o próprio — não promove nenhum outro a padrão no lugar
        # dele (ficar sem calendário padrão é um estado válido: a Agenda
        # simplesmente não mostra feriado nenhum até alguém marcar outro).
        calendar.is_default = False
    db.commit()
    db.refresh(calendar)
    return calendar


@router.post("/calendars/{calendar_id}/holidays", response_model=HolidayRead, status_code=status.HTTP_201_CREATED)
def add_holiday(
    calendar_id: str,
    data: HolidayCreate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> Holiday:
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    if db.scalar(select(Holiday).where(Holiday.calendar_id == calendar_id, Holiday.date == data.date)):
        raise HTTPException(status_code=409, detail=translate("Já existe um feriado cadastrado nesta data para este calendário", user.language))
    holiday = Holiday(calendar_id=calendar_id, **data.model_dump())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.get("/calendars/{calendar_id}/holidays", response_model=list[HolidayRead])
def list_holidays(calendar_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Holiday]:
    """Leitura aberta a qualquer perfil autenticado (ver list_calendars) —
    consultores/clientes precisam ver os feriados na própria Agenda;
    cadastrar/editar/excluir feriado continua em _MANAGE_ROLES abaixo."""
    if not db.get(Calendar, calendar_id):
        raise HTTPException(status_code=404, detail=translate("Calendário não encontrado", user.language))
    return list(db.scalars(select(Holiday).where(Holiday.calendar_id == calendar_id)).all())


def _get_holiday_or_404(db: Session, calendar_id: str, holiday_id: str, lang: str) -> Holiday:
    holiday = db.get(Holiday, holiday_id)
    if not holiday or holiday.calendar_id != calendar_id:
        raise HTTPException(status_code=404, detail=translate("Feriado não encontrado", lang))
    return holiday


@router.patch("/calendars/{calendar_id}/holidays/{holiday_id}", response_model=HolidayRead)
def update_holiday(
    calendar_id: str,
    holiday_id: str,
    data: HolidayUpdate,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> Holiday:
    holiday = _get_holiday_or_404(db, calendar_id, holiday_id, user.language)
    if data.date != holiday.date and db.scalar(
        select(Holiday).where(Holiday.calendar_id == calendar_id, Holiday.date == data.date, Holiday.id != holiday_id)
    ):
        raise HTTPException(status_code=409, detail=translate("Já existe um feriado cadastrado nesta data para este calendário", user.language))
    holiday.date = data.date
    holiday.description = data.description
    db.commit()
    db.refresh(holiday)
    return holiday


@router.delete("/calendars/{calendar_id}/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holiday(
    calendar_id: str,
    holiday_id: str,
    user: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    holiday = _get_holiday_or_404(db, calendar_id, holiday_id, user.language)
    db.delete(holiday)
    db.commit()
