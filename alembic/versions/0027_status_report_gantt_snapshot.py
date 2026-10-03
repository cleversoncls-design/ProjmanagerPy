"""Status Report: gantt_snapshot (Gantt nível 1+2, congelado)

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-03

Pedido do usuário, com 2 prints da EAP recolhida manualmente até o 2º
nível (depois de um round anterior equivocado, que tinha implementado isso
como um botão avulso na aba Gantt de Projetos): "imprima uma imagem do
GANTT considerando as informações até o segundo nível de tarefas pai e
filhas, em forma recolhida [...] é para imprimir o gantt até o segundo
nível no status report [...] na impressão do status tanto interna como
para o cliente". Confirmado com o usuário: o Gantt deve ser CONGELADO
junto com o resto do "fechamento" (igual custo/margem/burndown já são),
não recalculado ao vivo cada vez que o relatório é reaberto — ver
docstring de `ProjectStatusReport`/`gantt_snapshot` em app/models.py e
services._build_gantt_level2_snapshot.

Nullable: relatórios criados ANTES desta funcionalidade (a tabela já
existe em produção desde a migração 0026) ficam com `gantt_snapshot = NULL`
— o frontend mostra uma mensagem no lugar do desenho pra esses, em vez de
tentar recalcular algo que nunca foi congelado.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {c["name"] for c in sa.inspect(bind).get_columns("project_status_reports")}
    if "gantt_snapshot" in columns:
        return
    op.add_column("project_status_reports", sa.Column("gantt_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_status_reports", "gantt_snapshot")
