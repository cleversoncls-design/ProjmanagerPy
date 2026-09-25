from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .i18n import request_language, t
from .models import Project, User, UserRole, UserStatus
from .security import decode_access_token

INTERNAL_ROLES = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT}
EXTERNAL_ROLES = {UserRole.CLIENT_PM, UserRole.CLIENT_USER}


def get_current_user(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    """Exige `Authorization: Bearer <token>` emitido por POST /auth/login.

    Substitui o antigo adaptador de demonstração baseado no header
    `X-User-Id` (que aceitava qualquer identidade informada pelo cliente,
    sem nenhuma verificação de senha ou assinatura).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("Token de acesso ausente", request_language(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        user_id = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=t("Token inválido ou expirado", request_language(request)),
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(User, user_id)
    if not user or user.status != UserStatus.ACTIVE:
        lang = user.language if user else request_language(request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=t("Usuário inválido ou inativo", lang))
    return user


def require_roles(*roles: UserRole):
    """Fábrica de dependência: só libera a rota para os perfis informados."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("Perfil sem permissão para esta operação", user.language))
        return user

    return dependency


def require_project_access(project: Project, user: User, write: bool = False) -> None:
    """Aplica o isolamento por cliente e a regra de escrita.

    - Perfis internos (ADMIN, INTERNAL_PM, CONSULTANT) enxergam e escrevem em
      qualquer projeto.
    - Perfis externos (CLIENT_PM, CLIENT_USER) só enxergam projetos do
      próprio `client_id`.
    - Dentro do escopo do cliente, CLIENT_PM pode escrever; CLIENT_USER é
      sempre somente leitura.

    (Corrige o bug da versão anterior: a checagem de escrita comparava
    `user.role not in {CLIENT_PM, CLIENT_USER}` sob a guarda `external`, que
    por definição já exige `user.role in {CLIENT_PM, CLIENT_USER}` — as duas
    condições nunca eram verdadeiras ao mesmo tempo, então a restrição de
    escrita nunca era aplicada.)
    """
    if user.role in EXTERNAL_ROLES and project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("Projeto fora do escopo do cliente", user.language))
    if write and user.role == UserRole.CLIENT_USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("Perfil sem permissão de escrita", user.language))
