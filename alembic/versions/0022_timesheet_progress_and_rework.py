"""% de Avanço da Tarefa + classificador Normal/Retrabalho no apontamento

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-02

Pedido do usuário, tela de "Apontamento de horas":
1. Campo "% de Avanço da Tarefa" — reporta (e espelha em
   Task.progress_percentage) o avanço da tarefa no momento do apontamento.
2. Classificador Normal/Retrabalho quando o apontamento é numa tarefa do
   projeto; quando Retrabalho, exige ao menos um motivo de uma lista fixa
   (ReworkReason, guardada como JSON em `rework_reasons` — mesmo padrão de
   `resource_schedules.working_days`, migração 0016).

Três colunas novas em `timesheets`, todas opcionais (só fazem sentido
quando task_id está setado — ver _validate_rework em
app/routers/timesheets.py). Ver WorkClassification/ReworkReason em
app/models.py.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

work_classification_enum = sa.Enum("NORMAL", "REWORK", name="work_classification")


def upgrade() -> None:
    bind = op.get_bind()
    work_classification_enum.create(bind, checkfirst=True)
    op.add_column("timesheets", sa.Column("task_progress_percentage", sa.Numeric(5, 2), nullable=True))
    op.add_column("timesheets", sa.Column("work_classification", work_classification_enum, nullable=True))
    op.add_column("timesheets", sa.Column("rework_reasons", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("timesheets", "rework_reasons")
    op.drop_column("timesheets", "work_classification")
    op.drop_column("timesheets", "task_progress_percentage")
    bind = op.get_bind()
    work_classification_enum.drop(bind, checkfirst=True)
