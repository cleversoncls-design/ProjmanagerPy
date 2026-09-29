"""Vínculo direto recurso-projeto (Recursos do projeto)

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-29

Tabela nova `project_resources` — vincula um recurso diretamente ao
projeto (não só via TaskAssignment em uma tarefa específica), pra
projetos pequenos conduzidos por 1-2 consultores não precisarem de
alocação tarefa por tarefa. Ver `ProjectResource` (app/models.py) e
`_resolve_task_and_project` em app/routers/timesheets.py.

Cria a tabela a partir da própria definição do modelo (mesmo padrão de
0001_initial_schema, que delega a `Base.metadata.create_all`) em vez de
reescrever o DDL à mão — a definição de schema em app/models.py continua
sendo a única fonte da verdade, sem risco de a migração e o modelo
divergirem em tipo/tamanho de coluna.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.models import ProjectResource

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ProjectResource.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ProjectResource.__table__.drop(bind=op.get_bind(), checkfirst=True)
