"""Consumo anterior (sistema legado) + tipo de projeto

Revision ID: 0033
Revises: 0032
Create Date: 2026-10-08

Pedido do usuário:
- apontar horas já consumidas, a um custo médio, em projetos vindos do sistema
  anterior, como custo já apropriado → tabela `project_legacy_consumption`
  (vários lançamentos por projeto: data, horas, custo médio/hora, descrição);
- classificador de "tipos de projeto" (lista fixa) → `projects.project_type`
  (String(30), nulo nos projetos existentes).

Idempotente (mesmo motivo das migrações 0024-0032): o `init_db()` do app cria
tabelas que faltem no startup, antes do Alembic; a coluna nova em `projects`,
porém, só chega via esta migração.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_column("projects", "project_type"):
        op.add_column("projects", sa.Column("project_type", sa.String(30), nullable=True))
    if not _has_table("project_legacy_consumption"):
        op.create_table(
            "project_legacy_consumption",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
            sa.Column("reference_date", sa.Date(), nullable=False),
            sa.Column("hours", sa.Numeric(10, 2), nullable=False),
            sa.Column("cost_per_hour", sa.Numeric(12, 2), nullable=False),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )
        op.create_index("ix_project_legacy_consumption_project_id", "project_legacy_consumption", ["project_id"])


def downgrade() -> None:
    if _has_table("project_legacy_consumption"):
        op.drop_table("project_legacy_consumption")
    if _has_column("projects", "project_type"):
        op.drop_column("projects", "project_type")
