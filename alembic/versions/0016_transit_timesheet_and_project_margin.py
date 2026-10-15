"""Apontamento de Traslado e % de margem vendida no projeto

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-01

Pedido do usuário ("mais novas melhorias, parte 3"):

- `timesheets.is_transit` (boolean, default false) — marca um apontamento
  de "Traslado" (deslocamento), sempre vinculado a um projeto mas sem
  tarefa específica (mesmo "formato" do apontamento avulso já existente,
  só que com rótulo e categoria de relatório próprios — ver
  `_resolve_task_and_project` em app/routers/timesheets.py e
  `financials_by_task_type`/`service_orders` em app/services.py).
- `projects.margin_percentage` (numeric 5,2, opcional) — "% de Margem
  vendida" digitada diretamente no cadastro do Projeto (seção "Pacote
  vendido"), um dado declarado na venda/proposta — não é calculado a
  partir de custo nenhum (decisão confirmada com o usuário).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "timesheets",
        sa.Column("is_transit", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "projects",
        sa.Column("margin_percentage", sa.Numeric(5, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "margin_percentage")
    op.drop_column("timesheets", "is_transit")
