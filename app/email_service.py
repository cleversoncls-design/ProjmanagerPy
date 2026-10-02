"""Envio de e-mail via SMTP, usando a configuração salva em
`EmailSettings` (pedido do usuário: "será necessário criar um
configurador de dados para envio de email?").

Regra inegociável, mesmo critério já usado na integração com Google
Calendar (ver claude/integracao-google-calendar-agenda-consultores.md):
uma falha ao enviar e-mail NUNCA pode impedir a operação principal que
disparou o aviso (criar um agendamento, aprovar um apontamento, etc.) —
`send_email` nunca levanta exceção, só devolve `(ok, erro)`.
"""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from sqlalchemy import select
from sqlalchemy.orm import Session

from .crypto import decrypt_secret
from .models import EmailSecurity, EmailSettings

logger = logging.getLogger("app.email")


def get_email_settings(db: Session) -> EmailSettings | None:
    """Linha única (ver docstring de EmailSettings em app/models.py) —
    sempre a primeira (e única) que existir, ou None se a tela de
    Configurações nunca foi salva ainda."""
    return db.scalar(select(EmailSettings).limit(1))


def send_raw_email(
    settings: EmailSettings,
    *,
    to_email: str,
    to_name: str | None,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> tuple[bool, str | None]:
    """Conecta no SMTP configurado e manda o e-mail, SEM checar
    `settings.enabled` — usado pelo botão "Enviar e-mail de teste" (ver
    app/routers/email_settings.py), que precisa poder validar as
    credenciais mesmo antes de o admin marcar a configuração como Ativa.
    Todo disparo "de negócio" (agendamento, aprovação) passa por
    `send_email` abaixo, que checa `enabled` primeiro."""
    try:
        password = decrypt_secret(settings.smtp_password_encrypted) if settings.smtp_password_encrypted else None

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = formataddr((settings.from_name or "", settings.from_email))
        message["To"] = formataddr((to_name or "", to_email))
        if text_body:
            message.attach(MIMEText(text_body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))

        if settings.security == EmailSecurity.SSL:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
        try:
            if settings.security == EmailSecurity.STARTTLS:
                server.starttls()
            if settings.smtp_username and password:
                server.login(settings.smtp_username, password)
            server.sendmail(settings.from_email, [to_email], message.as_string())
        finally:
            server.quit()
        return True, None
    except Exception as exc:  # pragma: no cover - depende de um servidor SMTP real
        logger.exception("Falha ao enviar e-mail para %s", to_email)
        return False, str(exc)


def send_email(
    db: Session,
    *,
    to_email: str,
    to_name: str | None,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> tuple[bool, str | None]:
    """Manda um e-mail "de negócio" usando a configuração salva em
    `EmailSettings`. Retorna `(ok, erro)` — nunca levanta exceção (ver
    docstring do módulo). `(False, None)` significa "não há o que fazer"
    (envio desligado ou nunca configurado), bem diferente de `(False,
    "<erro>")` (configurado, mas a tentativa de envio falhou de verdade —
    problema de rede/credencial/servidor)."""
    settings = get_email_settings(db)
    if not settings or not settings.enabled:
        return False, None
    return send_raw_email(settings, to_email=to_email, to_name=to_name, subject=subject, html_body=html_body, text_body=text_body)
