from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import Resource, User, UserRole
from ..schemas import ResourceCreate, ResourceRead

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("", response_model=ResourceRead, status_code=status.HTTP_201_CREATED)
def create_resource(
    data: ResourceCreate,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> Resource:
    target_user = db.get(User, data.user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if db.scalar(select(Resource).where(Resource.user_id == data.user_id)):
        raise HTTPException(status_code=409, detail="Este usuário já possui um recurso cadastrado")
    resource = Resource(**data.model_dump())
    db.add(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.get("/{resource_id}", response_model=ResourceRead)
def read_resource(
    resource_id: str,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)),
    db: Session = Depends(get_db),
) -> Resource:
    resource = db.get(Resource, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return resource
