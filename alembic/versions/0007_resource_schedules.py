"""Agenda de consultores (ResourceSchedule) + cor do projeto

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-25

Fase 1 do pedido "Rotina para agendamento de recurso": uma tabela nova
(`resource_schedules`) guarda blocos de horário (recurso + projeto + data +
hora início/fim + descrição) — independente de `task_assignments`, que só
marca alocação sem horário nenhum. A tela "Agenda de consultores" lê/escreve
aqui.

Também adiciona `projects.color`: a cor de cada agendamento é fixa por
projeto (decisão tomada com o usuário), então o campo mora no projeto, não
na agenda — todo agendamento de um projeto herda a mesma cor
automaticamente. Usa uma das 8 chaves da paleta categórica já validada do
app ("series-1".."series-8", ver --series-* em frontend/src/index.css),
não uma cor livre — mesmo espírito de "escolher de uma paleta" que foi
pedido, só que aplicado no cadastro do projeto em vez de em cada
agendamento.

Segue o mesmo espírito da migração 0001 (delegar a definição exata de
colunas/tipos para `Base.metadata`, a mesma fonte que os testes já
exercitam) para a tabela nova — mas com `tables=[...]` para não tentar
recriar (nem falhar tentando) as ~15 tabelas que já existem.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.models import Base, ResourceSchedule

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    op.add_column("projects", sa.Column("color", sa.String(length=20), nullable=False, server_default="series-1"))
    Base.metadata.create_all(bind, tables=[ResourceSchedule.__table__])


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind, tables=[ResourceSchedule.__table__])
    op.drop_column("projects", "color")
