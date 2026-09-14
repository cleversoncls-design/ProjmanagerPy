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

## Frontend servido pelo Docker

O pacote full-stack inclui o build estático do Ledger & Field em `frontend/`, servido pelo Nginx no serviço `web`. A API permanece na porta `3035` e a interface web é publicada por padrão na porta `3036`.

Depois de extrair uma atualização no servidor, execute:

```bash
docker compose build --no-cache web api
docker compose up -d --force-recreate web api
docker compose ps
curl -I http://127.0.0.1:3036/
curl -fsS http://127.0.0.1:3035/health
```

Acesse a interface em `http://IP_DO_SERVIDOR:3036`. O bundle foi compilado com `VITE_API_BASE_URL=http://192.168.22.20:3035`. A API deve manter `CORS_ORIGINS` incluindo `http://192.168.22.20:3036`; ajuste essa variável no `.env` se o endereço do frontend for diferente.

Para liberar o frontend no firewalld:

```bash
firewall-cmd --permanent --add-port=3036/tcp
firewall-cmd --reload
```

## Atualização da tela de detalhe de projetos

A versão atual corrige o botão `Abrir projeto`. Ele navega para `/projects/{project_id}`, carrega o projeto e as tarefas pela API e mostra estados de carregamento, erro, projeto não encontrado e retorno à lista. Para instalar essa versão no servidor, extraia o pacote atualizado sobre o diretório existente e reconstrua `web` e `api`:

```bash
cd /home/ProjmanagerPy
rm -rf /tmp/projmanager-fullstack-detail
mkdir -p /tmp/projmanager-fullstack-detail
unzip -o /root/ProjmanagerPy_fullstack_detail.zip -d /tmp/projmanager-fullstack-detail
cp -aPf /tmp/projmanager-fullstack-detail/ProjmanagerPy/. /home/ProjmanagerPy/
docker compose build --no-cache web api
docker compose up -d --force-recreate web api
```

Valide a instalação com:

```bash
curl -fsS http://127.0.0.1:3035/health
curl -I http://127.0.0.1:3036/
```

A interface fica disponível em `http://IP_DO_SERVIDOR:3036`. Após autenticar, abra `Projetos`, clique em `Abrir projeto` e confirme que a URL muda para `/projects/{project_id}` e que a EAP é carregada. Perfis externos visualizam tarefas, mas o botão de nova tarefa permanece bloqueado.

## Primeiro administrador e smoke test autenticado

Para criar ou atualizar o primeiro administrador sem colocar a senha no código, execute o script abaixo dentro do servidor. Ele solicita os dados de forma interativa, gera hash PBKDF2 dentro do container da API e grava somente o hash no PostgreSQL:

```bash
chmod +x scripts/criar_admin.sh
./scripts/criar_admin.sh
```

Depois de criar o usuário, valide login JWT, sessão e leitura de projetos com o smoke test. A senha é recebida como argumento apenas para uso local; não a coloque em arquivos versionados:

```bash
chmod +x scripts/smoke_authenticated.sh
./scripts/smoke_authenticated.sh http://127.0.0.1:3035 admin@empresa.local 'SUA_SENHA'
```

Para evitar senha no histórico do shell, use uma sessão privada ou execute o comando imediatamente e limpe o histórico conforme a política do servidor. O teste deve ser executado no servidor ou em uma máquina que alcance `192.168.22.20:3035`.

## Login inicial do frontend

Ao abrir `http://IP_DO_SERVIDOR:3036/`, o portal exibe automaticamente a tela `Conectar à operação` quando não existe uma sessão JWT válida. Use um usuário criado por `scripts/criar_admin.sh` ou por outro procedimento administrativo. O botão `Continuar em demonstração` permite visualizar a interface sem autenticação, mas não substitui uma sessão real e não deve ser usado para operações de produção.

Após qualquer alteração no frontend, copie o novo pacote full-stack, reconstrua o serviço `web` e valide a tela de login:

```bash
docker compose build --no-cache web
docker compose up -d --force-recreate web
curl -I http://127.0.0.1:3036/
```

## Publicação e atualização da API completa

Quando o servidor tiver permissão de escrita no GitHub, publique as alterações com:

```bash
git add app scripts Dockerfile docker-compose.yml README.md requirements.txt
git commit -m "Update project operations API"
git push origin main
```

No servidor, atualize por Git e reconstrua os serviços necessários:

```bash
git pull --ff-only origin main
docker compose build --no-cache web api
docker compose up -d --force-recreate web api
```

Quando o servidor não tiver credenciais GitHub, use o pacote ZIP entregue pela sessão: transfira-o para `/root`, extraia em `/tmp`, copie com `cp -aPf` sobre `/home/ProjmanagerPy` e execute os mesmos comandos de build e `up`. Em ambas as alternativas, preserve o `.env` local e nunca execute `docker compose down -v` durante uma atualização normal.

## Atualização usando a pasta Descargas do servidor

Quando o pacote for baixado diretamente no servidor para `/home/resultarpy/Descargas/`, não é necessário usar `scp`. O script localiza automaticamente o ZIP full-stack mais recente, aplica os arquivos sobre `/home/ProjmanagerPy`, preserva `.env`, `.git` e o volume PostgreSQL, reconstrói os serviços `api` e `web`, aplica a migração idempotente do vínculo de calendários e valida as portas 3035 e 3036:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/atualizar_local.sh
./scripts/atualizar_local.sh
```

Para indicar um arquivo específico:

```bash
./scripts/atualizar_local.sh /home/resultarpy/Descargas/ProjmanagerPy_fullstack_auto_login_final.zip
```

Após a execução, acesse `http://192.168.22.20:3036/`. O atualizador remove a pasta `frontend` anterior antes da cópia para não deixar `index.html` ou chunks antigos no host. Se o navegador continuar exibindo o comportamento anterior, faça um recarregamento forçado (`Ctrl+F5`) ou teste em janela anônima. Não use `docker compose down -v` durante essa atualização, pois isso removeria os dados persistidos do PostgreSQL.

## Correção do script de criação do administrador

Se a execução anterior terminou com `KeyError: 'ADMIN_PASSWORD'`, substitua o script pelo pacote atualizado baixado em `/home/resultarpy/Descargas/`. O problema foi corrigido: a senha agora é encaminhada explicitamente ao processo Python dentro do container e não é impressa no terminal.

```bash
cd /home/ProjmanagerPy

rm -rf /tmp/projmanager-admin-fix
mkdir -p /tmp/projmanager-admin-fix
unzip -o /home/resultarpy/Descargas/ProjmanagerPy_admin_fix.zip -d /tmp/projmanager-admin-fix
cp -aPf /tmp/projmanager-admin-fix/ProjmanagerPy/. /home/ProjmanagerPy/

chmod +x scripts/criar_admin.sh
./scripts/criar_admin.sh
```

O script solicita nome, e-mail, senha e confirmação. Ele cria ou atualiza o administrador com papel `ADMIN` e status `ACTIVE`. Caso a execução falhe, verifique primeiro `docker compose ps` e confirme que o serviço `api` está ativo. Nunca use `docker compose down -v` durante essa correção.

## Correção do fluxo Novo projeto

A versão atual do frontend corrige o botão **Novo projeto** na tela de Projetos. O botão abre o formulário operacional, pré-preenche o gerente autenticado, envia o projeto para `POST /projects` e atualiza a listagem após o retorno da API. O campo de valor vendido é opcional e assume zero quando não informado.

Para aplicar o pacote no servidor local, coloque o ZIP em `/home/resultarpy/Descargas/` e execute:

```bash
cd /home/ProjmanagerPy
./scripts/atualizar_local.sh
```

O script reconstrói os serviços `api` e `web`, preservando o volume PostgreSQL e o arquivo `.env`. Após o rebuild, abra `http://192.168.22.20:3036/`, faça login e acesse **Projetos → Novo projeto**. O formulário exige o UUID do cliente, o UUID do gerente é preenchido automaticamente para o usuário autenticado, e código e nome do projeto são obrigatórios.

A configuração do serviço web inclui `frontend/Dockerfile` e `frontend/nginx.conf`. O Nginx publica o `frontend/index.html` atualizado, aplica fallback para as rotas SPA e envia `Cache-Control: no-store` para o `index.html`, evitando que o navegador reutilize um bundle antigo após o rebuild. Os arquivos JavaScript e CSS versionados em `/assets/` permanecem com cache imutável.

### Hotfix do atualizar_local.sh

Se aparecer `linha 40: ...: comando não encontrado`, o script local foi corrompido ou ainda é uma cópia antiga. Use o pacote `ProjmanagerPy_fullstack_clientes_projetos_hotfix_v2.zip`, que contém um atualizador reescrito em shell simples e ASCII:

```bash
cd /home/ProjmanagerPy
unzip -o /home/resultarpy/Descargas/ProjmanagerPy_fullstack_clientes_projetos_hotfix_v2.zip -d /tmp/projmanager-hotfix
cp -f /tmp/projmanager-hotfix/ProjmanagerPy/scripts/atualizar_local.sh scripts/atualizar_local.sh
chmod +x scripts/atualizar_local.sh
bash -n scripts/atualizar_local.sh
./scripts/atualizar_local.sh /home/resultarpy/Descargas/ProjmanagerPy_fullstack_clientes_projetos_hotfix_v2.zip
```

## Cadastro de clientes e vínculo em projetos

Na tela **Clientes**, o botão **Novo cliente** abre um formulário próprio, separado do painel genérico de registros. O formulário persiste `code` e `legal_name` em `POST /clients`, aceita dados de contato opcionais e atualiza a lista após o sucesso. Campos opcionais vazios não são enviados, evitando conflitos de unicidade no PostgreSQL.

Na tela **Projetos**, o botão **Novo projeto** abre somente o formulário de projeto. O cliente é escolhido em uma lista carregada de `GET /clients`, e o projeto é persistido com o `client_id` selecionado. Usuários externos não recebem permissão visual para cadastrar clientes.

## Usuários, perfis e gerentes de projeto

Depois de autenticar como `ADMIN`, a navegação lateral apresenta a seção **Usuários**. Use **Novo usuário** para cadastrar nome, e-mail, senha inicial, status e um dos perfis corporativos: `ADMIN`, `INTERNAL_PM` (Gerente de projetos), `CONSULTANT` (Consultor), `CLIENT_PM` (Gerente do cliente) ou `CLIENT_USER` (Usuário do cliente).

Perfis `CLIENT_PM` e `CLIENT_USER` exigem a seleção de um cliente vinculado. O backend aceita o cadastro somente para administradores, aplica hash PBKDF2 na senha e nunca retorna `password_hash`. Perfis externos não podem listar ou cadastrar usuários.

Ao abrir **Projetos → Novo projeto**, o campo **Gerente do projeto** é uma lista carregada de `/users/managers` e contém apenas usuários ativos com perfil `ADMIN`, `INTERNAL_PM` ou `CONSULTANT`. O projeto é criado com o `manager_id` selecionado; a resposta também apresenta `manager_name` para facilitar a conferência no cartão e no detalhe do projeto.

O fluxo recomendado para um novo projeto é:

```text
1. Clientes → Novo cliente
2. Usuários → Novo usuário → Gerente de projetos
3. Projetos → Novo projeto
4. Selecionar o cliente
5. Selecionar o gerente do projeto
6. Informar código e nome
7. Salvar registro
```

Para alterar o gerente de um projeto existente, abra o projeto, clique em **Editar projeto**, mantenha ou altere o nome/status e selecione outro usuário no campo **Gerente do projeto**. A lista mostra somente usuários internos elegíveis. Ao salvar, a API executa `PATCH /projects/{project_id}` com o novo `manager_id`, valida que o usuário está ativo e atualiza o nome do gerente no detalhe e no cartão da lista.

A criação de usuários e projetos, assim como a alteração do gerente, também é protegida no backend. Mesmo que um perfil externo tente chamar diretamente os endpoints, `/users`, `/users/managers`, `POST /projects` e o `PATCH /projects/{project_id}` rejeitam a operação conforme o papel e o escopo do usuário.

## Configuração de HTTPS e Segurança

Para expor o portal fora da rede local ou usar em produção, é obrigatório configurar HTTPS. O serviço `web` atual serve arquivos estáticos por HTTP na porta 3036. Recomenda-se o uso de um proxy reverso (Nginx ou Traefik) no host ou em um container adicional para gerenciar certificados SSL (Let's Encrypt).

Ao habilitar HTTPS, atualize o arquivo `.env` no servidor:
1. Altere `VITE_API_BASE_URL` para o endereço `https://` público da API.
2. Atualize `CORS_ORIGINS` para incluir o domínio `https://` do frontend.
3. Reconstrua o serviço `web` com `./scripts/atualizar_local.sh` para que o bundle do frontend aponte para o novo endpoint seguro.

## Calendários, feriados e recursos

A tela **Calendários** do frontend permite criar jornadas com qualquer combinação de segunda-feira a domingo. Informe o nome, marque os dias e clique em **Criar calendário**; após a confirmação da API, o calendário é selecionado automaticamente e o bloco **Feriados e folgas adicionais** aparece no mesmo editor. Cada calendário pode receber feriados ou folgas adicionais; essas datas são persistidas em `holidays` e tratadas como não trabalhadas pelo `BusinessCalendar`. Em caso de falha da API, o erro é mostrado junto ao formulário.

Recursos internos podem ser vinculados a um calendário próprio. A capacidade individual é calculada pela quantidade de dias úteis do calendário multiplicada pela capacidade diária do recurso. Quando `calendar_id` estiver vazio, a API usa o padrão de segunda a sexta-feira. O custo interno e a taxa de faturamento permanecem disponíveis somente para perfis internos.

A migração para instalações existentes é idempotente e adiciona `resources.calendar_id` com `ON DELETE SET NULL`, sem apagar recursos ou calendários:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/migrar_calendarios.sh
./scripts/migrar_calendarios.sh
```

O atualizador completo já executa essa migração automaticamente depois de reconstruir `api` e `web`:

```bash
cd /home/ProjmanagerPy
./scripts/atualizar_local.sh /home/resultarpy/Descargas/ProjmanagerPy_fullstack_calendar.zip
```

Os endpoints protegidos são `GET/POST/PATCH/DELETE /calendars`, `POST /calendars/{calendar_id}/holidays`, `DELETE /holidays/{holiday_id}`, `GET/POST/PATCH/DELETE /resources` e `GET /resources/{resource_id}/availability`. Perfis `CLIENT_PM` e `CLIENT_USER` recebem `403` e não conseguem consultar jornadas, feriados, custos ou disponibilidade interna.

Para validar o ambiente real após o rebuild, use o smoke test específico. Ele cria uma jornada, um feriado e um recurso temporários, verifica a disponibilidade de 3 a 9 de agosto de 2026 e remove os registros ao final:

```bash
chmod +x scripts/smoke_calendar_authenticated.sh
./scripts/smoke_calendar_authenticated.sh http://127.0.0.1:3035 admin@empresa.local 'SUA_SENHA'
```

O resultado esperado contém `client persisted in list`, `project persisted in list`, `resource linked`, `availability validated`, `resource calendar switched and persisted` e a confirmação final de que os registros temporários foram removidos.

## Correção da edição de projetos

Ao abrir **Gerenciar dados → Editar projeto**, o frontend consulta o projeto atual e preenche nome, status e gerente antes da submissão. Assim, a alteração do gerente ou do status não apaga o nome existente, e o salvamento pode ser feito sem redigitar o valor anterior.


## Entrega v8 — EAP/EDT, recursos múltiplos e indicadores EVM

A atualização v8 integra o frontend Ledger & Field ao módulo avançado de tarefas. A tela **Tarefas** organiza a EAP/EDT em árvore com WBS, permite escolher tarefa pai, atribuir múltiplos recursos internos ou do cliente, cadastrar predecessoras e acompanhar trabalho, duração, datas previstas, percentual previsto, percentual realizado, linha de base e observações.

O motor de agendamento usa o calendário associado ao recurso quando disponível e ignora finais de semana e feriados cadastrados. Alterações em predecessoras recalculam as sucessoras conforme o tipo FS, FF, SS ou SF e a defasagem. Os dados de início real, término real e horas reais são derivados dos timesheets. SPI e CPI são exibidos na grade e calculados a partir do planejamento, avanço, valor agregado, custos internos e horas apontadas, conforme os dados existentes.

As colunas da grade podem ser ocultadas pelo botão **Colunas**. A opção **Real / apontado** mostra início real, término real e horas reais sem transformar esses campos em edição manual. A grade possui rolagem horizontal para preservar a leitura em desktop e em telas estreitas.

Para instalar o pacote v8 baixado em `/home/resultarpy/Descargas/`, execute no servidor:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/atualizar_local.sh
./scripts/atualizar_local.sh /home/resultarpy/Descargas/ProjmanagerPy_fullstack_eap_v8.zip
docker compose ps
curl -fsS http://127.0.0.1:3035/health
curl -I http://127.0.0.1:3036/
```

O script reconstrói `api` e `web`, aplica as migrações idempotentes de calendários e tarefas avançadas e preserva o volume `postgres_data`. Não execute `docker compose down -v` durante uma atualização normal. Depois do rebuild, acesse `http://IP_DO_SERVIDOR:3036/`, faça login e valide a sequência pai → filha → múltiplos recursos → predecessor → timesheet → coluna de realizado/SPI/CPI.


## Moeda configurável por projeto

A entidade `Project` possui o campo `currency`, representado pelo enum `ProjectCurrency` com os valores `USD` (Dólar) e `PYG` (Guarani). O campo é aceito em `POST /projects`, pode ser alterado em `PATCH /projects/{project_id}` e é devolvido nas respostas de projeto. Projetos existentes recebem `USD` como padrão durante a migração.

O valor `sold_value`, os custos e a margem permanecem armazenados como valores numéricos; a moeda identifica a unidade monetária do projeto e não realiza conversão cambial. A API continua omitindo `sold_value` e `financials` para `CLIENT_PM` e `CLIENT_USER`.

Para aplicar a alteração em um servidor PostgreSQL já instalado, o atualizador executa automaticamente:

```bash
chmod +x scripts/migrar_moedas_projetos.sh
./scripts/migrar_moedas_projetos.sh
```

A migração é idempotente, cria o tipo ENUM `projectcurrency`, adiciona `projects.currency` com padrão `USD`, normaliza valores nulos e cria uma restrição que impede qualquer moeda fora de `USD` e `PYG`. Não remova o volume PostgreSQL durante o procedimento.


## WBS e campos derivados da tarefa

O backend trata `wbs_code` como identificador derivado da posição na hierarquia. Depois de criar, mover, editar ou excluir uma tarefa, `normalize_task_hierarchy` renumera os irmãos e recalcula a árvore do projeto. O valor manual enviado em `TaskCreate.wbs_code` ou `TaskPatch.wbs_code` é ignorado para evitar inconsistências entre a EAP exibida e os relacionamentos `parent_task_id`.

Para tarefas com filhos, `estimated_hours` é a soma recursiva das horas das folhas. O pai recebe o menor `planned_start_date`, o maior `planned_end_date` e uma nova `duration_days` contada em dias úteis pelo calendário aplicável. Se os filhos ainda não tiverem datas, a duração é estimada pela referência de oito horas úteis por dia, sem inventar datas. Tarefas sem filhos continuam aceitando alteração de horas, duração e datas; ao virar pai, seus campos passam a ser recalculados.

`observation` permanece opcional. O fluxo de apontamentos, EVM e permissões continua preservado; os campos reais são derivados dos timesheets e as informações financeiras sensíveis permanecem protegidas para perfis externos.


## Edição de tarefas e duração automática

A grade EAP possui a ação **Editar tarefa** em cada linha. O editor permite alterar nome, descrição, status, tarefa pai, prioridade, tipo, horas planejadas, data inicial, predecessor, tipo de dependência, defasagem, observação e múltiplos recursos. A troca de predecessor remove as dependências anteriores da tarefa e cria a nova relação, mantendo o recálculo da cascata protegido no backend. O WBS não é aceito como valor manual: após criar ou mover uma tarefa, a API renumera a árvore como `1`, `1.1`, `1.2` e assim por diante.

Os dias úteis previstos são derivados das horas planejadas e da capacidade diária dos recursos associados. A capacidade da tarefa é a soma das capacidades diárias dos recursos selecionados; sem recurso, o padrão é 8 horas por dia. O resultado usa arredondamento para cima e mínimo de um dia: 1 hora resulta em 1 dia, 8 horas em 1 dia e 9 horas em 2 dias. As datas planejadas continuam respeitando o calendário do recurso, seus feriados e os finais de semana. Para tarefas pai, horas, duração e intervalo de datas são consolidados recursivamente a partir das tarefas filhas.

Durante uma atualização, o atualizador local aplica o código e reconstrói API e frontend sem remover o volume PostgreSQL:

```bash
cd /home/ProjmanagerPy
./scripts/atualizar_local.sh /home/resultarpy/Descargas/ProjmanagerPy_fullstack_task_edit_v11.zip
```


## Ajustes de agenda e alocação — v12

O cadastro e a edição de tarefas calculam `duration_days` automaticamente a partir de `estimated_hours` e da capacidade diária dos recursos associados. A fórmula é `máximo(1, teto(horas / capacidade diária))`; portanto, 1 hora ocupa 1 dia útil, 8 horas ocupam 1 dia útil e 9 horas com capacidade de 8 horas por dia ocupam 2 dias úteis. Sem recurso associado, a capacidade padrão é de 8 horas por dia.

A criação de tarefa pode receber `predecessor_task_id`, `dependency_type` e `lag_days` no mesmo `POST /tasks`. A dependência é persistida na mesma transação e a data inicial/final da sucessora é recalculada conforme o calendário, fins de semana, feriados e o tipo FS, FF, SS ou SF. A edição continua permitindo trocar predecessor, tipo e defasagem.

No frontend, a carga de trabalho informada é replicada para cada recurso selecionado. O WBS permanece automático e os campos derivados não devem ser editados manualmente.


## Operação local sem conexões externas

A aplicação não depende de conexões externas para funcionar na rede local. O serviço `api` atende na porta 3035, o `web` atende na porta 3036 e o PostgreSQL permanece no volume Docker `postgres_data`. O frontend distribuído deve apontar para o endereço local da API por meio de `VITE_API_BASE_URL` gravado no build.

HTTPS não é obrigatório para a instalação interna em HTTP. Quando a empresa possuir um certificado interno, a terminação TLS pode ser adicionada na frente do serviço `web` por Nginx, proxy reverso ou balanceador corporativo, sem alterar o banco ou a API. Não foram incluídos certificados autoassinados no pacote, pois eles exigem distribuição da autoridade certificadora aos computadores clientes.

Para validar a instalação sem acesso externo, use o script incluído:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/validar_local.sh
./scripts/validar_local.sh
```

O script verifica `docker compose ps`, `GET /health`, os cabeçalhos do frontend e a presença do bundle JavaScript. Para endereços diferentes, informe `API_URL`, `WEB_URL` e `PROJECT_DIR` como variáveis de ambiente.


## Backup local do PostgreSQL

O pacote inclui `scripts/backup_postgres.sh`, que executa `pg_dump` dentro do container `db`, grava um arquivo `.sql.gz` com permissão restrita em `/home/ProjmanagerPy/backups` e remove backups com mais de 14 dias por padrão. O banco não é exposto na rede; o backup é executado localmente no host Docker.

Para executar um backup manual e verificar a integridade:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/backup_postgres.sh
./scripts/backup_postgres.sh
gzip -t backups/projmanager_*.sql.gz
```

Para instalar uma execução diária às 02:00, use o script de cron como root:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/configurar_backup_cron.sh scripts/backup_postgres.sh
./scripts/configurar_backup_cron.sh
cat /etc/cron.d/projmanager-postgres-backup
```

Para alterar o horário para 23:30 e manter 30 dias de retenção:

```bash
CRON_SCHEDULE='30 23 * * *' RETENTION_DAYS=30 ./scripts/configurar_backup_cron.sh
```

Antes de uma restauração, preserve uma cópia dos arquivos existentes. Para restaurar um backup em uma base controlada, pare a API, descompacte o arquivo e envie o SQL ao PostgreSQL:

```bash
docker compose stop api
gunzip -c backups/arquivo.sql.gz | docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
docker compose start api
```

O arquivo de cron usa o horário configurado no servidor. O script de backup não envia arquivos para serviços externos.

## Validação local após atualização

```bash
cd /home/ProjmanagerPy
chmod +x scripts/validar_local.sh
./scripts/validar_local.sh
```


Para simular uma restauração sem alterar a base operacional, use o restaurador temporário. Ele cria um banco separado, restaura o backup com `ON_ERROR_STOP=1`, conta as tabelas públicas e remove o banco ao final:

```bash
cd /home/ProjmanagerPy
chmod +x scripts/testar_restauracao_homologacao.sh
./scripts/testar_restauracao_homologacao.sh
```

Para preservar o banco temporário e inspecioná-lo manualmente, use `KEEP_DB=1`; remova-o depois com `dropdb` dentro do container `db`.


### HTTPS opcional com Nginx

O pacote contém `deploy/nginx/projmanager-https.conf.example`. Depois que a equipe disponibilizar um certificado interno e a resolução DNS ou `/etc/hosts` para `projetos.empresa.local`, copie o modelo, ajuste o nome e os caminhos dos arquivos `.crt` e `.key`, valide a configuração e recarregue o Nginx:

```bash
install -D -m 0644 deploy/nginx/projmanager-https.conf.example /etc/nginx/conf.d/projmanager.conf
nginx -t
systemctl reload nginx
```

Não habilite esse exemplo com caminhos ou certificados inexistentes. O redirecionamento de HTTP para HTTPS só deve ser ativado depois que o acesso HTTPS for validado a partir de uma estação cliente da rede.


## Correção de tarefas: exclusão e predecessor

A grade **Cronograma operacional** agora exibe ações de editar e excluir para usuários internos autenticados. Uma tarefa pode ser excluída somente quando não possui apontamentos e não possui atividades filhas; essa regra é validada no backend, com resposta HTTP `409` e mensagem explicativa quando a exclusão não é permitida. A remoção de uma tarefa sem apontamentos recalcula a numeração WBS/EDT das demais tarefas do projeto. Perfis externos não recebem a ação de exclusão.

No formulário de criação e no editor de tarefas, a ordem operacional é **Tarefa pai → Predecessor → Tipo de dependência → Defasagem → Prioridade**. Ao selecionar uma predecessora, a data inicial prevista passa a ser somente leitura e é recalculada conforme o tipo `FS`, `FF`, `SS` ou `SF`, a defasagem e os dias úteis. A mesma regra é aplicada no backend ao criar ou editar a dependência; portanto, a API permanece a autoridade mesmo que a interface seja chamada diretamente.

Para aplicar a atualização no servidor local:

```bash
cd /home/ProjmanagerPy
./scripts/atualizar_local.sh /home/resultarpy/Descargas/ProjmanagerPy_fullstack_task_delete_predecessor_v15.zip
./scripts/validar_local.sh
```

Após autenticar, abra **Cronograma**, selecione o projeto e use o ícone de lixeira em uma tarefa sem apontamentos. A exclusão solicita confirmação. Em uma tarefa com apontamentos ou atividades filhas, o botão permanece desabilitado e a API também rejeita a operação. Para verificar a data calculada, selecione uma predecessora com datas planejadas; em uma dependência `FS` sem defasagem, a sucessora começa no próximo dia útil após o término da predecessora.
