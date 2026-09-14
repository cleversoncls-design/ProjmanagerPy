#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ProjmanagerPy}"
cd "$PROJECT_DIR"

if ! docker compose ps --status running --services | grep -qx 'db'; then
  echo "O serviço db não está em execução. Inicie-o com: docker compose up -d db" >&2
  exit 1
fi

echo "Aplicando migração de calendários e vínculo aos recursos..."
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < scripts/migrar_calendarios.sql

echo "Migração concluída."
