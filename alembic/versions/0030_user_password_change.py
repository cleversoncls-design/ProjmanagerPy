"""Troca de senha pelo próprio usuário: must_change_password e token_version

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-05

Pedido do usuário: "uma funcionalidade para que o usuário possa modificar a
sua senha de acesso à aplicação". Confirmado com o usuário: disponível pra
todos os perfis, atalho no menu do usuário (Header), exige senha atual +
confirmação, troca obrigatória no 1º acesso (usuário criado ou senha
redefinida pelo ADMIN) e encerramento das outras sessões ao trocar.

Colunas novas em `users`:
- `must_change_password` (Boolean, default false): usuários que já existem
  ficam com false (não são forçados a trocar nada no deploy).
- `token_version` (Integer, default 0): entra no JWT; trocar/redefinir a
  senha incrementa e invalida os tokens anteriores. Tokens já emitidos (sem
  claim "tv") valem como 0, então o deploy não derruba ninguém.

Idempotente (`has_column`) pelo mesmo motivo das migrações 0024-0029: o
`init_db()` do app cria colunas que faltem no startup da API antes de
alguém rodar `alembic upgrade head`.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: Union[str, None] = "0029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("users", "must_change_password"):
        op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _has_column("users", "token_version"):
        op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    if _has_column("users", "token_version"):
        op.drop_column("users", "token_version")
    if _has_column("users", "must_change_password"):
        op.drop_column("users", "must_change_password")
