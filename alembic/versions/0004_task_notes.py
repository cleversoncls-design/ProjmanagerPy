"""Campo de observações (notas livres) na tarefa

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24

Item 16 do pedido de revisão da tela de tarefas ("Campo de Observações")
que tinha ficado de fora da migração 0003 — texto livre, sem uso em
nenhum cálculo do motor de agendamento.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "notes")
