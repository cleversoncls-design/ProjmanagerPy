from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import EXTERNAL_ROLES, get_current_user, require_roles
from ..i18n import t as translate
from ..models import Client, User, UserRole
from ..schemas import ClientCreate, ClientRead

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    # "Administrar clientes" ficou só com o Administrador (revisão de
    # acessos do usuário) — Gerente de Projetos perdeu esse item do menu,
    # então também não pode mais criar cliente por aqui, mesmo direto pela
    # API. Continua enxergando a lista (GET abaixo, INTERNAL_ROLES) — só
    # precisa dela pra escolher o cliente ao criar/editar projeto.
    user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> Client:
    if db.scalar(select(Client).where(Client.code == data.code)):
        raise HTTPException(status_code=409, detail=translate("Já existe um cliente com este código", user.language))
    client = Client(**data.model_dump())
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("", response_model=list[ClientRead])
def list_clients(
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT)),
    db: Session = Depends(get_db),
) -> list[Client]:
    return list(db.scalars(select(Client).order_by(Client.legal_name)).all())


@router.get("/{client_id}", response_model=ClientRead)
def read_client(client_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", user.language))
    if user.role in EXTERNAL_ROLES and client.id != user.client_id:
        raise HTTPException(status_code=403, detail=translate("Fora do escopo do cliente", user.language))
    return client
