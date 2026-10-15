"""Grupos de Tarefas (TaskGroup/TaskGroupItem)

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-02

Pedido do usuário: um novo cadastro, "agrupador de tarefas" reutilizável —
não um projeto — que pode ser aplicado depois como tarefas-filhas de uma
tarefa de projeto real, pra acelerar a criação de projetos parecidos.
Decisões confirmadas com o usuário: cadastro novo e dedicado (não
reaproveitar Projeto Modelo), hierarquia aninhada (qualquer profundidade,
via `task_group_items.parent_item_id`), gerenciado numa página própria do
menu lateral.

Duas tabelas novas:
- `task_groups`: o cadastro em si (nome/descrição).
- `task_group_items`: os nós da árvore do grupo — mesmos campos de
  estrutura de uma Task (nome, tipo, duração/trabalho, marco, nível mínimo,
  modalidade, observações), sem nenhum campo de execução (ver
  app/models.py). Reaproveita os tipos enum já existentes `tasktype`
  (criado pela migração 0002) e `task_modality` (criado pela 0018) —
  `create_type=False` pra não tentar recriá-los.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_type_enum = sa.Enum("MANAGEMENT", "CONSULTING", name="tasktype", create_type=False)
task_modality_enum = sa.Enum("REMOTE", "ON_SITE", "BOTH", name="task_modality", create_type=False)


def upgrade() -> None:
    op.create_table(
        "task_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "task_group_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("task_groups.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "parent_item_id",
            sa.String(36),
            sa.ForeignKey("task_group_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("task_type", task_type_enum, nullable=False, server_default="CONSULTING"),
        sa.Column("duration_days", sa.Numeric(6, 2), nullable=False, server_default="1"),
        sa.Column("estimated_hours", sa.Numeric(10, 2), nullable=True, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_milestone", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("min_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("modality", task_modality_enum, nullable=False, server_default="BOTH"),
        sa.CheckConstraint("min_level BETWEEN 1 AND 4", name="ck_task_group_item_min_level_range"),
    )
    op.create_index("ix_task_group_items_group_id", "task_group_items", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_task_group_items_group_id", table_name="task_group_items")
    op.drop_table("task_group_items")
    op.drop_table("task_groups")
