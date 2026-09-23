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
| `app/audit.py` | Helper de auditoria mínima (`record_audit`), usado pelos routers de negócio. |
| `app/rate_limit.py` | Middleware opcional de rate limiting (janela deslizante em memória). |
| `app/routers/` | Rotas da API, uma por domínio (auth, projetos, tarefas, timesheets, riscos, auditoria, relatórios/dashboard, etc.). |
| `app/main.py` | Monta a aplicação FastAPI, inclui os routers, CORS e trata erros de integridade do banco. |
| `alembic/` | Migrações versionadas de schema (ver seção própria abaixo). |
| `docker-compose.yml` | Serviços `api`, `db` e `web` (frontend), persistência PostgreSQL, healthcheck e reinício automático. |
| `Dockerfile` | Imagem reproduzível da API, rodando com usuário não-root. |
| `frontend/` | SPA React (Fase 3) — ver `frontend/README.md` para desenvolvimento local; o `frontend/Dockerfile` builda a partir do código-fonte (não é um artefato pré-compilado commitado). |
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

O mesmo `docker compose up -d --build` já sobe o frontend junto (serviço `web`), disponível por padrão em `http://localhost:3036` (ou `http://<ip-do-servidor>:3036` quando acessado de outra máquina na rede — local ou pela internet, se a porta estiver liberada). Um ponto importante antes do primeiro build:

- **`CORS_ORIGINS`** precisa incluir **todas** as origens pelas quais alguém vai acessar o frontend — ex.: `http://192.168.22.20:3036,http://localhost:3036,http://<ip-publico>:3036` — senão a API rejeita por CORS as chamadas vindas dessas origens, mesmo com tudo no ar.

`VITE_API_BASE_URL` (no `.env`) normalmente fica **vazia** — o frontend descobre sozinho o endereço da API a partir do host que o navegador usou pra abrir a página, então o mesmo build funciona acessando por rede local, `localhost` ou IP público, sem precisar escolher um fixo. Só preencha essa variável se a API morar num host diferente do frontend; nesse caso o valor fica gravado dentro do JavaScript estático no momento do build, e mudar depois exige `docker compose build web && docker compose up -d web` — reiniciar o container sozinho não é suficiente.

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

### CORS

Por padrão, nenhuma origem de navegador é liberada (chamadas via curl, Swagger ou servidor-a-servidor continuam funcionando normalmente, pois CORS é uma restrição aplicada pelo navegador, não pela API). Para permitir que um front-end em outro domínio consuma a API diretamente do navegador, defina `CORS_ORIGINS` no `.env` com as origens autorizadas, separadas por vírgula:

```bash
CORS_ORIGINS=https://app.exemplo.com,https://admin.exemplo.com
```

## Endpoints

| Domínio | Rotas |
|---|---|
| Autenticação | `POST /auth/login` |
| Usuários | `POST /users` (ADMIN), `GET /users/me`, `GET /users?role=&client_id=` (ADMIN/INTERNAL_PM) |
| Clientes | `POST /clients`, `GET /clients`, `GET /clients/{id}` |
| Solicitações de projeto | `POST /clients/{client_id}/intakes`, `GET /clients/{client_id}/intakes`, `PATCH /intakes/{id}/status` |
| Projetos | `POST /projects`, `GET /projects`, `GET /projects/{id}`, `PATCH /projects/{id}` |
| Tarefas / EAP | `POST /projects/{project_id}/tasks`, `GET /projects/{project_id}/tasks`, `GET /tasks/{id}`, `PATCH /tasks/{id}` |
| Aprovação da tarefa pelo cliente | `POST /tasks/{id}/submit-for-approval`, `PATCH /tasks/{id}/client-approval` (CLIENT_PM/CLIENT_USER) |
| Dependências | `POST /task-dependencies`, `GET /tasks/{id}/dependencies`, `POST /tasks/{id}/reschedule` |
| Recursos e alocação | `POST /resources`, `GET /resources?user_id=`, `GET /resources/{id}`, `POST /tasks/{id}/assignments`, `GET /tasks/{id}/assignments` |
| Timesheets | `POST /timesheets`, `GET /timesheets?project_id=\|task_id=`, `PATCH /timesheets/{id}/status` |
| Despesas | `POST /projects/{project_id}/expenses`, `GET /projects/{project_id}/expenses` |
| Calendário | `POST /calendars`, `GET /calendars`, `GET /calendars/{id}`, `POST /calendars/{id}/holidays`, `GET /calendars/{id}/holidays` |
| Riscos | `POST /projects/{project_id}/risks`, `GET /projects/{project_id}/risks`, `PATCH /risks/{id}` |
| Mudanças | `POST /projects/{project_id}/change-requests`, `GET /projects/{project_id}/change-requests`, `PATCH /change-requests/{id}/status` |
| Baselines | `POST /projects/{project_id}/baselines`, `GET /projects/{project_id}/baselines` |
| Auditoria | `GET /audit-log?entity_type=&entity_id=&limit=` (ADMIN/INTERNAL_PM) |
| Relatórios / dashboard | `GET /dashboard`, `GET /reports/portfolio`, `GET /projects/{id}/report`, `GET /resources/utilization`, `GET /projects/{id}/risks/matrix`, `GET /reports/velocity`, `GET /reports/roi` (ADMIN/INTERNAL_PM), `GET /projects/{id}/gantt` |
| Operação | `GET /health` |

A documentação interativa (`/docs`) traz o schema completo de cada rota, incluindo os campos obrigatórios de cada payload.

`GET /users`, `GET /resources` e `GET /calendars` (listagem) foram adicionados no início da Fase 3: antes só existia leitura por id (ou, no caso de usuário, só `GET /users/me`), o que é suficiente para uma API consumida via Swagger/curl mas não para um frontend montar um seletor (`manager_id` ao criar projeto, `user_id`/`calendar_id` ao criar recurso, etc.) sem o usuário saber o id de cor.

## Tipo de tarefa e aprovação do cliente

Toda tarefa tem um `task_type` (`MANAGEMENT` ou `CONSULTING`, padrão `CONSULTING`), usado para separar o consumo das horas vendidas por gestão das horas vendidas por consultoria (ver seção financeira abaixo).

Independentemente do `status` de execução da tarefa (`NOT_STARTED`/`IN_PROGRESS`/`COMPLETED`/`DELAYED`), existe um segundo campo, `client_approval_status`, para o fluxo de validação pelo lado do cliente — uma tarefa pode estar `COMPLETED` e ainda não ter sido aprovada pelo cliente:

- `NOT_REQUIRED` (padrão) → `POST /tasks/{id}/submit-for-approval` (quem tem acesso de escrita na tarefa) → `PENDING`.
- `PENDING` → `PATCH /tasks/{id}/client-approval` com `{"status": "APPROVED"}` ou `{"status": "REJECTED", "comment": "..."}`, feito por `CLIENT_PM` ou `CLIENT_USER` do cliente do projeto. `CLIENT_USER` é somente-leitura em todo o resto da API, mas validar a própria tarefa é a razão desse perfil existir.
- `REJECTED` pode ser resubmetido (`submit-for-approval` de novo), reiniciando o ciclo.

## Migrações de banco (Alembic)

O projeto usa Alembic para controlar o schema do banco. A migração inicial (`alembic/versions/0001_initial_schema.py`) delega para `Base.metadata.create_all`/`drop_all` — a mesma definição de `app/models.py` já usada pelos testes — em vez de DDL escrito à mão tabela por tabela.

```bash
# Dentro do container da API (ou de um venv com requirements-dev.txt instalado):
docker compose exec api alembic upgrade head
# ou, em desenvolvimento local sem Docker:
alembic upgrade head
```

Isso é seguro tanto para uma instalação nova quanto para um banco que já existia antes do Alembic (criado pelo `init_db()` automático no startup da API): `create_all` só cria tabelas que ainda não existem, então rodar `alembic upgrade head` num banco já populado apenas registra a versão atual na tabela `alembic_version`, sem recriar nada. O `init_db()` no startup continua rodando por conveniência (principalmente para o fallback SQLite e para os testes), mas a partir de agora **qualquer alteração de schema deve virar uma nova revisão Alembic**:

```bash
alembic revision --autogenerate -m "descrição da mudança"
alembic upgrade head
```

`create_all` nunca altera uma tabela que já existe (não adiciona/remove coluna, não muda tipo, não cria índice novo em tabela existente) — por isso, sem uma migração real, uma mudança em `app/models.py` feita depois da primeira instalação simplesmente não chegaria ao banco de produção. A partir da `0002` isso já vale na prática: é a primeira migração com DDL de verdade (`op.add_column`/`op.alter_column`), em vez de delegar para `create_all` como a baseline `0001`.

## Valor vendido do projeto (horas de gestão × consultoria)

`Project.sold_value` não é mais um campo de entrada — é sempre calculado como `management_hours × management_rate + consulting_hours × consulting_rate`, recalculado a cada `POST /projects` ou `PATCH /projects/{id}` que toque qualquer um desses quatro campos. Perfis externos (`CLIENT_PM`/`CLIENT_USER`) não podem alterá-los (o valor enviado é silenciosamente ignorado, mesmo padrão já usado para `sold_value` antes desta mudança) nem vê-los na resposta de `GET /projects/{id}`.

Cada tarefa tem um `task_type` (acima) que indica se ela consome a bolsa de horas de gestão ou de consultoria — a apuração de quanto de cada bolsa já foi consumido está em `GET /projects/{id}/report` (`financials_by_task_type`, ver seção de relatórios abaixo).

## Calendário do recurso

`POST /resources` aceita um `calendar_id` opcional, vinculando o recurso (consultor/PM) a um calendário próprio de dias úteis/feriados — junto com o custo interno, a taxa de faturamento e a capacidade diária já existentes, fica reunido num único cadastro o "perfil completo" do recurso.

## Apontamento avulso

`POST /timesheets` aceita `task_id` opcional (era obrigatório). Três modos:

- **Vinculado a uma tarefa** (`task_id` informado): comportamento de sempre — exige `TaskAssignment` prévio, projeto `ACTIVE`, e bloqueia duplicidade por recurso+tarefa+data.
- **Avulso vinculado a um projeto** (`project_id` informado, sem `task_id`): não exige alocação prévia, mas ainda exige acesso de escrita ao projeto e projeto `ACTIVE`. Entra no custo real do projeto (`project_financials`) e aparece em `GET /timesheets?project_id=`.
- **Hora administrativa** (nem `task_id` nem `project_id`): qualquer recurso autenticado pode lançar, sem checagem de escopo de cliente — não é alocada a projeto nenhum.

## Relatórios e dashboard (Fase 2)

Endpoints somente-leitura que agregam dados já existentes — nenhum deles grava nada novo no banco. Todos respeitam o mesmo isolamento por `client_id`/`require_project_access` do resto da API: perfil externo só vê o(s) projeto(s) do próprio cliente, e nunca vê dado financeiro (`financials`, `financials_by_task_type`, `margin`, ROI).

| Endpoint | O que traz |
|---|---|
| `GET /dashboard` | Visão de portfólio: contagem de projetos por status, tarefas por status/tipo, tarefas atrasadas, progresso médio, e a lista `portfolio` (uma linha por projeto). |
| `GET /reports/portfolio` | Só a lista "uma linha por projeto" do dashboard (status, % concluído, tarefas restantes, margem, próximo marco) — útil quando só isso é preciso, sem o resto do payload do dashboard. Aceita `client_id` (perfis internos). |
| `GET /projects/{id}/report` | Relatório do projeto: % concluído (ponderado por `estimated_hours`, não média simples entre tarefas), tarefas restantes, `financials` (Budget vs Actual, igual a `ProjectDetail.financials`), `financials_by_task_type` (quebra GESTÃO/CONSULTORIA/ADHOC) e `burndown`. |
| `GET /resources/utilization` | Carga de trabalho por recurso: capacidade do período (dias úteis do calendário pessoal × capacidade diária), horas realmente apontadas no período, e horas alocadas (total de `TaskAssignment`, não filtrado por período — ver ressalva abaixo). Aceita `start`/`end` (padrão: mês corrente) e `resource_id`. Restrito a `ADMIN`/`INTERNAL_PM`/`CONSULTANT`. |
| `GET /projects/{id}/risks/matrix` | Grade probabilidade × impacto (contagem por célula) e a lista de riscos `HIGH`/`HIGH` ainda não `CLOSED`. |
| `GET /reports/velocity` | Horas entregues por semana ou mês (`granularity=week\|month`), opcionalmente filtradas por `project_id` e/ou `resource_id`. Sem `project_id`, é uma métrica de portfólio — perfil externo é obrigado a informar um `project_id` do próprio cliente. Padrão: últimos 90 dias. |
| `GET /reports/roi` | `sold_value`, `real_cost` e `roi_percentage` por projeto (ou de todos, sem `project_id`). Restrito a `ADMIN`/`INTERNAL_PM`. |
| `GET /projects/{id}/gantt` | Tarefas (ordenadas por WBS) + dependências do projeto num único payload, pronto para desenhar um Gantt sem N chamadas separadas. |

Três decisões de design que valem registrar:

- **Burndown sem snapshot diário**: `project_burndown` calcula a série sob demanda a partir dos dados atuais, em vez de gravar um snapshot por dia. "Planejado" assume que cada tarefa consome 100% da sua `estimated_hours` exatamente em `planned_end_date`; "realizado" é o acumulado de `Timesheet.hours_spent` (excluindo `REJECTED`) até cada data amostrada semanalmente entre o início e o fim do projeto. Mais simples e nunca fica dessincronizado dos dados reais — um snapshot congelado continua possível via `Baseline` (`snapshot_data`), se algum dia for preciso comparar contra um plano histórico específico em vez do plano atual.
- **ROI = margem ÷ custo real**: não há uma receita externa própria a medir além do valor vendido do pacote (`sold_value`), então o ROI aqui é o retorno sobre o custo efetivamente incorrido no projeto — a leitura mais direta possível com os dados hoje modelados. `None` quando ainda não há custo real lançado.
- **"Velocity" é literal**: horas entregues por semana/mês, confirmado com o usuário como a definição desejada — não é velocidade de Scrum/story points, e o sistema não modela nenhuma entidade de sprint.

E uma ressalva conhecida: `TaskAssignment` não tem data própria neste modelo, então `allocated_hours` em `GET /resources/utilization` é o total alocado ao recurso em todas as tarefas, não o alocado especificamente dentro de `[start, end]` — só `capacity_hours` e `actual_hours` são de fato escopados ao período pedido.

## Auditoria

Toda criação/atualização de projeto, tarefa, timesheet e mudança de status de solicitação de mudança grava uma entrada em `audit_logs` (quem fez, o quê, quando, e em qual registro — não um diff campo-a-campo completo, apenas os nomes dos campos alterados). Consulte pela API:

```bash
curl "http://localhost:3035/audit-log?entity_type=task&entity_id=<id>" \
  -H "Authorization: Bearer <access_token>"
```

Restrito a `ADMIN` e `INTERNAL_PM` — é informação operacional interna sobre quem alterou o quê, não algo exposto a `CONSULTANT` nem aos perfis de cliente.

## Rate limiting

Um rate limiting básico por cliente (janela deslizante em memória, chave por header `Authorization` quando presente, senão por IP) está disponível mas **desativado por padrão** — não há custo nem risco de bloquear tráfego legítimo até ser explicitamente ligado:

```bash
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

O estado do contador vive na memória do processo da API: cada worker/réplica conta de forma independente, então isto é uma primeira barreira contra abuso vindo de uma única origem, não uma solução distribuída (para isso, um proxy/API gateway com um backend compartilhado como Redis é o caminho recomendado). Requisições acima do limite recebem `429 Too Many Requests`.

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

A função `project_financials` calcula o custo real como horas apontadas multiplicadas pelo custo interno do recurso (incluindo apontamentos avulsos alocados ao projeto via `project_id`, não só os vinculados a uma tarefa), acrescidas das despesas do projeto, excluindo timesheets rejeitados (`PENDING` e `APPROVED` entram no custo real). A margem é calculada como `sold_value - real_cost`, e `sold_value` por sua vez vem de `management_hours × management_rate + consulting_hours × consulting_rate` (seção própria acima).

Perfis `CLIENT_PM` e `CLIENT_USER` só acessam projetos cujo `client_id` seja igual ao seu próprio; para esses perfis, a resposta de `GET /projects/{id}` omite `sold_value`, `financials` e os quatro campos de horas/taxa. Dentro do escopo do cliente, `CLIENT_PM` pode escrever (criar tarefas, riscos, mudanças, despesas) e validar tarefas (`client-approval`); `CLIENT_USER` é somente leitura em tudo, exceto validar tarefas — que é a própria razão desse perfil existir. Perfis internos (`ADMIN`, `INTERNAL_PM`, `CONSULTANT`) têm acesso de leitura e escrita a qualquer projeto.

Um apontamento de horas vinculado a uma tarefa (`POST /timesheets` com `task_id`) só é aceito se: o projeto estiver `ACTIVE`; o usuário autenticado tiver um `Resource` cadastrado; e esse recurso estiver alocado à tarefa via `TaskAssignment`. Não é permitido mais de um apontamento do mesmo recurso, na mesma tarefa, na mesma data. Apontamentos avulsos (sem `task_id`) dispensam a alocação prévia — ver seção própria acima.

`tasks.is_critical_path` é um campo gravável manualmente (`PATCH /tasks/{id}`), não calculado automaticamente por um motor de caminho crítico (CPM forward/backward pass) — `GET /projects/{id}/gantt` devolve o valor como está armazenado. Calcular o caminho crítico de verdade é uma extensão natural de `reschedule_cascade`, mas fica fora do escopo desta fase de relatórios.

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

Antes de produção, considere rotação de chave JWT/refresh tokens e observabilidade (logs estruturados, métricas), além de expandir a auditoria e o rate limiting básicos já incluídos (veja as seções acima).
