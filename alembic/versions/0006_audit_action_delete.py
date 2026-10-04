"""Ação de auditoria DELETE

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-25

`DELETE /users/{id}` (exclusão de usuário) precisa registrar em
`audit_logs.action` que o registro foi apagado, mas o tipo Postgres
`auditaction` (nome que o SQLAlchemy gera por create_all: classe
`AuditAction` em minúsculas, sem underscore — mesmo padrão de
`tasktype`/`taskapprovalstatus` na migração 0002) só tinha CREATE/UPDATE
até aqui. Diferente da migração 0005 (enum novo, sem dado dependendo
dele — dava pra dropar e recriar), este tipo já é usado por linhas
existentes em `audit_logs`, então a única forma segura de adicionar um
valor é `ALTER TYPE ... ADD VALUE` (Postgres >= 9.1) — não dropar/recriar.

`ADD VALUE` não pode rodar dentro do bloco de transação que o Alembic
abre por padrão em algumas versões do Postgres < 12; como aqui não
tentamos *usar* o valor novo na mesma migração (só inserido depois, por
código da aplicação), basta commitar a transação da migração antes do
valor ser usado — o que já acontece naturalmente ao terminar
`alembic upgrade head`.

Não existe downgrade de "remover valor de enum" no Postgres (só dá pra
recriar o tipo do zero) — como isso exigiria já não ter nenhuma linha
com action='DELETE', o downgrade aqui é undo simbólico (não faz nada) em
vez de arriscar apagar dado.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'DELETE'"))


def downgrade() -> None:
    # Ver nota acima: remover um valor de enum do Postgres exige recriar o
    # tipo (e só é seguro se nenhuma linha o usa mais) — não implementado
    # aqui de propósito, pra não arriscar apagar audit_logs existentes.
    pass
