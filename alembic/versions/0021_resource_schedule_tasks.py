"""Tarefas vinculadas a um bloco da Agenda (ResourceScheduleTask)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-02

Pedido do usuário: ao montar a Agenda de um consultor num projeto, poder
adicionar uma ou mais tarefas — sem hora própria, só uma lista do que
trabalhar naquele bloco — pra ele ver, ao abrir o agendamento, o que
precisa fazer. Tabela de ligação nova `resource_schedule_tasks`, mesmo
padrão de `project_resources` (migração 0013): puramente um vínculo
(schedule_id, task_id), sem `allocated_hours` (diferente de
`task_assignments`). Ver `ResourceScheduleTask`/`ResourceSchedule.tasks`
em app/models.py.

Cria a tabela a partir da própria definição do modelo (mesmo padrão de
0013_project_resources) em vez de reescrever o DDL à mão.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from app.models import ResourceScheduleTask

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ResourceScheduleTask.__table__.create(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    ResourceScheduleTask.__table__.drop(bind=op.get_bind(), checkfirst=True)
