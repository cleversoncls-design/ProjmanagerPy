"""Cronômetro de atendimento dos tickets

Revision ID: 0036
Revises: 0035
Create Date: 2026-10-09

Sessão de atendimento (Iniciar/Finalizar atendimento) do responsável do
ticket; ao finalizar vira um apontamento de horas. Idempotente (o
`init_db()` cria tabelas novas no startup, antes do Alembic).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: Union[str, None] = "0035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_table("ticket_work_sessions"):
        op.create_table(
            "ticket_work_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("timesheet_id", sa.String(36), sa.ForeignKey("timesheets.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_ticket_work_sessions_ticket_id", "ticket_work_sessions", ["ticket_id"])
        op.create_index("ix_ticket_work_sessions_user_id", "ticket_work_sessions", ["user_id"])


def downgrade() -> None:
    if _has_table("ticket_work_sessions"):
        op.drop_table("ticket_work_sessions")
