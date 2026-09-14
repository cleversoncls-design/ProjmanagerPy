#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:3035}"
WEB_URL="${WEB_URL:-http://127.0.0.1:3036}"

cd "${PROJECT_DIR:-/home/ProjmanagerPy}"

echo "Containers:"
docker compose ps

echo
echo "API health:"
curl -fsS --connect-timeout 3 --max-time 8 "$API_URL/health"
echo
echo "Frontend headers:"
curl -fsSI --connect-timeout 3 --max-time 8 "$WEB_URL/"
echo
echo "Frontend bundle:"
INDEX_HTML=$(curl -fsS --connect-timeout 3 --max-time 8 "$WEB_URL/")
BUNDLE=$(printf '%s' "$INDEX_HTML" | grep -oE '/assets/index-[^\"]+\.js' | head -n 1 || true)
if [ -z "$BUNDLE" ]; then
  echo "Frontend bundle not found" >&2
  exit 1
fi
printf '%s\n' "$BUNDLE"
echo
echo "Local validation completed."
