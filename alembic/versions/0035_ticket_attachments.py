"""Anexos dos tickets internos

Revision ID: 0035
Revises: 0034
Create Date: 2026-10-09

Segunda entrega dos tickets: arquivos anexados (print, log, planilha...) à
abertura ou a uma interação do ticket. O arquivo fica em disco (volume do
Docker); aqui só os metadados. Idempotente (o `init_db()` cria tabelas novas
no startup, antes do Alembic).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: Union[str, None] = "0034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_table("ticket_attachments"):
        op.create_table(
            "ticket_attachments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("ticket_id", sa.String(36), sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
            sa.Column("interaction_id", sa.String(36), sa.ForeignKey("ticket_interactions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("stored_name", sa.String(80), nullable=False),
            sa.Column("content_type", sa.String(100), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("uploaded_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])
        op.create_index("ix_ticket_attachments_interaction_id", "ticket_attachments", ["interaction_id"])


def downgrade() -> None:
    if _has_table("ticket_attachments"):
        op.drop_table("ticket_attachments")
