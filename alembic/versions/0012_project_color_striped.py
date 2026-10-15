"""Flag de cor listrada para projetos finalizados

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-29

Novo campo `projects.color_striped` (boolean, default false). Controla se
a tela mostra a cor real do projeto (`projects.color`, nunca apagada) ou
o padrão listrado branco/vermelho fixo de projeto finalizado — ver
comentário em `Project.color_striped` (app/models.py) e
`_ensure_color_available`/`_sync_color_striped` em app/routers/projects.py.
Liga sozinho quando o status vira COMPLETED ou CANCELLED (libera a cor
pra outro projeto ativo usar) e desliga sozinho na reativação.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "color_striped",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("projects", "color_striped")
