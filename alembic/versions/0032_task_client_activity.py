"""Atividade do cliente: flag na tarefa + usuários do cliente alocados

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-08

Pedido do usuário: tarefa executada pelo cliente (sem "Nível mínimo") com
seletor filtrado pelos usuários do cliente do projeto.

- `tasks.is_client_activity` (Boolean, default false) — tarefas existentes
  continuam como estavam.
- `task_client_assignments` (task_id, user_id, único por par) — usuários
  CLIENT_PM/CLIENT_USER do cliente do projeto, sem horas nem custo.

Idempotente (mesmo motivo das migrações 0024-0031): o `init_db()` do app
cria tabelas/colunas que faltem no startup, antes do Alembic.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def _has_table(table: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table)


def upgrade() -> None:
    if not _has_column("tasks", "is_client_activity"):
        op.add_column("tasks", sa.Column("is_client_activity", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _has_table("task_client_assignments"):
        op.create_table(
            "task_client_assignments",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.UniqueConstraint("task_id", "user_id", name="uq_task_client_user"),
        )
        op.create_index("ix_task_client_assignments_task_id", "task_client_assignments", ["task_id"])
        op.create_index("ix_task_client_assignments_user_id", "task_client_assignments", ["user_id"])


def downgrade() -> None:
    if _has_table("task_client_assignments"):
        op.drop_table("task_client_assignments")
    if _has_column("tasks", "is_client_activity"):
        op.drop_column("tasks", "is_client_activity")
