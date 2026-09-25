from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..i18n import request_language, t
from ..models import User, UserStatus
from ..schemas import TokenResponse
from ..security import create_access_token, verify_password

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
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user_id=user.id, role=user.role)
