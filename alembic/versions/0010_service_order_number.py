"""Numeração oficial da Ordem de Serviço (Nro. O.S. / Emissão)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-28

Tabela nova `service_order_numbers`: guarda o número sequencial (o próprio
id autoincrement) e a data de emissão de cada Ordem de Serviço, uma linha
por grupo (dia, projeto, consultor) — atribuída sob demanda na primeira vez
que o grupo aparece em GET /reports/service-orders (ver
`_get_or_create_order_number` em app/services.py). A OS em si continua sem
tabela própria (é montada na hora a partir de Timesheet); só o número e a
data de emissão precisam ficar fixos pra sempre.

Segue o mesmo padrão das migrações 0007/0009: delega a definição exata de
colunas pra `Base.metadata`, com `tables=[...]` pra não mexer nas tabelas
já existentes.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.models import Base, ServiceOrderNumber

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind, tables=[ServiceOrderNumber.__table__])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind, tables=[ServiceOrderNumber.__table__])
