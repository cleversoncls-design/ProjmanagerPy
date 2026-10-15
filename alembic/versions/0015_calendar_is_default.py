"""Calendário padrão (feriados na Agenda)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-01

Novo campo `calendars.is_default` (boolean, default false). A Agenda não é
de um projeto só — pode mostrar agendamentos de vários projetos/recursos
no mesmo mês, cada um com seu próprio Calendário — então, em vez de
resolver múltiplos calendários por mês visível, um único calendário
marcado como padrão é usado para mostrar feriados como indisponíveis pra
todo mundo na tela de Agenda (pedido do usuário). Ver
`_set_as_default` em app/routers/calendars.py.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "calendars",
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("calendars", "is_default")
