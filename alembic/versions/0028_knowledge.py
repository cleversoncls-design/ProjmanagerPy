"""Conhecimento: catálogo (Sistema/Módulo/Funcionalidade), autoavaliação e aprovação

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-04

Pedido do usuário, "NOVAS MELHORIAS": "criar um processo de registro de
conhecimento dos consultores" — cadastro em 3 níveis (Sistema > Módulo >
Funcionalidade), autoavaliação de nível de conhecimento (0 a 4) por recurso
(Consultor/Gerente de Projeto) e revisão/aprovação por um gestor. Ver
docstrings de KnowledgeSystem/KnowledgeModule/KnowledgeFunctionality/
KnowledgeSubmission/ResourceKnowledge em app/models.py para o detalhe de
cada campo e decisão confirmada com o usuário (aprovação por envio
completo, revisor pode ajustar o nível, vínculo de perfil fica no Módulo).

`requirement`/`status` usam `String` simples, NÃO enum do Postgres — mesma
política já adotada desde a migração 0026 (ver lá e em
claude/processo-envio-emails.md): poucos valores fixos, sem necessidade
real de crescer, então nem vale o risco à toa do bug de enum duplicado da
migração 0024.

`has_table` checkfirst de propósito — mesmo motivo já documentado nas
migrações 0024/0025/0026: o `init_db()` do próprio app (app/database.py)
cria qualquer tabela que falte no startup da API a partir do metadata do
SQLAlchemy, antes de alguém rodar `alembic upgrade head` manualmente.

Ordem de criação respeita as dependências de FK: systems -> modules ->
functionalities -> submissions (depende só de resources/users, que já
existem) -> resource_knowledge (depende de resources, functionalities e
submissions).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0028"
down_revision: Union[str, None] = "0027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "knowledge_systems" not in existing:
        op.create_table(
            "knowledge_systems",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False, unique=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )

    if "knowledge_modules" not in existing:
        op.create_table(
            "knowledge_modules",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("system_id", sa.String(36), sa.ForeignKey("knowledge_systems.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("applies_to_consultant", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("applies_to_internal_pm", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("applies_to_consultant OR applies_to_internal_pm", name="ck_knowledge_module_has_profile"),
        )
        op.create_index("ix_knowledge_modules_system_id", "knowledge_modules", ["system_id"])

    if "knowledge_functionalities" not in existing:
        op.create_table(
            "knowledge_functionalities",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("module_id", sa.String(36), sa.ForeignKey("knowledge_modules.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("requirement", sa.String(12), nullable=False, server_default="REQUIRED"),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_knowledge_functionalities_module_id", "knowledge_functionalities", ["module_id"])

    if "knowledge_submissions" not in existing:
        op.create_table(
            "knowledge_submissions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("resource_id", sa.String(36), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("status", sa.String(12), nullable=False, server_default="SUBMITTED"),
            sa.Column("submitted_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("review_notes", sa.Text(), nullable=True),
        )
        op.create_index("ix_knowledge_submissions_resource_id", "knowledge_submissions", ["resource_id"])

    if "resource_knowledge" not in existing:
        op.create_table(
            "resource_knowledge",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("resource_id", sa.String(36), sa.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "functionality_id",
                sa.String(36),
                sa.ForeignKey("knowledge_functionalities.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("self_level", sa.Integer(), nullable=True),
            sa.Column("reviewed_level", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(12), nullable=False, server_default="DRAFT"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "submission_id", sa.String(36), sa.ForeignKey("knowledge_submissions.id", ondelete="SET NULL"), nullable=True
            ),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("resource_id", "functionality_id", name="uq_resource_knowledge_resource_functionality"),
            sa.CheckConstraint("self_level IS NULL OR self_level BETWEEN 0 AND 4", name="ck_resource_knowledge_self_level_range"),
            sa.CheckConstraint(
                "reviewed_level IS NULL OR reviewed_level BETWEEN 0 AND 4", name="ck_resource_knowledge_reviewed_level_range"
            ),
        )
        op.create_index("ix_resource_knowledge_resource_id", "resource_knowledge", ["resource_id"])
        op.create_index("ix_resource_knowledge_functionality_id", "resource_knowledge", ["functionality_id"])
        op.create_index("ix_resource_knowledge_submission_id", "resource_knowledge", ["submission_id"])


def downgrade() -> None:
    op.drop_table("resource_knowledge")
    op.drop_table("knowledge_submissions")
    op.drop_table("knowledge_functionalities")
    op.drop_table("knowledge_modules")
    op.drop_table("knowledge_systems")
