"""Fase 4: motor de agendamento (duração/trabalho effort-driven, ordem
manual de tarefas), calendário e data de status do projeto

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

Adiciona as colunas que faltavam para: (1) distinguir "Duração" (dias) de
"Trabalho" (horas, campo `estimated_hours` já existente) num modelo
effort-driven — ver `services.apply_effort_driven`; (2) permitir mover uma
tarefa para antes/depois de outra tarefa-irmã sem depender da ordenação
alfabética do WBS (`tasks.sort_order`); (3) atribuir um calendário ao
projeto e gravar a "data de status" que dirige o cálculo de % previsto e o
status (no prazo/atrasada) de cada tarefa (`projects.calendar_id`,
`projects.status_date`).

Segue o mesmo padrão da 0002: ALTER TABLE de verdade (não
`create_all`), com server_default equivalente ao default do lado do
ORM para não quebrar contra uma tabela já populada.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tasks: duração (dias) + ordem manual entre irmãs ------------------
    op.add_column("tasks", sa.Column("duration_days", sa.Numeric(6, 2), nullable=False, server_default="1"))
    op.add_column("tasks", sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"))

    # --- projects: calendário do projeto + data de status -------------------
    op.add_column("projects", sa.Column("calendar_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_projects_calendar_id_calendars",
        "projects",
        "calendars",
        ["calendar_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("projects", sa.Column("status_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "status_date")
    op.drop_constraint("fk_projects_calendar_id_calendars", "projects", type_="foreignkey")
    op.drop_column("projects", "calendar_id")

    op.drop_column("tasks", "sort_order")
    op.drop_column("tasks", "duration_days")
