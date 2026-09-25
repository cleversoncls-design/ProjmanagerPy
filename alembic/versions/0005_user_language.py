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
    # `checkfirst=True` só confere se já existe um tipo com esse NOME — não
    # se os valores batem com o que esta migração espera. Se sobrou um tipo
    # "language" órfão no banco (ex.: uma tentativa anterior desta mesma
    # migração que criou o tipo mas não chegou a adicionar a coluna, ou
    # qualquer outra coisa com esse nome), o CREATE TYPE é pulado e o
    # ALTER TABLE seguinte quebra tentando usar 'pt-BR'/'es' num tipo que
    # não tem esses valores. Recria do zero em vez de confiar no nome:
    # ainda não existe nenhuma coluna usando esse tipo neste banco (é a
    # primeira vez que "language" é adicionado), então dropar é seguro — se
    # por algum motivo já houver algo dependendo dele, o DROP falha alto e
    # claro em vez de corromper dado.
    bind.execute(sa.text("DROP TYPE IF EXISTS language"))
    language_enum.create(bind)
    op.add_column(
        "users",
        sa.Column("language", language_enum, nullable=False, server_default="pt-BR"),
    )


def downgrade() -> None:
    op.drop_column("users", "language")
    bind = op.get_bind()
    language_enum.drop(bind, checkfirst=True)
