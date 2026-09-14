#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:3035}"
EMAIL="${2:-}"
PASSWORD="${3:-}"
STAMP="$(date +%s)"
CLIENT_ID=""
PROJECT_ID=""
TASK_ID=""

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Uso: $0 BASE_URL EMAIL SENHA" >&2
  exit 2
fi

json_value() {
  python3 -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

assert_list_contains_id() {
  python3 -c 'import json, sys; rows=json.load(sys.stdin); rid=sys.argv[1]; assert any(row.get("id") == rid for row in rows), f"ID não encontrado na listagem: {rid}"' "$1"
}

request_json() {
  curl -fsS "$@"
}

cleanup() {
  set +e
  [[ -n "$TASK_ID" ]] && curl -fsS -o /dev/null -X DELETE "$BASE_URL/tasks/$TASK_ID" -H "Authorization: Bearer $TOKEN"
  [[ -n "$PROJECT_ID" ]] && curl -fsS -o /dev/null -X DELETE "$BASE_URL/projects/$PROJECT_ID" -H "Authorization: Bearer $TOKEN"
  [[ -n "$CLIENT_ID" ]] && curl -fsS -o /dev/null -X DELETE "$BASE_URL/clients/$CLIENT_ID" -H "Authorization: Bearer $TOKEN"
}

LOGIN_RESPONSE=$(request_json -X POST "$BASE_URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(EMAIL="$EMAIL" PASSWORD="$PASSWORD" python3 -c 'import json, os; print(json.dumps({"email": os.environ["EMAIL"], "password": os.environ["PASSWORD"]}))')")
TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | json_value access_token)
USER_ID=$(printf '%s' "$LOGIN_RESPONSE" | python3 -c 'import json, sys; print(json.load(sys.stdin)["user"]["id"])')
trap cleanup EXIT

printf 'auth/me: '
curl -fsS "$BASE_URL/auth/me" -H "Authorization: Bearer $TOKEN"
printf '\n'

CLIENT_RESPONSE=$(request_json -X POST "$BASE_URL/clients" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"code\":\"E2E-$STAMP\",\"legal_name\":\"Cliente E2E Temporário\",\"trade_name\":\"E2E\"}")
CLIENT_ID=$(printf '%s' "$CLIENT_RESPONSE" | json_value id)
printf 'client created: %s\n' "$CLIENT_ID"

CLIENT_PATCH=$(request_json -X PATCH "$BASE_URL/clients/$CLIENT_ID" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"trade_name":"E2E Atualizado"}')
printf 'client updated: %s\n' "$(printf '%s' "$CLIENT_PATCH" | json_value trade_name)"
CLIENT_LIST=$(request_json "$BASE_URL/clients" -H "Authorization: Bearer $TOKEN")
printf '%s' "$CLIENT_LIST" | assert_list_contains_id "$CLIENT_ID"
printf 'client persisted in list: %s\n' "$CLIENT_ID"

PROJECT_RESPONSE=$(request_json -X POST "$BASE_URL/projects" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"client_id\":\"$CLIENT_ID\",\"manager_id\":\"$USER_ID\",\"code\":\"E2E-$STAMP\",\"name\":\"Projeto E2E Temporário\",\"sold_value\":0}")
PROJECT_ID=$(printf '%s' "$PROJECT_RESPONSE" | json_value id)
printf 'project created: %s\n' "$PROJECT_ID"

PROJECT_PATCH=$(request_json -X PATCH "$BASE_URL/projects/$PROJECT_ID" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"name":"Projeto E2E Atualizado","status":"ACTIVE"}')
printf 'project updated: %s\n' "$(printf '%s' "$PROJECT_PATCH" | json_value name)"
PROJECT_LIST=$(request_json "$BASE_URL/projects" -H "Authorization: Bearer $TOKEN")
printf '%s' "$PROJECT_LIST" | assert_list_contains_id "$PROJECT_ID"
printf 'project persisted in list: %s\n' "$PROJECT_ID"
printf '%s' "$PROJECT_LIST" | python3 -c 'import json, sys; rows=json.load(sys.stdin); project_id, client_id=sys.argv[1:]; row=next(item for item in rows if item.get("id") == project_id); assert row.get("client_id") == client_id, "Cliente não vinculado ao projeto: %s" % row.get("client_id")' "$PROJECT_ID" "$CLIENT_ID"
printf 'project linked to client: %s\n' "$CLIENT_ID"

TASK_RESPONSE=$(request_json -X POST "$BASE_URL/tasks" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d "{\"project_id\":\"$PROJECT_ID\",\"name\":\"Tarefa E2E Temporária\",\"wbs_code\":\"1.1\",\"estimated_hours\":1}")
TASK_ID=$(printf '%s' "$TASK_RESPONSE" | json_value id)
printf 'task created: %s\n' "$TASK_ID"

TASK_PATCH=$(request_json -X PATCH "$BASE_URL/tasks/$TASK_ID" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{"name":"Tarefa E2E Atualizada","progress_percentage":25}')
printf 'task updated: %s\n' "$(printf '%s' "$TASK_PATCH" | json_value name)"

printf 'CRUD autenticado concluído; os registros temporários serão removidos automaticamente.\n'
