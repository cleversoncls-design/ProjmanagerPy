from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_roles
from ..models import Calendar, Resource, User, UserRole
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
    if data.calendar_id and not db.get(Calendar, data.calendar_id):
        raise HTTPException(status_code=404, detail="Calendário não encontrado")
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
