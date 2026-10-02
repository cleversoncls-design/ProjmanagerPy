from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .database import get_db
from .i18n import request_language, t
from .models import Project, User, UserRole, UserStatus
from .security import decode_access_token

# Gerente de Serviços/Diretor Geral (pedido do usuário) têm acessos
# equivalentes ao Administrador, exceto cadastrar/editar/excluir usuário
# (ver routers/users.py: create_user/update_user/delete_user/
# reset_user_password continuam exclusivos de UserRole.ADMIN, de propósito,
# NUNCA destes dois conjuntos abaixo) — por isso entram em INTERNAL_ROLES
# (perfil interno, sem isolamento por cliente) e em MANAGEMENT_ROLES/
# ADMIN_LIKE_ROLES (todo `require_roles`/checagem que hoje já é
# ADMIN+INTERNAL_PM ou só ADMIN, menos as quatro exceções citadas acima).
INTERNAL_ROLES = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.CONSULTANT, UserRole.SERVICE_MANAGER, UserRole.GENERAL_DIRECTOR}
EXTERNAL_ROLES = {UserRole.CLIENT_PM, UserRole.CLIENT_USER}
MANAGEMENT_ROLES = {UserRole.ADMIN, UserRole.INTERNAL_PM, UserRole.SERVICE_MANAGER, UserRole.GENERAL_DIRECTOR}
ADMIN_LIKE_ROLES = {UserRole.ADMIN, UserRole.SERVICE_MANAGER, UserRole.GENERAL_DIRECTOR}


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


def require_project_access(project: Project, user: User, write: bool = False, allow_consultant_write: bool = True) -> None:
    """Aplica o isolamento por cliente e a regra de escrita.

    - Perfis internos (ADMIN, INTERNAL_PM, CONSULTANT) enxergam qualquer
      projeto; escrevem também, exceto onde `allow_consultant_write=False`
      tira o Consultor (ver abaixo).
    - Perfis externos (CLIENT_PM, CLIENT_USER) só enxergam projetos do
      próprio `client_id`, e dentro desse escopo são SEMPRE somente
      leitura — ver nota da reorganização de menus logo abaixo.

    (Corrige o bug da versão anterior: a checagem de escrita comparava
    `user.role not in {CLIENT_PM, CLIENT_USER}` sob a guarda `external`, que
    por definição já exige `user.role in {CLIENT_PM, CLIENT_USER}` — as duas
    condições nunca eram verdadeiras ao mesmo tempo, então a restrição de
    escrita nunca era aplicada.)

    Reorganização de menus (pedido do usuário): PM do Cliente deixou de
    poder escrever — antes só CLIENT_USER era bloqueado aqui, CLIENT_PM
    tinha escrita dentro do próprio escopo de cliente. Confirmado com o
    usuário: os dois perfis externos (EXTERNAL_ROLES) agora são sempre
    somente leitura em qualquer rota que passe por esta função, mesmo
    chamando a API direto (sem passar pela UI, que já escondia os botões de
    edição pros dois). Isso inclui `POST /tasks/{id}/submit-for-approval`
    (que antes citava CLIENT_PM como exceção) — a validação do cliente
    continua funcionando normalmente porque `PATCH /tasks/{id}/client-
    approval` chama esta função com `write=False` (ver routers/tasks.py).

    `allow_consultant_write=False` (revisão de acessos do usuário:
    "Administrar projetos"/"Administrar tarefas" ficaram só com
    Administrador/Gerente de Projetos — Consultor não tem mais essa tela)
    bloqueia especificamente o Consultor nas rotas de administração de
    projeto/tarefa/risco/mudança/linha-base/despesa, mesmo que ele chame a
    API direto (sem passar pela UI, que já esconde essas telas dele). O
    default (True) preserva o comportamento de sempre, usado por rotas
    onde o Consultor tem escrita legítima (ex.: Registro de Horas, que
    reaproveita esta função só pra checar escopo de cliente/projeto ativo,
    não pra "administrar" o projeto em si)."""
    if user.role in EXTERNAL_ROLES and project.client_id != user.client_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("Projeto fora do escopo do cliente", user.language))
    if write and user.role in EXTERNAL_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("Perfil sem permissão de escrita", user.language))
    if write and not allow_consultant_write and user.role == UserRole.CONSULTANT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=t("Perfil sem permissão de escrita", user.language))
