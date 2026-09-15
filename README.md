# ProjmanagerPy — Controle de Projetos Corporativo

Base em **Python 3.12, FastAPI, SQLAlchemy 2 e PostgreSQL 16**, preparada para execução local ou em servidor próprio por meio de Docker Compose. O modelo corporativo cobre clientes, usuários, projetos, EAP/WBS, recursos, timesheets, despesas, calendário, riscos, mudanças e dependências de tarefas, com autenticação por login (JWT) e uma API REST cobrindo cada uma dessas entidades.

## Componentes

| Componente | Responsabilidade |
|---|---|
| `app/models.py` | ORM completo, enums, chaves estrangeiras, índices e restrições de unicidade. |
| `app/services.py` | Calendário de dias úteis, motor de cascata FS/SS/FF/SF e cálculo financeiro. |
| `app/database.py` | Configuração e ciclo de vida da engine/sessão do banco. |
| `app/security.py` | Hash de senha (bcrypt) e emissão/validação de tokens JWT. |
| `app/deps.py` | Dependências de autenticação e autorização (escopo por perfil/`client_id`). |
| `app/schemas.py` | Modelos Pydantic de entrada/saída da API. |
| `app/routers/` | Rotas da API, uma por domínio (auth, projetos, tarefas, timesheets, riscos, etc.). |
| `app/main.py` | Monta a aplicação FastAPI, inclui os routers e trata erros de integridade do banco. |
| `docker-compose.yml` | Serviços `api` e `db`, persistência PostgreSQL, healthcheck e reinício automático. |
| `Dockerfile` | Imagem reproduzível da API, rodando com usuário não-root. |
| `scripts/seed_admin.py` | Cria o primeiro usuário `ADMIN` (necessário para começar a usar a API). |
| `tests/` | Testes de calendário, cascata, cálculo financeiro e da API (autenticação, autorização, endpoints). |
| `.github/workflows/tests.yml` | CI: roda `pytest` a cada push/PR. |

## Instalação com Docker e PostgreSQL

No servidor local, instale Docker Engine e o plugin Docker Compose. Depois, clone o repositório, crie o arquivo de ambiente e suba os serviços:

```bash
git clone https://github.com/cleversoncls-design/ProjmanagerPy.git
cd ProjmanagerPy
cp .env.example .env
# Edite .env: defina uma senha forte em POSTGRES_PASSWORD e um valor
# aleatório forte em JWT_SECRET_KEY (ex.: openssl rand -hex 32)
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

O script cria `.env` quando necessário, gera um `JWT_SECRET_KEY` aleatório se ainda não houver um, valida a senha do PostgreSQL, fixa `API_PORT=3035`, valida o Compose e executa o build. Na primeira execução, ele interrompe antes do `docker compose up` para que você possa trocar a senha padrão.

Depois que a API estiver de pé, crie o primeiro usuário administrador (sem ele não há como fazer login em nenhuma rota):

```bash
docker compose exec api python -m scripts.seed_admin --email admin@empresa.com --name "Admin" --password "senha-forte"
```

Para acompanhar os logs ou parar a instalação:

```bash
docker compose logs -f api
docker compose down
```

Não use `docker compose down -v` salvo quando desejar apagar permanentemente o volume do PostgreSQL.

## Autenticação

A API usa login por e-mail/senha com token JWT — não existe mais o antigo header `X-User-Id` (que era aceito sem nenhuma verificação):

```bash
curl -X POST http://localhost:3035/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@empresa.com&password=senha-forte"
# -> {"access_token": "...", "token_type": "bearer", "user_id": "...", "role": "ADMIN"}

curl http://localhost:3035/projects \
  -H "Authorization: Bearer <access_token>"
```

O token expira em `JWT_EXPIRE_MINUTES` (padrão 480 minutos) e é assinado com `JWT_SECRET_KEY`. Troque essa chave por um valor aleatório forte antes de qualquer ambiente com dados reais — quem tiver a chave consegue forjar tokens.

## Endpoints

| Domínio | Rotas |
|---|---|
| Autenticação | `POST /auth/login` |
| Usuários | `POST /users` (ADMIN), `GET /users/me` |
| Clientes | `POST /clients`, `GET /clients`, `GET /clients/{id}` |
| Solicitações de projeto | `POST /clients/{client_id}/intakes`, `GET /clients/{client_id}/intakes`, `PATCH /intakes/{id}/status` |
| Projetos | `POST /projects`, `GET /projects`, `GET /projects/{id}`, `PATCH /projects/{id}` |
| Tarefas / EAP | `POST /projects/{project_id}/tasks`, `GET /projects/{project_id}/tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}` |
| Dependências | `POST /task-dependencies`, `GET /tasks/{id}/dependencies`, `POST /tasks/{id}/reschedule` |
| Recursos e alocação | `POST /resources`, `GET /resources/{id}`, `POST /tasks/{id}/assignments`, `GET /tasks/{id}/assignments` |
| Timesheets | `POST /timesheets`, `GET /timesheets?project_id=\|task_id=`, `PATCH /timesheets/{id}/status` |
| Despesas | `POST /projects/{project_id}/expenses`, `GET /projects/{project_id}/expenses` |
| Calendário | `POST /calendars`, `GET /calendars/{id}`, `POST /calendars/{id}/holidays`, `GET /calendars/{id}/holidays` |
| Riscos | `POST /projects/{project_id}/risks`, `GET /projects/{project_id}/risks`, `PATCH /risks/{id}` |
| Mudanças | `POST /projects/{project_id}/change-requests`, `GET /projects/{project_id}/change-requests`, `PATCH /change-requests/{id}/status` |
| Baselines | `POST /projects/{project_id}/baselines`, `GET /projects/{project_id}/baselines` |
| Operação | `GET /health` |

A documentação interativa (`/docs`) traz o schema completo de cada rota, incluindo os campos obrigatórios de cada payload.

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

O motor `reschedule_cascade` percorre o grafo de dependências em ordem topológica, detecta ciclos e recalcula cada sucessora pela predecessora mais restritiva entre todas as suas dependências (não apenas a última processada), ignorando finais de semana e feriados cadastrados. A tabela `task_dependencies` representa múltiplas relações predecessor/sucessor, enquanto `tasks.parent_task_id` permanece dedicada à hierarquia da EAP/WBS. O endpoint `POST /tasks/{id}/reschedule` aciona esse motor.

A função `project_financials` calcula o custo real como horas apontadas multiplicadas pelo custo interno do recurso, acrescidas das despesas do projeto, excluindo timesheets rejeitados (`PENDING` e `APPROVED` entram no custo real). A margem é calculada como `sold_value - real_cost`.

Perfis `CLIENT_PM` e `CLIENT_USER` só acessam projetos cujo `client_id` seja igual ao seu próprio; para esses perfis, a resposta de `GET /projects/{id}` omite `sold_value` e `financials`. Dentro do escopo do cliente, `CLIENT_PM` pode escrever (criar tarefas, riscos, mudanças, despesas); `CLIENT_USER` é sempre somente leitura. Perfis internos (`ADMIN`, `INTERNAL_PM`, `CONSULTANT`) têm acesso de leitura e escrita a qualquer projeto.

Um apontamento de horas (`POST /timesheets`) só é aceito se: o projeto estiver `ACTIVE`; o usuário autenticado tiver um `Resource` cadastrado; e esse recurso estiver alocado à tarefa via `TaskAssignment`. Não é permitido mais de um apontamento do mesmo recurso, na mesma tarefa, na mesma data.

## Desenvolvimento sem Docker

O SQLite continua disponível como fallback local quando `DATABASE_URL` não é definida:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
export JWT_SECRET_KEY="chave-de-desenvolvimento"
PYTHONPATH=. pytest -q
python -m scripts.seed_admin --email admin@local.dev --name "Admin" --password "senha-forte"
uvicorn app.main:app --reload
```

`requirements.txt` contém só as dependências de produção; `requirements-dev.txt` acrescenta `pytest`/`httpx` para rodar a suíte de testes.

## Próximas evoluções recomendadas

Antes de produção, adicione Alembic para migrações versionadas, rotação de chave JWT/refresh tokens, auditoria (quem alterou o quê), rate limiting e observabilidade (logs estruturados, métricas). A criação automática das tabelas por `Base.metadata.create_all` é adequada para a primeira instalação, mas deve ser substituída por migrações controladas em ambientes produtivos.
