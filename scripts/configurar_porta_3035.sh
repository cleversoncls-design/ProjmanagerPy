#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Erro: Docker não está instalado ou não está no PATH." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "Erro: o plugin Docker Compose não está disponível." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Arquivo .env criado a partir de .env.example."
  echo "Edite POSTGRES_PASSWORD antes de continuar: $APP_DIR/.env"
  exit 1
fi

if grep -Eq '^POSTGRES_PASSWORD=(troque-esta-senha)?$' .env; then
  echo "Erro: defina uma senha real em POSTGRES_PASSWORD no arquivo .env." >&2
  exit 1
fi

if grep -q '^API_PORT=' .env; then
  sed -i 's/^API_PORT=.*/API_PORT=3035/' .env
else
  printf '\nAPI_PORT=3035\n' >> .env
fi

echo "Validando configuração do Compose..."
docker compose config >/dev/null

echo "Subindo a aplicação na porta externa 3035..."
docker compose up -d --build

echo
echo "Status dos serviços:"
docker compose ps

echo
echo "API: http://$(hostname -I | awk '{print $1}'):3035"
echo "Documentação: http://$(hostname -I | awk '{print $1}'):3035/docs"

echo
echo "Se o firewalld estiver ativo, libere a porta com:"
echo "  firewall-cmd --permanent --add-port=3035/tcp"
echo "  firewall-cmd --reload"
