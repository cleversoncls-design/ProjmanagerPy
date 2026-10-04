"""Fase 1: tipo de tarefa, split financeiro do projeto, calendário do
recurso, apontamento avulso e aprovação de tarefa pelo cliente

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-23

Ao contrário da migração 0001 (que delega para Base.metadata.create_all,
seguro por ser uma baseline num banco vazio), esta migração faz ALTER
TABLE de verdade, porque já pode haver dados em produção. Cada coluna nova
NOT NULL leva um server_default equivalente ao default do lado do
Python/ORM em app/models.py, para não quebrar ao rodar contra uma tabela
já populada.

Os dois enums novos (TaskType, TaskApprovalStatus) são criados
explicitamente com nome igual ao que SQLAlchemy usaria automaticamente
via create_all (nome da classe Python em minúsculas) — isso só tem efeito
real em PostgreSQL (tipo ENUM nativo); em SQLite, `Enum.create()`/`.drop()`
são no-ops (lá o tipo vira VARCHAR + CHECK, inline na própria coluna).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

task_type_enum = sa.Enum("MANAGEMENT", "CONSULTING", name="tasktype")
task_approval_status_enum = sa.Enum("NOT_REQUIRED", "PENDING", "APPROVED", "REJECTED", name="taskapprovalstatus")


def upgrade() -> None:
    bind = op.get_bind()

    # --- tasks: tipo (gestão/consultoria) + aprovação do cliente ---------
    task_type_enum.create(bind, checkfirst=True)
    task_approval_status_enum.create(bind, checkfirst=True)
    op.add_column(
        "tasks",
        sa.Column("task_type", task_type_enum, nullable=False, server_default="CONSULTING"),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "client_approval_status",
            task_approval_status_enum,
            nullable=False,
            server_default="NOT_REQUIRED",
        ),
    )

    # --- projects: split do valor vendido em horas × taxa por tipo -------
    op.add_column("projects", sa.Column("management_hours", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("management_rate", sa.Numeric(12, 2), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("consulting_hours", sa.Numeric(10, 2), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("consulting_rate", sa.Numeric(12, 2), nullable=False, server_default="0"))

    # --- resources: calendário pessoal opcional ---------------------------
    op.add_column("resources", sa.Column("calendar_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_resources_calendar_id_calendars",
        "resources",
        "calendars",
        ["calendar_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- timesheets: apontamento avulso (task_id opcional + project_id) --
    op.alter_column("timesheets", "task_id", existing_type=sa.String(length=36), nullable=True)
    op.add_column("timesheets", sa.Column("project_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_timesheets_project_id_projects",
        "timesheets",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_timesheets_project_id_projects", "timesheets", type_="foreignkey")
    op.drop_column("timesheets", "project_id")
    # Falha aqui se já existir algum apontamento avulso (task_id NULL) criado
    # depois do upgrade — é esperado: downgrade não decide por você o que
    # fazer com dados que só existem por causa da funcionalidade nova.
    # Apague ou vincule manualmente esses registros a uma tarefa antes de
    # rodar o downgrade, se for o caso.
    op.alter_column("timesheets", "task_id", existing_type=sa.String(length=36), nullable=False)

    op.drop_constraint("fk_resources_calendar_id_calendars", "resources", type_="foreignkey")
    op.drop_column("resources", "calendar_id")

    op.drop_column("projects", "consulting_rate")
    op.drop_column("projects", "consulting_hours")
    op.drop_column("projects", "management_rate")
    op.drop_column("projects", "management_hours")

    op.drop_column("tasks", "client_approval_status")
    op.drop_column("tasks", "task_type")

    bind = op.get_bind()
    task_approval_status_enum.drop(bind, checkfirst=True)
    task_type_enum.drop(bind, checkfirst=True)
