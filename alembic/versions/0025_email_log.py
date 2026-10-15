"""Log de e-mails enviados (EmailLog)

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-03

Pedido do usuário: "poderia criar um botão para abrir uma tela com o log
dos emails enviados? esse log precisa ser gravado em algum arquivo .log
ou na base de dados e que tenha a opção de limpar o log". Decisão: base
de dados (não arquivo) — é o que permite a tela ler/filtrar/limpar sem
precisar de acesso ao servidor, mesmo critério já usado em toda a
funcionalidade de e-mail (ver 0024_email_settings.py).

Tabela nova, `email_logs` — apêndice, sem edição, só leitura (tela) e
DELETE em massa (botão "Limpar log"). `kind` é String simples, não enum:
na migração anterior (0024), o enum `email_security` quebrou em produção
porque um `create_table` tentou recriar um tipo que já existia (ver o
comentário na 0024 e claude/processo-envio-emails.md) — aqui, sem enum,
esse problema não pode se repetir, e novos tipos de aviso (e-mail de
validação pelo cliente, status report — "vão ser incrementados") não
vão precisar de uma migração só para ampliar a lista de valores aceitos.

`has_table` checkfirst de propósito: o `init_db()` do próprio app
(app/database.py) cria qualquer tabela que falte no startup da API a
partir do metadata do SQLAlchemy — foi exatamente isso que fez a
migração 0024 (da tabela email_settings) encontrar "relation already
exists" em produção, já que a API sobe (e roda init_db) antes de alguém
rodar `alembic upgrade head` manualmente. Aqui a migração simplesmente
não tenta recriar o que o init_db já criou, em vez de depender de quem
aplicar isso lembrar de rodar `alembic stamp head` depois.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("email_logs"):
        return
    op.create_table(
        "email_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False, server_default="outro"),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("to_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_email_logs_created_at", "email_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_email_logs_created_at", table_name="email_logs")
    op.drop_table("email_logs")
