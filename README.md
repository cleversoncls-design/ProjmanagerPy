# ProjmanagerPy — Controle de Projetos Corporativo

Base em **Python 3.12, FastAPI, SQLAlchemy 2 e PostgreSQL 16**, preparada para execução local ou em servidor próprio por meio de Docker Compose. O repositório agora contém o modelo corporativo de clientes, usuários, projetos, EAP/WBS, recursos, timesheets, despesas, calendário, riscos, mudanças e dependências de tarefas.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `app/models.py` | ORM completo, enums, chaves estrangeiras, índices e restrições de unicidade. |
| `app/services.py` | Calendário de dias úteis, motor de cascata FS/SS/FF/SF e cálculo financeiro. |
| `app/main.py` | API FastAPI, conexão configurável e controle de escopo por perfil/client_id. |
| `docker-compose.yml` | Serviços `api` e `db`, persistência PostgreSQL, healthcheck e reinício automático. |
| `Dockerfile` | Imagem reproduzível da API. |
| `tests/` | Testes de calendário, cascata e margem financeira. |

## Instalação com Docker e PostgreSQL

No servidor local, instale Docker Engine e o plugin Docker Compose. Depois, clone o repositório, crie o arquivo de ambiente e suba os serviços:

```bash
git clone https://github.com/cleversoncls-design/ProjmanagerPy.git
cd ProjmanagerPy
cp .env.example .env
# Edite .env e defina uma senha forte em POSTGRES_PASSWORD
nano .env
docker compose up -d --build
docker compose ps
```

A API ficará disponível em `http://localhost:3035` e a documentação interativa em `http://localhost:3035/docs`. A aplicação espera o PostgreSQL passar no healthcheck antes de iniciar. Os dados são persistidos no volume Docker `postgres_data`, portanto a remoção dos containers não remove o banco. O padrão configurado para acesso externo é a porta **3035**; a porta interna do container continua sendo `8000`. A aplicação recebe as credenciais do PostgreSQL em variáveis separadas e monta a URL com SQLAlchemy, permitindo senhas com caracteres como `@`, `:`, `/` e `#`.

Para aplicar a configuração automaticamente, tornar o processo repetível e recriar os serviços, execute:

```bash
chmod +x scripts/configurar_porta_3035.sh
./scripts/configurar_porta_3035.sh
```

O script cria `.env` quando necessário, valida a senha do PostgreSQL, fixa `API_PORT=3035`, valida o Compose e executa o build. Na primeira execução, ele interrompe antes do `docker compose up` para que você possa trocar a senha padrão.

Para acompanhar os logs ou parar a instalação:

```bash
docker compose logs -f api
docker compose down
```

Não use `docker compose down -v` salvo quando desejar apagar permanentemente o volume do PostgreSQL.

## Backup e restauração

O backup deve ser executado a partir do container do banco:

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" > backups/projmanager_$(date +%Y%m%d_%H%M%S).sql
```

Para restaurar em uma base vazia, interrompa a API e envie o arquivo para o PostgreSQL:

```bash
docker compose stop api
docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backups/arquivo.sql
docker compose start api
```

## Regras implementadas

O motor `reschedule_cascade` percorre dependências em profundidade, detecta ciclos e recalcula sucessoras ignorando finais de semana e feriados cadastrados. A tabela adicional `task_dependencies` representa múltiplas relações predecessor/sucessora, enquanto `tasks.parent_task_id` permanece dedicada à hierarquia da EAP/WBS.

A função `project_financials` calcula o custo real como horas apontadas multiplicadas pelo custo interno do recurso, acrescidas das despesas do projeto, excluindo timesheets rejeitados. A margem é calculada como `sold_value - real_cost`.

Perfis `CLIENT_PM` e `CLIENT_USER` só acessam projetos cujo `client_id` seja igual ao seu próprio. Para esses perfis, a resposta omite `sold_value` e todos os dados de rentabilidade. O cabeçalho `X-User-Id` é um adaptador demonstrativo; antes de produção, substitua-o por JWT/OIDC com assinatura, expiração, rotação de chaves e auditoria.

## Desenvolvimento sem Docker

O SQLite continua disponível como fallback local quando `DATABASE_URL` não é definida:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest -q
uvicorn app.main:app --reload
```

## Próximas evoluções recomendadas

Antes de produção, adicione Alembic para migrações versionadas, autenticação OIDC/JWT, auditoria, validações de datas e limites, isolamento por tenant em todas as consultas, observabilidade, rate limiting e testes de autorização entre clientes. A criação automática das tabelas por `Base.metadata.create_all` é adequada para a primeira instalação, mas deve ser substituída por migrações controladas em ambientes produtivos.
