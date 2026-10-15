"""Convite de calendário ligado por padrão

Revision ID: 0037
Revises: 0036
Create Date: 2026-10-09

O convite `.ics` da Agenda de consultores nascia DESLIGADO (0031): o
consultor precisava ligar "Meu Google Calendar" para receber, e quem não
ligou nunca recebia o convite. Agora vale para todos por padrão (continua
dando para desligar em "Meu Google Calendar"):

- o padrão da coluna passa a ser verdadeiro;
- consultores que já existiam (todos com a coluna falsa, porque ela nunca
  foi ligada) passam a verdadeiro. Quem tinha desligado de propósito precisa
  desligar de novo.

Só vale para agendamentos novos ou alterados daqui em diante.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: Union[str, None] = "0036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("resources") as batch:
        batch.alter_column(
            "calendar_invite_enabled",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.true(),
        )
    op.execute(sa.text("UPDATE resources SET calendar_invite_enabled = :on WHERE calendar_invite_enabled = :off").bindparams(on=True, off=False))


def downgrade() -> None:
    with op.batch_alter_table("resources") as batch:
        batch.alter_column(
            "calendar_invite_enabled",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            server_default=sa.false(),
        )
