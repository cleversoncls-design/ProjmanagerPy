"""Conhecimento: vínculo de perfil e Necessário/Desejável também no Sistema/Módulo

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-04

Pedido do usuário, olhando a tela de Cadastro de Funcionalidades pronta:
"a obrigatoriedade que hoje está para consultor e gerente de projetos,
gostaria de configurar no sistema/módulo, incluindo se é necessário ou
desejável.. manter pela funcionalidade a mesma regra". Perguntado e
confirmado com o usuário (2 perguntas): os dois campos (vínculo de perfil
Consultor/Gerente de Projetos + Necessário/Desejável) passam a existir
também no Sistema e no Módulo, mas só como classificação/organização —
NADA muda no comportamento de hoje: GET /knowledge/my-catalog continua
filtrando só pelo `applies_to_consultant`/`applies_to_internal_pm` do
MÓDULO (não do Sistema), e o badge "Necessário/Desejável" mostrado na
autoavaliação/revisão continua vindo só de
`KnowledgeFunctionality.requirement` (não do Sistema/Módulo). Ver
docstrings de KnowledgeSystem/KnowledgeModule em app/models.py.

Colunas novas:
- `knowledge_systems.applies_to_consultant`/`applies_to_internal_pm`
  (Boolean, default true) + CheckConstraint "pelo menos um perfil" —
  Sistema não tinha nenhum vínculo de perfil até agora.
- `knowledge_systems.requirement` (String, default "REQUIRED") — Sistema
  não tinha Necessário/Desejável até agora.
- `knowledge_modules.requirement` (String, default "REQUIRED") — Módulo
  já tinha o vínculo de perfil (migração 0028); só faltava o
  Necessário/Desejável.

`server_default` em todas pra não quebrar linhas já existentes em
produção (nascem com o valor default, editável depois por quem cadastra).
`has_column`/`get_check_constraints` checkfirst de propósito — mesmo
motivo já documentado nas migrações 0024-0028: o `init_db()` do próprio
app (app/database.py) cria qualquer tabela/coluna que falte no startup da
API a partir do metadata do SQLAlchemy, antes de alguém rodar
`alembic upgrade head` manualmente.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0029"
down_revision: Union[str, None] = "0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    system_columns = {c["name"] for c in inspector.get_columns("knowledge_systems")}
    if "applies_to_consultant" not in system_columns:
        op.add_column("knowledge_systems", sa.Column("applies_to_consultant", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "applies_to_internal_pm" not in system_columns:
        op.add_column("knowledge_systems", sa.Column("applies_to_internal_pm", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "requirement" not in system_columns:
        op.add_column("knowledge_systems", sa.Column("requirement", sa.String(12), nullable=False, server_default="REQUIRED"))

    system_constraints = {c["name"] for c in inspector.get_check_constraints("knowledge_systems")}
    if "ck_knowledge_system_has_profile" not in system_constraints:
        op.create_check_constraint(
            "ck_knowledge_system_has_profile", "knowledge_systems", "applies_to_consultant OR applies_to_internal_pm"
        )

    module_columns = {c["name"] for c in inspector.get_columns("knowledge_modules")}
    if "requirement" not in module_columns:
        op.add_column("knowledge_modules", sa.Column("requirement", sa.String(12), nullable=False, server_default="REQUIRED"))


def downgrade() -> None:
    op.drop_column("knowledge_modules", "requirement")
    op.drop_constraint("ck_knowledge_system_has_profile", "knowledge_systems", type_="check")
    op.drop_column("knowledge_systems", "requirement")
    op.drop_column("knowledge_systems", "applies_to_internal_pm")
    op.drop_column("knowledge_systems", "applies_to_consultant")
