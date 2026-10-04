from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import ADMIN_LIKE_ROLES, EXTERNAL_ROLES, INTERNAL_ROLES, get_current_user, require_roles
from ..i18n import t as translate
from ..models import AuditAction, Client, Project, ProjectIntake, User
from ..schemas import ClientCreate, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    data: ClientCreate,
    # "Administrar clientes" ficou só com ADMIN_LIKE_ROLES (revisão de
    # acessos do usuário) — Gerente de Projetos não tem esse item do menu,
    # então também não pode criar cliente por aqui, mesmo direto pela API.
    # Gerente de Serviços/Diretor Geral entram aqui (acesso equivalente ao
    # Administrador). Continua enxergando a lista (GET abaixo,
    # INTERNAL_ROLES) — só precisa dela pra escolher o cliente ao criar/
    # editar projeto.
    user: User = Depends(require_roles(*ADMIN_LIKE_ROLES)),
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
    _: User = Depends(require_roles(*INTERNAL_ROLES)),
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


@router.patch("/{client_id}", response_model=ClientRead)
def update_client(
    client_id: str,
    data: ClientUpdate,
    # Mesma restrição de create_client acima — ADMIN_LIKE_ROLES edita
    # cadastro de clientes (pedido do usuário, "mais melhorias": "O cadastro
    # de clientes não permite modificar dados").
    user: User = Depends(require_roles(*ADMIN_LIKE_ROLES)),
    db: Session = Depends(get_db),
) -> Client:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", user.language))
    changes = data.model_dump(exclude_unset=True)
    if "code" in changes and changes["code"] != client.code:
        if db.scalar(select(Client).where(Client.code == changes["code"], Client.id != client_id)):
            raise HTTPException(status_code=409, detail=translate("Já existe um cliente com este código", user.language))
    for field, value in changes.items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: str,
    # Mesma restrição de create_client/update_client — ADMIN_LIKE_ROLES
    # exclui cliente (pedido do usuário, "mais novas melhorias, parte 3":
    # "ter botão de excluir, validando se o mesmo não está vinculado a
    # nenhuma tabela").
    user: User = Depends(require_roles(*ADMIN_LIKE_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    client = db.get(Client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", user.language))
    # Project.client_id é RESTRICT (ver app/models.py) — o banco já
    # recusaria sozinho, mas a checagem aqui dá uma mensagem 409 traduzida
    # em vez de estourar um IntegrityError genérico pro usuário.
    if db.scalar(select(Project.id).where(Project.client_id == client_id)):
        raise HTTPException(status_code=409, detail=translate("Cliente tem projeto(s) vinculado(s) — não pode ser excluído", user.language))
    # User.client_id é SET NULL (não bloquearia no banco), mas o pedido do
    # usuário foi validar QUALQUER vínculo antes de excluir — um usuário
    # (PM do cliente/Usuário-chave) ligado a este cliente também bloqueia.
    if db.scalar(select(User.id).where(User.client_id == client_id)):
        raise HTTPException(status_code=409, detail=translate("Cliente tem usuário(s) vinculado(s) — não pode ser excluído", user.language))
    # ProjectIntake.client_id é CASCADE e NOT NULL — sem esta checagem, uma
    # solicitação de projeto já registrada pro cliente seria apagada em
    # silêncio junto com ele.
    if db.scalar(select(ProjectIntake.id).where(ProjectIntake.client_id == client_id)):
        raise HTTPException(status_code=409, detail=translate("Cliente tem solicitação(ões) de projeto vinculada(s) — não pode ser excluído", user.language))
    record_audit(db, entity_type="client", entity_id=client.id, action=AuditAction.DELETE, user_id=user.id, details={"code": client.code, "legal_name": client.legal_name})
    db.delete(client)
    db.commit()
