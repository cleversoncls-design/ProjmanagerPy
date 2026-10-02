"""Configuração de e-mail (EmailSettings)

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-02

Pedido do usuário: "preciso criar um processo de envio de emails" para
alguns casos (agendas definidas para consultores, aviso de registro de
horas para aprovar, validação de tarefas pelo cliente, status report —
"estes são alguns casos, que vão ser incrementados") e a pergunta "será
necessário criar um configurador de dados para envio de email? para
indicar servidor, usuario, senha, tipos de autentitcação, email de
origem, etc.?". Decisão confirmada com o usuário: sim — uma tela de
Configurações (não variável de ambiente), com autenticação usuário/senha
(sem OAuth2 por enquanto).

Tabela nova, `email_settings`, linha única (a API sempre lê/atualiza a
primeira que existir — ver app/routers/email_settings.py). A senha de
SMTP nunca fica em texto puro (`smtp_password_encrypted`, cifrada com
Fernet — ver app/crypto.py); `last_test_*` guarda o resultado do botão
"Enviar e-mail de teste" da tela, já que este ambiente de desenvolvimento
não tem rede até um servidor SMTP real para validar o envio de verdade.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: Union[str, None] = "0023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

email_security_enum = sa.Enum("NONE", "STARTTLS", "SSL", name="email_security")


def upgrade() -> None:
    bind = op.get_bind()
    email_security_enum.create(bind, checkfirst=True)
    op.create_table(
        "email_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("smtp_host", sa.String(255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("security", email_security_enum, nullable=False, server_default="STARTTLS"),
        sa.Column("smtp_username", sa.String(255), nullable=True),
        sa.Column("smtp_password_encrypted", sa.Text(), nullable=True),
        sa.Column("from_email", sa.String(255), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_ok", sa.Boolean(), nullable=True),
        sa.Column("last_test_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_by_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("email_settings")
    bind = op.get_bind()
    email_security_enum.drop(bind, checkfirst=True)
