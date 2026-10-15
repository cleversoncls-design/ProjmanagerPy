from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import record_audit
from ..database import get_db
from ..deps import get_current_user_allow_pending_password
from ..i18n import request_language, t
from ..models import AuditAction, User, UserStatus
from ..schemas import PasswordChange, TokenResponse
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> TokenResponse:
    """Autentica por e-mail (campo `username` do form) + senha e emite um JWT.

    Substitui o header `X-User-Id` (não verificado) que a versão anterior da
    API usava como identidade.
    """
    user = db.scalar(select(User).where(User.email == form_data.username))
    if not user or not verify_password(form_data.password, user.password_hash):
        # Antes de saber quem é (e-mail não encontrado), não há
        # user.language pra consultar — usa o idioma que o frontend manda
        # no header (ver i18n.request_language). Quando o e-mail existe mas
        # a senha está errada, já dá pra usar user.language mesmo.
        lang = user.language if user else request_language(request)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=t("Credenciais inválidas", lang))
    if user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=t("Usuário inativo ou bloqueado", user.language))
    token = create_access_token(user.id, token_version=user.token_version)
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user_allow_pending_password),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Troca da própria senha — qualquer perfil autenticado, inclusive quem
    ainda está com a senha provisória (`must_change_password`).

    Exige a senha atual e uma nova senha diferente dela. Incrementa
    `token_version`: toda sessão aberta com a senha antiga (outros
    navegadores/dispositivos) passa a receber 401. A resposta traz um token
    novo, pra sessão atual seguir sem precisar logar de novo.

    Erro de senha atual é 400 (não 401) de propósito: o frontend descarta o
    token em qualquer 401 fora do login e deslogaria o usuário por um
    simples erro de digitação.
    """
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t("Senha atual incorreta", current_user.language))
    if data.current_password == data.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=t("A nova senha deve ser diferente da senha atual", current_user.language))
    current_user.password_hash = hash_password(data.new_password)
    current_user.must_change_password = False
    current_user.token_version = (current_user.token_version or 0) + 1
    record_audit(db, entity_type="user", entity_id=current_user.id, action=AuditAction.UPDATE, user_id=current_user.id, details={"action": "password_change"})
    db.commit()
    db.refresh(current_user)
    token = create_access_token(current_user.id, token_version=current_user.token_version)
    return TokenResponse(access_token=token, user_id=current_user.id, role=current_user.role)
