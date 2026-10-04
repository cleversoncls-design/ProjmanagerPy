from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES_DEFAULT = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))


def _secret_key() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY não definido. Gere um valor aleatório forte "
            "(ex.: `openssl rand -hex 32`) e defina-o no .env antes de subir a API."
        )
    return secret


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes or JWT_EXPIRE_MINUTES_DEFAULT)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, _secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> str:
    """Retorna o `sub` (user_id) do token. Levanta jwt.PyJWTError se inválido/expirado."""
    payload = jwt.decode(token, _secret_key(), algorithms=[JWT_ALGORITHM])
    return payload["sub"]
