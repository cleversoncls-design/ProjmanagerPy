"""Schema inicial

Revision ID: 0001
Revises:
Create Date: 2026-09-15

Esta é a migração-base do projeto: em vez de reescrever à mão o DDL de cada
uma das ~15 tabelas (arriscado sem um banco real disponível para validar
coluna a coluna), upgrade/downgrade delegam para
`Base.metadata.create_all`/`drop_all`, a mesma definição de schema que
`app/models.py` já usa e que a suíte de testes já exercita.

Isso é seguro tanto para instalações novas quanto para bancos que já
existiam antes do Alembic (criados pelo `init_db()` automático da API):
`create_all` só cria tabelas que ainda não existem (`checkfirst=True` é o
padrão), então rodar `alembic upgrade head` num banco já populado apenas
registra a versão em `alembic_version`, sem tentar recriar nada.

A partir desta migração, qualquer alteração de schema deve ganhar uma nova
revisão Alembic (`alembic revision --autogenerate -m "..."`) em vez de
depender do `create_all` para "alcançar" mudanças em colunas/tabelas já
existentes — `create_all` nunca altera uma tabela que já existe.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.models import Base

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
