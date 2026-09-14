#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ProjmanagerPy}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi
if ! [[ "$RETENTION_DAYS" =~ ^[0-9]+$ ]]; then
  echo "RETENTION_DAYS must be a non-negative integer" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
cd "$PROJECT_DIR"

STAMP=$(date -u +%Y%m%d_%H%M%S)
TARGET="$BACKUP_DIR/projmanager_${STAMP}.sql.gz"
TEMP="$TARGET.tmp"
trap 'rm -f "$TEMP"' EXIT
umask 077

echo "Creating PostgreSQL backup: $TARGET"
docker compose exec -T db sh -c 'pg_dump --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB"' | gzip -9 > "$TEMP"
gzip -t "$TEMP"
mv -f "$TEMP" "$TARGET"

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'projmanager_*.sql.gz' -mtime "+$RETENTION_DAYS" -delete

printf 'Backup completed: %s\n' "$TARGET"
printf 'Backup size: '
stat -c '%s bytes' "$TARGET"
printf 'Available backups: '
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'projmanager_*.sql.gz' -printf '%f\n' | sort | wc -l
