"""Ausência da empresa no apontamento (Timesheet.absence_type)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-02

Pedido do usuário: controlar ausências da empresa (Férias/Licença Médica/
Licença Maternidade/Ausência/Folga) nos apontamentos de hora dos recursos.
Decisão confirmada: classificar igual ao "Traslado" (Timesheet.is_transit,
migração 0016), só que invertido — Traslado é sempre COM projeto (custo do
cliente), ausência é sempre SEM projeto nem tarefa (custo interno da
empresa). Por isso `absence_type` é só uma coluna nova opcional em
`timesheets`, nunca uma entidade/projeto/cliente novo (ver análise completa
em app/models.py, classe AbsenceType, e _resolve_task_and_project em
app/routers/timesheets.py).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

absence_type_enum = sa.Enum(
    "VACATION", "MEDICAL_LEAVE", "MATERNITY_LEAVE", "ABSENCE", "DAY_OFF", name="absence_type"
)


def upgrade() -> None:
    bind = op.get_bind()
    absence_type_enum.create(bind, checkfirst=True)
    op.add_column("timesheets", sa.Column("absence_type", absence_type_enum, nullable=True))


def downgrade() -> None:
    op.drop_column("timesheets", "absence_type")
    bind = op.get_bind()
    absence_type_enum.drop(bind, checkfirst=True)
