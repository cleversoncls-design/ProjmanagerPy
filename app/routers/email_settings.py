from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..crypto import encrypt_secret
from ..database import get_db
from ..deps import ADMIN_LIKE_ROLES, require_roles
from ..email_service import get_email_settings, send_raw_email
from ..i18n import t as translate
from ..models import EmailSecurity, EmailSettings, User
from ..schemas import EmailSettingsRead, EmailSettingsUpdate, EmailTestRequest

# Pedido do usuário: "será necessário criar um configurador de dados para
# envio de email? para indicar servidor, usuario, senha, tipos de
# autentitcação, email de origem, etc." — confirmado: tela de
# Configurações (não variável de ambiente), ADMIN_LIKE_ROLES (mesmo
# critério de quem administra Usuários/Clientes — dado sensível, credencial
# de SMTP de verdade).
router = APIRouter(prefix="/email-settings", tags=["email-settings"])


def _settings_to_read(settings: EmailSettings | None) -> EmailSettingsRead:
    if settings is None:
        return EmailSettingsRead(
            enabled=False,
            smtp_host="",
            smtp_port=587,
            security=EmailSecurity.STARTTLS,
            smtp_username=None,
            password_configured=False,
            from_email="",
            from_name=None,
            last_test_at=None,
            last_test_ok=None,
            last_test_error=None,
            updated_at=None,
        )
    return EmailSettingsRead(
        id=settings.id,
        enabled=settings.enabled,
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        security=settings.security,
        smtp_username=settings.smtp_username,
        password_configured=bool(settings.smtp_password_encrypted),
        from_email=settings.from_email,
        from_name=settings.from_name,
        last_test_at=settings.last_test_at,
        last_test_ok=settings.last_test_ok,
        last_test_error=settings.last_test_error,
        updated_at=settings.updated_at,
    )


@router.get("", response_model=EmailSettingsRead)
def read_email_settings(
    _: User = Depends(require_roles(*ADMIN_LIKE_ROLES)),
    db: Session = Depends(get_db),
) -> EmailSettingsRead:
    return _settings_to_read(get_email_settings(db))


@router.put("", response_model=EmailSettingsRead)
def update_email_settings(
    data: EmailSettingsUpdate,
    user: User = Depends(require_roles(*ADMIN_LIKE_ROLES)),
    db: Session = Depends(get_db),
) -> EmailSettingsRead:
    settings = get_email_settings(db)
    if settings is None:
        settings = EmailSettings(smtp_host=data.smtp_host, from_email=data.from_email)
        db.add(settings)
    settings.enabled = data.enabled
    settings.smtp_host = data.smtp_host
    settings.smtp_port = data.smtp_port
    settings.security = data.security
    settings.smtp_username = data.smtp_username
    settings.from_email = data.from_email
    settings.from_name = data.from_name
    # Senha: omitida (None) mantém a já salva; "" explícito apaga (ver
    # docstring de EmailSettingsUpdate).
    if data.smtp_password:
        settings.smtp_password_encrypted = encrypt_secret(data.smtp_password)
    elif data.smtp_password == "":
        settings.smtp_password_encrypted = None
    settings.updated_by_id = user.id
    db.commit()
    db.refresh(settings)
    return _settings_to_read(settings)


@router.post("/test-email", response_model=EmailSettingsRead)
def send_test_email(
    data: EmailTestRequest,
    user: User = Depends(require_roles(*ADMIN_LIKE_ROLES)),
    db: Session = Depends(get_db),
) -> EmailSettingsRead:
    """Manda um e-mail de teste pros dados JÁ SALVOS (pedido implícito pela
    limitação conhecida: o ambiente onde este código é desenvolvido não
    tem rede até um servidor SMTP de verdade — ver docstring de
    EmailSettings em app/models.py — então validar que a configuração
    funciona só é possível no servidor real do usuário). Usa
    `send_raw_email` (ignora `enabled`) — dá pra testar antes de marcar a
    configuração como Ativa."""
    settings = get_email_settings(db)
    if not settings:
        raise HTTPException(status_code=422, detail=translate("Configuração de e-mail ainda não foi salva", user.language))
    ok, error = send_raw_email(
        settings,
        to_email=data.to_email,
        to_name=None,
        subject=translate("E-mail de teste — ProjmanagerPy", user.language),
        html_body=f"<p>{translate('Este é um e-mail de teste da configuração de SMTP do ProjmanagerPy.', user.language)}</p>",
    )
    settings.last_test_at = datetime.now(timezone.utc)
    settings.last_test_ok = ok
    settings.last_test_error = error
    db.commit()
    db.refresh(settings)
    return _settings_to_read(settings)
