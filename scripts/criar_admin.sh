#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "Arquivo .env não encontrado. Execute: cp .env.example .env" >&2
  exit 1
fi

set -a
source ./.env
set +a

read -r -p "Nome do administrador: " ADMIN_NAME
read -r -p "E-mail do administrador: " ADMIN_EMAIL
read -r -s -p "Senha inicial: " ADMIN_PASSWORD
echo
read -r -s -p "Confirme a senha: " ADMIN_PASSWORD_CONFIRM
echo

if [[ -z "$ADMIN_NAME" || -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
  echo "Nome, e-mail e senha são obrigatórios." >&2
  exit 1
fi
if [[ "$ADMIN_PASSWORD" != "$ADMIN_PASSWORD_CONFIRM" ]]; then
  echo "As senhas não conferem." >&2
  exit 1
fi

USER_ID=$(cat /proc/sys/kernel/random/uuid)
PASSWORD_HASH=$(docker compose exec -T -e ADMIN_PASSWORD="$ADMIN_PASSWORD" api python -c 'import hashlib, os; salt=os.urandom(16); digest=hashlib.pbkdf2_hmac("sha256", os.environ["ADMIN_PASSWORD"].encode(), salt, 310000); print(f"pbkdf2_sha256$310000${salt.hex()}${digest.hex()}")')

docker compose exec -T db psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v user_id="$USER_ID" -v user_name="$ADMIN_NAME" \
  -v user_email="$ADMIN_EMAIL" -v user_hash="$PASSWORD_HASH" <<'SQL'
INSERT INTO users (id, name, email, password_hash, role, status)
VALUES (:'user_id', :'user_name', lower(:'user_email'), :'user_hash', 'ADMIN', 'ACTIVE')
ON CONFLICT (email) DO UPDATE SET
  name = EXCLUDED.name,
  password_hash = EXCLUDED.password_hash,
  role = 'ADMIN',
  status = 'ACTIVE',
  updated_at = CURRENT_TIMESTAMP;
SQL

echo "Administrador criado/atualizado: $ADMIN_EMAIL"
