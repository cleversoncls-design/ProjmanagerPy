#!/usr/bin/env bash
# Prepara o .env, fixa API_PORT=3035, valida o docker-compose e builda os
# serviços. Referenciado pelo README, mas ausente no repositório até esta
# correção.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

ENV_FILE=".env"
FIRST_RUN=false

if [ ! -f "$ENV_FILE" ]; then
    cp .env.example "$ENV_FILE"
    FIRST_RUN=true
    echo "Arquivo $ENV_FILE criado a partir de .env.example."
fi

# Garante que a porta externa da API seja 3035, independentemente do que já
# estiver no .env.
if grep -q '^API_PORT=' "$ENV_FILE"; then
    sed -i.bak 's/^API_PORT=.*/API_PORT=3035/' "$ENV_FILE" && rm -f "$ENV_FILE.bak"
else
    echo "API_PORT=3035" >> "$ENV_FILE"
fi

CURRENT_PASSWORD=$(grep '^POSTGRES_PASSWORD=' "$ENV_FILE" | cut -d '=' -f2-)
if [ -z "$CURRENT_PASSWORD" ] || [ "$CURRENT_PASSWORD" = "troque-esta-senha" ]; then
    echo
    echo "AVISO: defina uma senha forte em POSTGRES_PASSWORD no arquivo $ENV_FILE antes de continuar."
    FIRST_RUN=true
fi

CURRENT_SECRET=$(grep '^JWT_SECRET_KEY=' "$ENV_FILE" 2>/dev/null | cut -d '=' -f2- || true)
if [ -z "$CURRENT_SECRET" ] || [ "$CURRENT_SECRET" = "troque-esta-chave-por-um-valor-aleatorio-forte" ]; then
    GENERATED_SECRET=$(openssl rand -hex 32)
    if grep -q '^JWT_SECRET_KEY=' "$ENV_FILE"; then
        sed -i.bak "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${GENERATED_SECRET}/" "$ENV_FILE" && rm -f "$ENV_FILE.bak"
    else
        echo "JWT_SECRET_KEY=${GENERATED_SECRET}" >> "$ENV_FILE"
    fi
    echo "JWT_SECRET_KEY gerado automaticamente em $ENV_FILE."
fi

docker compose config >/dev/null

if [ "$FIRST_RUN" = true ]; then
    echo
    echo "Revise o arquivo $ENV_FILE (principalmente POSTGRES_PASSWORD) e rode este script novamente para continuar."
    exit 0
fi

docker compose build
docker compose up -d
docker compose ps
