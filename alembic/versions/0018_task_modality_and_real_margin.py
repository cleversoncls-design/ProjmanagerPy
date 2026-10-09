"""Modalidade da tarefa (Remoto/Presencial/Ambos)

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-01

Pedido do usuário ("melhorias, parte 5"):

- `tasks.modality` (enum: REMOTE/ON_SITE/BOTH — "Remotamente"/"Presencial"/
  "Ambos"), obrigatório, default BOTH. Puramente informativo — não
  restringe alocação de recurso nem bloqueia nada no backend (mesmo
  espírito do `tasks.min_level` da parte 4, que só filtra o seletor no
  frontend).

Os outros dois itens da "parte 5" não precisam de migração:
- O bug do campo "% Margem vendida" não aceitar 2 casas decimais era só o
  atributo `step` do input HTML no frontend (o backend já aceitava,
  `Numeric(5,2)`).
- "% Margem Planejada"/"% Margem Real" no Financeiro do projeto são
  calculados em cima de colunas que já existem (`projects.margin_percentage`
  da parte 3 + `project_financials()` em app/services.py) — nenhuma coluna
  nova.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_modality_enum = sa.Enum("REMOTE", "ON_SITE", "BOTH", name="task_modality")


def upgrade() -> None:
    bind = op.get_bind()
    task_modality_enum.create(bind, checkfirst=True)
    op.add_column("tasks", sa.Column("modality", task_modality_enum, nullable=False, server_default="BOTH"))


def downgrade() -> None:
    op.drop_column("tasks", "modality")
    bind = op.get_bind()
    task_modality_enum.drop(bind, checkfirst=True)
