from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user, require_roles
from ..i18n import t as translate
from ..models import AuditAction, Client, User, UserRole
from ..schemas import UserCreate, UserPasswordReset, UserRead, UserSelfUpdate, UserUpdate
from ..security import hash_password

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    admin_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    if data.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER} and not data.client_id:
        raise HTTPException(status_code=422, detail=translate("Perfis de cliente exigem client_id", admin_user.language))
    if data.client_id and not db.get(Client, data.client_id):
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", admin_user.language))
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=409, detail=translate("Já existe um usuário com este e-mail", admin_user.language))
    user = User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=data.role,
        client_id=data.client_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.patch("/users/me", response_model=UserRead)
def update_my_language(
    data: UserSelfUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """Autoatendimento de idioma — qualquer usuário logado pode trocar,
    sem depender de um ADMIN editar o cadastro (PATCH /users/{id})."""
    current_user.language = data.language
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/users", response_model=list[UserRead])
def list_users(
    role: UserRole | None = None,
    client_id: str | None = None,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.INTERNAL_PM)),
    db: Session = Depends(get_db),
) -> list[User]:
    """Faltava um jeito de listar usuários — só existia `GET /users/me`. Sem
    isso, uma tela (de gestão de usuários, ou só o seletor de `manager_id`
    ao criar um projeto / `user_id` ao criar um recurso) não tem como
    popular a lista de opções. Restrito a quem já pode criar usuário/recurso
    (ADMIN/INTERNAL_PM)."""
    stmt = select(User)
    if role:
        stmt = stmt.where(User.role == role)
    if client_id:
        stmt = stmt.where(User.client_id == client_id)
    return list(db.scalars(stmt.order_by(User.name)).all())


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    """Edição de usuário — inclui bloquear/desbloquear via `status`
    (UserStatus.BLOCKED impede login em POST /auth/login, ver deps.py e
    routers/auth.py, que já checavam `status != ACTIVE`)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", current_user.language))
    changes = data.model_dump(exclude_unset=True)
    if "role" in changes and changes["role"] in {UserRole.CLIENT_PM, UserRole.CLIENT_USER}:
        effective_client_id = changes.get("client_id", user.client_id)
        if not effective_client_id:
            raise HTTPException(status_code=422, detail=translate("Perfis de cliente exigem client_id", current_user.language))
    if "client_id" in changes and changes["client_id"] and not db.get(Client, changes["client_id"]):
        raise HTTPException(status_code=404, detail=translate("Cliente não encontrado", current_user.language))
    for field, value in changes.items():
        setattr(user, field, value)
    if changes:
        record_audit(db, entity_type="user", entity_id=user.id, action=AuditAction.UPDATE, user_id=current_user.id, details={"fields": sorted(changes.keys())})
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: str,
    data: UserPasswordReset,
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail=translate("Usuário não encontrado", current_user.language))
    user.password_hash = hash_password(data.new_password)
    record_audit(db, entity_type="user", entity_id=user.id, action=AuditAction.UPDATE, user_id=current_user.id, details={"action": "password_reset"})
    db.commit()
    return None
