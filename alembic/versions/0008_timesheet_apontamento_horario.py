"""Fase 2 do apontamento: hora início/fim, intervalo, vínculo com a Agenda
e a flag "avulso" (fora da agenda, exige aprovação extra)

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-27

ALTER TABLE de verdade (como a 0002/0003), não `create_all` — já pode haver
apontamentos em produção. `start_time`/`end_time` ficam NULOS pra não
quebrar linhas antigas (criadas só com `hours_spent`, sem hora nenhuma);
todo apontamento novo, a partir do router, sempre grava os dois.
`break_minutes` e `unscheduled` (boolean) levam `server_default` pra não
quebrar contra uma tabela já populada, igual às colunas NOT NULL das
migrações anteriores.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("timesheets", sa.Column("schedule_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_timesheets_schedule_id_resource_schedules",
        "timesheets",
        "resource_schedules",
        ["schedule_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("timesheets", sa.Column("start_time", sa.Time(), nullable=True))
    op.add_column("timesheets", sa.Column("end_time", sa.Time(), nullable=True))
    op.add_column("timesheets", sa.Column("break_minutes", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("timesheets", sa.Column("unscheduled", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("timesheets", "unscheduled")
    op.drop_column("timesheets", "break_minutes")
    op.drop_column("timesheets", "end_time")
    op.drop_column("timesheets", "start_time")
    op.drop_constraint("fk_timesheets_schedule_id_resource_schedules", "timesheets", type_="foreignkey")
    op.drop_column("timesheets", "schedule_id")
