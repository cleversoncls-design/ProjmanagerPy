"""Status de projeto MODELO

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-29

Novo valor `MODELO` no enum Postgres `projectstatus` (mesmo padrão da
migração 0006: `ALTER TYPE ... ADD VALUE`, porque o tipo já é usado por
linhas existentes em `projects.status`, então dropar/recriar não é opção
segura). Projeto com esse status é só uma base de estrutura pro botão
"Copiar estrutura de outro projeto" (ver `copy_tasks_from` em
app/routers/projects.py) — nunca entra em indicador/dashboard (ver
`_scoped_projects`/`roi()` em app/routers/reports.py).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'MODELO'"))


def downgrade() -> None:
    # Ver nota da migração 0006: remover um valor de enum do Postgres exige
    # recriar o tipo, só seguro se nenhuma linha o usa mais — não
    # implementado aqui de propósito, pra não arriscar apagar/alterar
    # projetos existentes com status MODELO.
    pass
