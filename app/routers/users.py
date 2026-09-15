from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_roles
from ..models import Client, User, UserRole
from ..schemas import UserCreate, UserRead
from ..security import hash_password

router = APIRouter(tags=["users"])


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    _: User = Depends(require_roles(UserRole.ADMIN)),
    db: Session = Depends(get_db),
) -> User:
    if data.role in {UserRole.CLIENT_PM, UserRole.CLIENT_USER} and not data.client_id:
        raise HTTPException(status_code=422, detail="Perfis de cliente exigem client_id")
    if data.client_id and not db.get(Client, data.client_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=409, detail="Já existe um usuário com este e-mail")
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
