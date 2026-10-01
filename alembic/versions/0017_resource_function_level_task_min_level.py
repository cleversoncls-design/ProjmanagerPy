"""Função/Nível do recurso e Nível mínimo da tarefa

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-01

Pedido do usuário ("melhorias, parte 4"):

- `resources.role_title` (texto livre) é SUBSTITUÍDO por dois campos
  estruturados e independentes — decisão confirmada com o usuário (dois
  campos, em vez de uma lista única com as 8 combinações literais que ele
  sugeriu, ex.: "Consultor Pleno - Nível 2"):
    - `resources.function` (enum: CONSULTANT/DEVELOPER/SPECIALIST/
      PROJECT_MANAGER — "Consultor"/"Desenvolvedor"/"Especialista"/
      "Gerente de Projetos"), opcional.
    - `resources.level` (inteiro 1 a 4, senioridade), opcional. Inteiro
      simples (não enum) de propósito: permite comparação >= direta no
      filtro de "Nível mínimo" da tarefa.
  Nenhuma migração automática do texto livre existente (decisão
  confirmada) — os dois campos novos nascem vazios pra todo mundo; cada
  recurso recebe a Função/Nível corretos quando alguém editar o cadastro
  dele. O texto livre antigo é perdido (não há como mapear com segurança
  pra uma das 4 categorias a partir de texto arbitrário).
- `tasks.min_level` (inteiro 1 a 4, obrigatório, default 1) — "Nível
  mínimo" exigido pra executar a tarefa; usado só como FILTRO no seletor
  de "Recurso" da alocação (Recursos Alocados) no frontend — não bloqueia
  nada no backend (decisão confirmada). Obrigatório porque o usuário pediu
  explicitamente; default 1 ("qualquer nível serve") pra não exigir
  preenchimento manual em tarefas que já existem nem travar a criação de
  tarefas novas que não se importam com nível.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

resource_function_enum = sa.Enum("CONSULTANT", "DEVELOPER", "SPECIALIST", "PROJECT_MANAGER", name="resource_function")


def upgrade() -> None:
    bind = op.get_bind()

    resource_function_enum.create(bind, checkfirst=True)
    op.add_column("resources", sa.Column("function", resource_function_enum, nullable=True))
    op.add_column("resources", sa.Column("level", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_resource_level_range",
        "resources",
        "level IS NULL OR level BETWEEN 1 AND 4",
    )
    op.drop_column("resources", "role_title")

    op.add_column("tasks", sa.Column("min_level", sa.Integer(), nullable=False, server_default="1"))
    op.create_check_constraint(
        "ck_task_min_level_range",
        "tasks",
        "min_level BETWEEN 1 AND 4",
    )


def downgrade() -> None:
    op.drop_constraint("ck_task_min_level_range", "tasks", type_="check")
    op.drop_column("tasks", "min_level")

    # O texto livre original não é recuperável — volta com um valor
    # provisório que precisa ser corrigido manualmente após o downgrade.
    op.add_column("resources", sa.Column("role_title", sa.String(length=120), nullable=False, server_default="A definir"))
    op.drop_constraint("ck_resource_level_range", "resources", type_="check")
    op.drop_column("resources", "level")
    op.drop_column("resources", "function")

    bind = op.get_bind()
    resource_function_enum.drop(bind, checkfirst=True)
