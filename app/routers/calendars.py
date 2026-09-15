from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import Calendar, Holiday, User, UserRole
from ..schemas import CalendarCreate, CalendarRead, HolidayCreate, HolidayRead

router = APIRouter(tags=["calendars"])

_MANAGE_ROLES = (UserRole.ADMIN, UserRole.INTERNAL_PM)


@router.post("/calendars", response_model=CalendarRead, status_code=status.HTTP_201_CREATED)
def create_calendar(data: CalendarCreate, _: User = Depends(require_roles(*_MANAGE_ROLES)), db: Session = Depends(get_db)) -> Calendar:
    calendar = Calendar(**data.model_dump())
    db.add(calendar)
    db.commit()
    db.refresh(calendar)
    return calendar


@router.get("/calendars/{calendar_id}", response_model=CalendarRead)
def read_calendar(calendar_id: str, _: User = Depends(require_roles(*_MANAGE_ROLES)), db: Session = Depends(get_db)) -> Calendar:
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
    return calendar


@router.post("/calendars/{calendar_id}/holidays", response_model=HolidayRead, status_code=status.HTTP_201_CREATED)
def add_holiday(
    calendar_id: str,
    data: HolidayCreate,
    _: User = Depends(require_roles(*_MANAGE_ROLES)),
    db: Session = Depends(get_db),
) -> Holiday:
    calendar = db.get(Calendar, calendar_id)
    if not calendar:
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
    if db.scalar(select(Holiday).where(Holiday.calendar_id == calendar_id, Holiday.date == data.date)):
        raise HTTPException(status_code=409, detail="Já existe um feriado cadastrado nesta data para este calendário")
    holiday = Holiday(calendar_id=calendar_id, **data.model_dump())
    db.add(holiday)
    db.commit()
    db.refresh(holiday)
    return holiday


@router.get("/calendars/{calendar_id}/holidays", response_model=list[HolidayRead])
def list_holidays(calendar_id: str, _: User = Depends(require_roles(*_MANAGE_ROLES)), db: Session = Depends(get_db)) -> list[Holiday]:
    if not db.get(Calendar, calendar_id):
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
    return list(db.scalars(select(Holiday).where(Holiday.calendar_id == calendar_id)).all())
