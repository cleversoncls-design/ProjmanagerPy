"""Status Report por período (ProjectStatusReport)

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-03

Pedido do usuário: "pode implementar os 2 modelos e colocar na opção de
relatórios" — depois de validar os mockups visuais "Interno" (diretoria e
gerências) e "Cliente" (gerente de projeto do cliente) no canvas de
design. Decisão confirmada com o usuário: cada status report é um registro
SALVO por período (não calculado na hora) — "fechamento" congelado, como
uma Baseline, pra permitir reabrir relatórios antigos depois. Ver docstring
de `ProjectStatusReport` em app/models.py para o detalhe de cada campo.

`rag_*` usam `String(12)` simples, NÃO um enum do Postgres — decisão
direta da lição aprendida com o bug do enum `email_security` na migração
0024 (ver comentário lá e em `claude/processo-envio-emails.md`): um
`create_table` com múltiplas colunas usando o MESMO tipo enum nomeado
corre risco real de tentar recriar o tipo mais de uma vez na mesma
transação. Com 5 colunas RAG nesta tabela, `String` elimina esse risco de
vez — mesmo critério já usado em `EmailLog.kind`.

`has_table` checkfirst de propósito — mesmo motivo já documentado nas
migrações 0024/0025: o `init_db()` do próprio app (app/database.py) cria
qualquer tabela que falte no startup da API a partir do metadata do
SQLAlchemy, antes de alguém rodar `alembic upgrade head` manualmente.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026"
down_revision: Union[str, None] = "0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("project_status_reports"):
        return
    op.create_table(
        "project_status_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("prepared_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("rag_schedule", sa.String(12), nullable=False),
        sa.Column("rag_cost", sa.String(12), nullable=False),
        sa.Column("rag_margin", sa.String(12), nullable=False),
        sa.Column("rag_scope", sa.String(12), nullable=False),
        sa.Column("rag_risk", sa.String(12), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("next_steps_client", sa.Text(), nullable=False),
        sa.Column("next_steps_internal", sa.Text(), nullable=True),
        sa.Column("schedule_actual_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("schedule_planned_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("hours_consumed", sa.Numeric(10, 2), nullable=True),
        sa.Column("hours_budgeted", sa.Numeric(10, 2), nullable=True),
        sa.Column("cost_planned", sa.Numeric(14, 2), nullable=True),
        sa.Column("cost_actual", sa.Numeric(14, 2), nullable=True),
        sa.Column("margin_planned_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("margin_actual_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("tasks_done", sa.JSON(), nullable=False),
        sa.Column("tasks_next", sa.JSON(), nullable=False),
        sa.Column("risks_snapshot", sa.JSON(), nullable=False),
        sa.Column("burndown", sa.JSON(), nullable=False),
    )
    op.create_index("ix_project_status_reports_project_id", "project_status_reports", ["project_id"])
    op.create_index("ix_project_status_reports_created_at", "project_status_reports", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_project_status_reports_created_at", table_name="project_status_reports")
    op.drop_index("ix_project_status_reports_project_id", table_name="project_status_reports")
    op.drop_table("project_status_reports")
