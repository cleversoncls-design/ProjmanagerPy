from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    """`EMAIL_CREDENTIALS_ENCRYPTION_KEY` é uma chave separada da
    `JWT_SECRET_KEY` (mesmo critério já planejado para os tokens OAuth do
    Google Calendar, ver claude/integracao-google-calendar-agenda-
    consultores.md) — a senha de SMTP salva em `EmailSettings.
    smtp_password_encrypted` fica criptografada em repouso no banco, nunca
    em texto puro. Gerar com:

        python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    """
    key = os.getenv("EMAIL_CREDENTIALS_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "EMAIL_CREDENTIALS_ENCRYPTION_KEY não definido. Gere um valor com "
            '`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` '
            "e defina-o no .env antes de salvar a configuração de e-mail."
        )
    return Fernet(key.encode("utf-8"))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    """Levanta RuntimeError se a chave mudou desde que o valor foi salvo
    (InvalidToken) — erro claro em vez de um traceback cru de `cryptography`
    no meio do envio de um e-mail."""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError(
            "Não foi possível decifrar a senha de e-mail salva — "
            "EMAIL_CREDENTIALS_ENCRYPTION_KEY pode ter mudado desde que ela foi gravada."
        ) from exc
