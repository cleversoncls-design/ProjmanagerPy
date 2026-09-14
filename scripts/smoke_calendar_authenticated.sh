#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:3035}"
EMAIL="${2:-}"
PASSWORD="${3:-}"
STAMP="$(date +%s)"
TOKEN=""
CALENDAR_ID=""
SECOND_CALENDAR_ID=""
RESOURCE_ID=""

if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
  echo "Uso: $0 BASE_URL EMAIL SENHA" >&2
  exit 2
fi

request_json() {
  curl -fsS "$@"
}

json_value() {
  python3 -c 'import json, sys; print(json.load(sys.stdin)[sys.argv[1]])' "$1"
}

cleanup() {
  set +e
  if [[ -n "$TOKEN" ]]; then
    [[ -n "$RESOURCE_ID" ]] && curl -fsS -o /dev/null -X DELETE "$BASE_URL/resources/$RESOURCE_ID" -H "Authorization: Bearer $TOKEN"
    [[ -n "$SECOND_CALENDAR_ID" ]] && curl -fsS -o /dev/null -X DELETE "$BASE_URL/calendars/$SECOND_CALENDAR_ID" -H "Authorization: Bearer $TOKEN"
    [[ -n "$CALENDAR_ID" ]] && curl -fsS -o /dev/null -X DELETE "$BASE_URL/calendars/$CALENDAR_ID" -H "Authorization: Bearer $TOKEN"
  fi
}
trap cleanup EXIT

LOGIN_RESPONSE=$(request_json -X POST "$BASE_URL/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(EMAIL="$EMAIL" PASSWORD="$PASSWORD" python3 -c 'import json, os; print(json.dumps({"email": os.environ["EMAIL"], "password": os.environ["PASSWORD"]}))')")
TOKEN=$(printf '%s' "$LOGIN_RESPONSE" | json_value access_token)

MANAGERS_RESPONSE=$(request_json "$BASE_URL/users/managers" -H "Authorization: Bearer $TOKEN")
USER_ID=$(printf '%s' "$MANAGERS_RESPONSE" | python3 -c 'import json, sys; rows=json.load(sys.stdin); print(rows[0]["id"] if rows else "")')
if [[ -z "$USER_ID" ]]; then
  echo "Nenhum usuário interno elegível foi encontrado para criar o recurso temporário." >&2
  exit 1
fi

CALENDAR_RESPONSE=$(request_json -X POST "$BASE_URL/calendars" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke jornada $STAMP\",\"working_days\":[0,1,2,3,4]}")
CALENDAR_ID=$(printf '%s' "$CALENDAR_RESPONSE" | json_value id)
printf 'calendar created: %s\n' "$CALENDAR_ID"

HOLIDAY_RESPONSE=$(request_json -X POST "$BASE_URL/calendars/$CALENDAR_ID/holidays" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"date":"2026-08-05","description":"Smoke feriado temporário"}')
printf 'holiday created: %s\n' "$(printf '%s' "$HOLIDAY_RESPONSE" | json_value id)"

RESOURCE_RESPONSE=$(request_json -X POST "$BASE_URL/resources" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"user_id\":\"$USER_ID\",\"calendar_id\":\"$CALENDAR_ID\",\"role_title\":\"Smoke recurso temporário\",\"internal_cost_per_hour\":1,\"billing_rate_per_hour\":2,\"daily_capacity_hours\":6}")
RESOURCE_ID=$(printf '%s' "$RESOURCE_RESPONSE" | json_value id)
RESOURCE_CALENDAR_ID=$(printf '%s' "$RESOURCE_RESPONSE" | json_value calendar_id)
if [[ "$RESOURCE_CALENDAR_ID" != "$CALENDAR_ID" ]]; then
  echo "O recurso não retornou o calendário vinculado." >&2
  exit 1
fi
printf 'resource linked: %s\n' "$RESOURCE_ID"

AVAILABILITY=$(request_json "$BASE_URL/resources/$RESOURCE_ID/availability?start_date=2026-08-03&end_date=2026-08-09" -H "Authorization: Bearer $TOKEN")
ACTUAL_DATES=$(printf '%s' "$AVAILABILITY" | python3 -c 'import json, sys; print(",".join(json.load(sys.stdin)["working_dates"]))')
EXPECTED_DATES="2026-08-03,2026-08-04,2026-08-06,2026-08-07"
if [[ "$ACTUAL_DATES" != "$EXPECTED_DATES" ]]; then
  echo "Disponibilidade inesperada: $ACTUAL_DATES (esperado: $EXPECTED_DATES)" >&2
  exit 1
fi
printf 'availability validated: %s\n' "$ACTUAL_DATES"

SECOND_CALENDAR_RESPONSE=$(request_json -X POST "$BASE_URL/calendars" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"name\":\"Smoke jornada alternativa $STAMP\",\"working_days\":[0,2,4]}")
SECOND_CALENDAR_ID=$(printf '%s' "$SECOND_CALENDAR_RESPONSE" | json_value id)
SWITCHED_RESOURCE=$(request_json -X PATCH "$BASE_URL/resources/$RESOURCE_ID" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"calendar_id\":\"$SECOND_CALENDAR_ID\"}")
if [[ "$(printf '%s' "$SWITCHED_RESOURCE" | json_value calendar_id)" != "$SECOND_CALENDAR_ID" ]]; then
  echo "A troca do calendário do recurso não foi persistida." >&2
  exit 1
fi
PERSISTED_RESOURCE=$(request_json "$BASE_URL/resources" -H "Authorization: Bearer $TOKEN" | python3 -c 'import json, sys; rows=json.load(sys.stdin); rid=sys.argv[1]; print(next(row["calendar_id"] for row in rows if row["id"] == rid))' "$RESOURCE_ID")
if [[ "$PERSISTED_RESOURCE" != "$SECOND_CALENDAR_ID" ]]; then
  echo "O vínculo alterado não foi persistido na listagem de recursos." >&2
  exit 1
fi
printf 'resource calendar switched and persisted: %s\n' "$SECOND_CALENDAR_ID"
printf 'Calendário, feriado, vínculo, exceção de disponibilidade e troca de jornada validados; registros temporários serão removidos automaticamente.\n'
