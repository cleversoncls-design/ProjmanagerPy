"""Perfis Gerente de Serviços e Diretor Geral

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-01

Dois novos valores no enum Postgres `userrole` (mesmo padrão das migrações
0006/0011/0014: `ALTER TYPE ... ADD VALUE`, porque o tipo já é usado por
linhas existentes em `users.role`, então dropar/recriar não é opção
segura). Pedido do usuário: "Gerente de Serviços" e "Diretor Geral" têm
acessos equivalentes ao Administrador, exceto cadastrar/editar/excluir
usuário (que continua exclusivo de ADMIN) — ver ADMIN_LIKE_ROLES/
MANAGEMENT_ROLES/INTERNAL_ROLES em app/deps.py.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SERVICE_MANAGER'"))
    bind.execute(sa.text("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'GENERAL_DIRECTOR'"))


def downgrade() -> None:
    # Ver nota da migração 0006/0011/0014: remover um valor de enum do
    # Postgres exige recriar o tipo, só seguro se nenhuma linha o usa mais —
    # não implementado aqui de propósito, pra não arriscar apagar/alterar
    # usuários existentes com um destes dois perfis.
    pass
