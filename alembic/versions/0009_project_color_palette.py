"""Cor do projeto: paleta de 256 cores nomeadas (hex) no lugar das 8 chaves
categóricas fixas ("series-1".."series-8")

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-29

Migração só de DADOS — a coluna `projects.color` já era string (varchar) e
continua sendo, tamanho já suficiente pra guardar um hex ("#RRGGBB", 7
caracteres). O que muda é o CONTEÚDO: projetos existentes tinham uma das 8
chaves antigas ("series-1".."series-8", que o frontend resolvia via
variável CSS --series-N, com um valor pra tema claro e outro pra escuro —
ver frontend/src/index.css); a partir de agora `color` guarda o hex direto
(ver app/color_palette.py), então esta migração troca cada chave antiga
pelo hex correspondente do tema CLARO (valor usado como referência, já que
a paleta nova não tem mais par claro/escuro por cor — trade-off aceito
pelo usuário ao pedir uma paleta maior). Nenhum projeto fica com uma chave
"series-N" órfã depois desta migração.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Hex do tema claro de cada chave antiga (--series-1..8 em index.css, bloco
# :root, ANTES desta mudança) — usado só pra converter dados existentes.
_OLD_KEY_TO_HEX = {
    "series-1": "#2A78D6",
    "series-2": "#EB6834",
    "series-3": "#1BAF7A",
    "series-4": "#EDA100",
    "series-5": "#E87BA4",
    "series-6": "#008300",
    "series-7": "#4A3AA7",
    "series-8": "#E34948",
}


def upgrade() -> None:
    projects = sa.table("projects", sa.column("color", sa.String))
    for key, hex_value in _OLD_KEY_TO_HEX.items():
        op.execute(projects.update().where(projects.c.color == key).values(color=hex_value))


def downgrade() -> None:
    # Downgrade com perda: só reverte os projetos cujo hex bate exatamente
    # com um dos 8 valores originais (mapeamento 1:1 inverso). Um projeto
    # recolorido para qualquer uma das outras 248 cores novas não tem
    # correspondente na paleta antiga de 8 — fica em "series-1" como
    # fallback, mesmo default de antes desta migração existir.
    projects = sa.table("projects", sa.column("color", sa.String))
    hex_to_old_key = {hex_value: key for key, hex_value in _OLD_KEY_TO_HEX.items()}
    for hex_value, key in hex_to_old_key.items():
        op.execute(projects.update().where(projects.c.color == hex_value).values(color=key))
    known_hexes = tuple(hex_to_old_key.keys())
    op.execute(projects.update().where(projects.c.color.notin_(known_hexes)).values(color="series-1"))
