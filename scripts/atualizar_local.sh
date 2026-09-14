#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ProjmanagerPy}"
DOWNLOAD_DIR="${DOWNLOAD_DIR:-/home/resultarpy/Descargas}"
WORK_DIR="${WORK_DIR:-/tmp/projmanager-atualizacao}"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "Project directory not found: $PROJECT_DIR" >&2
  exit 1
fi

if [ ! -d "$DOWNLOAD_DIR" ]; then
  echo "Download directory not found: $DOWNLOAD_DIR" >&2
  exit 1
fi

PACKAGE="${1:-}"
if [ -z "$PACKAGE" ]; then
  PACKAGE=$(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -name 'ProjmanagerPy_fullstack_*.zip' -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n 1 | cut -d' ' -f2-)
fi

if [ -z "$PACKAGE" ] || [ ! -f "$PACKAGE" ]; then
  echo "No full-stack ZIP found in $DOWNLOAD_DIR" >&2
  echo "Usage: $0 /path/to/ProjmanagerPy_fullstack_package.zip" >&2
  exit 1
fi

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR"
unzip -q -o "$PACKAGE" -d "$WORK_DIR"

EXTRACTED="$WORK_DIR/ProjmanagerPy"
if [ ! -d "$EXTRACTED" ]; then
  echo "Invalid package: expected $EXTRACTED" >&2
  exit 1
fi

if [ -d "$EXTRACTED/frontend" ]; then
  rm -rf "$PROJECT_DIR/frontend"
fi
cp -aPf "$EXTRACTED/." "$PROJECT_DIR/"

cd "$PROJECT_DIR"
chmod +x scripts/*.sh 2>/dev/null || true

echo "Package applied: $PACKAGE"
echo "Rebuilding API and web; PostgreSQL data volume is preserved."
docker compose build --no-cache api web
docker compose up -d --force-recreate api web
./scripts/migrar_calendarios.sh
./scripts/migrar_tarefas_avancadas.sh
./scripts/migrar_moedas_projetos.sh

echo "Local validation:"

docker compose ps
wait_for_url() {
  local url="$1"
  local response=""
  local attempt
  for attempt in $(seq 1 30); do
    if response=$(curl -fsS --connect-timeout 2 --max-time 5 "$url" 2>/dev/null); then
      printf '%s' "$response"
      return 0
    fi
    sleep 2
  done
  echo "Service did not become ready: $url" >&2
  return 1
}
API_HEALTH=$(wait_for_url http://127.0.0.1:3035/health)
printf 'API health: %s\n' "$API_HEALTH"
INDEX_HTML=$(wait_for_url http://127.0.0.1:3036/)
BUNDLE=$(printf '%s' "$INDEX_HTML" | grep -oE '/assets/index-[^\"]+\.js' | head -n 1 || true)
if [ -z "$BUNDLE" ]; then
  echo "Frontend bundle was not found in the served index.html" >&2
  exit 1
fi
printf 'Frontend bundle: %s\n' "$BUNDLE"
printf 'Frontend and API updated at http://127.0.0.1:3036/ and http://127.0.0.1:3035/docs\n'
