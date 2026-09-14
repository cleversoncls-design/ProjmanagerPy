#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ProjmanagerPy}"
BACKUP_FILE="${1:-}"
KEEP_DB="${KEEP_DB:-0}"

cd "$PROJECT_DIR"
if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE=$(find "$PROJECT_DIR/backups" -maxdepth 1 -type f -name 'projmanager_*.sql.gz' -printf '%T@ %p\n' 2>/dev/null | sort -nr | awk 'NR==1 {$1=""; sub(/^ /, ""); print}')
fi
if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
  echo "Nenhum backup .sql.gz foi encontrado." >&2
  exit 1
fi

gzip -t "$BACKUP_FILE"
DB_NAME="projmanager_homologacao_$(date -u +%Y%m%d_%H%M%S)_$$"
cleanup() {
  if [ "$KEEP_DB" != "1" ]; then
    docker compose exec -T db sh -c 'dropdb --if-exists -U "$POSTGRES_USER" "$1"' sh "$DB_NAME" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Criando banco temporário: $DB_NAME"
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$DB_NAME"
echo "Restaurando: $BACKUP_FILE"
gunzip -c "$BACKUP_FILE" | docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1"' sh "$DB_NAME" >/dev/null
TABLES=$(docker compose exec -T db sh -c 'psql -At -U "$POSTGRES_USER" -d "$1" -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = '\''public'\'';"' sh "$DB_NAME" | tr -d '[:space:]')
case "$TABLES" in
  ''|*[!0-9]*) echo "Não foi possível validar a quantidade de tabelas." >&2; exit 1 ;;
  0) echo "Restauração concluída, mas nenhuma tabela pública foi encontrada." >&2; exit 1 ;;
  *) echo "Restauração de homologação validada: $TABLES tabela(s)." ;;
esac
if [ "$KEEP_DB" = "1" ]; then
  echo "Banco preservado por KEEP_DB=1: $DB_NAME"
else
  echo "Banco temporário será removido ao finalizar o teste."
fi
