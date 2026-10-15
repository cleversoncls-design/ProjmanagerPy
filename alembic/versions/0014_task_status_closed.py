"""Status CLOSED (tarefa cerrada/desativada)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-01

Novo valor `CLOSED` no enum Postgres `taskstatus` (mesmo padrão das
migrações 0006/0011: `ALTER TYPE ... ADD VALUE`, porque o tipo já é usado
por linhas existentes em `tasks.status`, então dropar/recriar não é opção
segura). "Ativar/Desativar tarefa" (pedido do usuário) passa a significar
alternar entre CLOSED e o status normal da tarefa — ver
TASK_FINISHED_STATUSES em app/models.py e o botão correspondente em
ProjectDetailPage.jsx.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TYPE taskstatus ADD VALUE IF NOT EXISTS 'CLOSED'"))


def downgrade() -> None:
    # Ver nota da migração 0006/0011: remover um valor de enum do Postgres
    # exige recriar o tipo, só seguro se nenhuma linha o usa mais — não
    # implementado aqui de propósito, pra não arriscar apagar/alterar
    # tarefas existentes com status CLOSED.
    pass
