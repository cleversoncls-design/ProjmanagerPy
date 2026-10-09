"""Tickets internos (pendentes): tickets, interações e apontamento vinculado

Revision ID: 0034
Revises: 0033
Create Date: 2026-10-09

Pedido do usuário: controle de pendentes/tickets por projeto e tarefa — o
consultor abre, o gerente direciona, as interações ficam gravadas no histórico
e o tempo gasto vira apontamento de horas na tarefa.

- `tickets` (número TK-AAAA-NNNN = year + seq, projeto, tarefa, criticidade,
  status, solicitante, responsável, datas);
- `ticket_interactions` (linha do tempo: comentário, status, direcionamento,
  criticidade, tempo apontado);
- `timesheets.ticket_id` (FK opcional, SET NULL) — coluna nova em tabela
  existente, só chega via esta migração.

Idempotente (mesmo motivo das migrações 0024-0033): o `init_db()` cria as
tabelas novas no startup, antes do Alembic.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: Union[str, None] = "0033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_table("tickets"):
        op.create_table(
            "tickets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("code", sa.String(20), nullable=False),
            sa.Column("year", sa.Integer(), nullable=False),
            sa.Column("seq", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("criticality", sa.String(10), nullable=False),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("requester_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assignee_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("year", "seq", name="uq_ticket_year_seq"),
        )
        op.create_index("ix_tickets_code", "tickets", ["code"], unique=True)
        op.create_index("ix_tickets_project_id", "tickets", ["project_id"])
        op.create_index("ix_tickets_task_id", "tickets", ["task_id"])
        op.create_index("ix_tickets_status", "tickets", ["status"])
        op.create_index("ix_tickets_requester_id", "tickets", ["requester_id"])
        op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"])
    if not _has_table("ticket_interactions"):
        op.create_table(
            "ticket_interactions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("author_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("from_value", sa.String(255), nullable=True),
            sa.Column("to_value", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ticket_interactions_ticket_id", "ticket_interactions", ["ticket_id"])
    if not _has_column("timesheets", "ticket_id"):
        op.add_column(
            "timesheets",
            sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True),
        )
        op.create_index("ix_timesheets_ticket_id", "timesheets", ["ticket_id"])


def downgrade() -> None:
    if _has_column("timesheets", "ticket_id"):
        op.drop_index("ix_timesheets_ticket_id", table_name="timesheets")
        op.drop_column("timesheets", "ticket_id")
    if _has_table("ticket_interactions"):
        op.drop_table("ticket_interactions")
    if _has_table("tickets"):
        op.drop_table("tickets")
