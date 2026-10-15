"""Cria o primeiro usuário ADMIN, necessário para começar a usar a API depois
da migração para login real (JWT). Sem isso não há como autenticar, já que
POST /users exige um ADMIN autenticado.

Uso (dentro do container ou de um ambiente com as mesmas variáveis de
ambiente do banco configuradas):

    python -m scripts.seed_admin --email admin@empresa.com --name "Admin" --password "senha-forte"

Ou, via Docker Compose, depois de `docker compose up -d`:

    docker compose exec api python -m scripts.seed_admin --email admin@empresa.com --name "Admin" --password "senha-forte"
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.database import get_session_factory, init_db
from app.models import User, UserRole, UserStatus
from app.security import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Cria o primeiro usuário ADMIN do sistema.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    init_db()
    session = get_session_factory()()
    try:
        existing = session.scalar(select(User).where(User.email == args.email))
        if existing:
            print(f"Já existe um usuário com o e-mail {args.email}.", file=sys.stderr)
            return 1
        user = User(
            name=args.name,
            email=args.email,
            password_hash=hash_password(args.password),
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
        )
        session.add(user)
        session.commit()
        print(f"Usuário ADMIN criado: {args.email} (id={user.id})")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
