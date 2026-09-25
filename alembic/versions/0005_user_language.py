"""Idioma do usuário (pt-BR/es)

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-25

Suporte a troca de idioma da interface (Português/Espanhol) — a
preferência fica vinculada ao cadastro do usuário (não ao navegador), pra
seguir a pessoa entre dispositivos. Mesmo padrão de enum novo da migração
0002: nome do tipo igual ao que SQLAlchemy usaria via create_all (nome da
classe Python em minúsculas), server_default equivalente ao default do
model pra não quebrar contra uma tabela já populada.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

language_enum = sa.Enum("pt-BR", "es", name="language")


def upgrade() -> None:
    bind = op.get_bind()
    language_enum.create(bind, checkfirst=True)
    op.add_column(
        "users",
        sa.Column("language", language_enum, nullable=False, server_default="pt-BR"),
    )


def downgrade() -> None:
    op.drop_column("users", "language")
    bind = op.get_bind()
    language_enum.drop(bind, checkfirst=True)
