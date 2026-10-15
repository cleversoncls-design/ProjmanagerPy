"""Convite de calendário por e-mail: opção por consultor e SEQUENCE do .ics

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-05

Integração Agenda de consultores → Google Calendar, no modelo escolhido com o
usuário: convite `.ics` por e-mail (SMTP que já existe), em vez de OAuth com
o Google. Cada consultor liga/desliga pra si (menu do avatar → "Meu Google
Calendar").

Colunas novas:
- `resources.calendar_invite_enabled` (Boolean, default false) — consultores
  existentes ficam desligados; nada muda até cada um ligar.
- `resources.calendar_invite_email` (String 255, nulo) — conta Google quando
  diferente do e-mail de login.
- `resource_schedules.ics_sequence` (Integer, default 0) — SEQUENCE do convite.

Idempotente (`has_column`), mesmo motivo das migrações 0024-0030: o
`init_db()` do app cria colunas que faltem no startup antes do Alembic.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_column("resources", "calendar_invite_enabled"):
        op.add_column("resources", sa.Column("calendar_invite_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    if not _has_column("resources", "calendar_invite_email"):
        op.add_column("resources", sa.Column("calendar_invite_email", sa.String(255), nullable=True))
    if not _has_column("resource_schedules", "ics_sequence"):
        op.add_column("resource_schedules", sa.Column("ics_sequence", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    for table, column in (
        ("resource_schedules", "ics_sequence"),
        ("resources", "calendar_invite_email"),
        ("resources", "calendar_invite_enabled"),
    ):
        if _has_column(table, column):
            op.drop_column(table, column)
