# ProjmanagerPy — frontend (Fase 3, MVP)

SPA em React (Vite + Tailwind CSS v4, sem TypeScript) que consome a API do
ProjmanagerPy (backend em `../app`). Esta é a primeira leva da Fase 3 —
escopo combinado com o usuário: **login, dashboard, portfólio, cadastros
(clientes, usuários/recursos, calendários, projetos/tarefas) e um Gantt
básico**. Kanban, apontamento de horas e as telas dos relatórios mais
avançados (velocity, ROI, matriz de riscos, burndown) ficam para a próxima
leva — os endpoints já existem na API (Fase 2), só faltam as telas.

## Rodando localmente

Pré-requisito: a API precisa estar rodando (veja o README na raiz do
repositório) e com CORS liberado para a origem do Vite — defina, no
ambiente da API:

```bash
export CORS_ORIGINS="http://localhost:5173"
```

Depois:

```bash
cd frontend
cp .env.example .env   # ajuste VITE_API_BASE_URL se a API não estiver em localhost:8000
npm install
npm run dev
```

Abre em `http://localhost:5173`. Não existe usuário de exemplo — crie o
primeiro ADMIN pelo `scripts/seed_admin.py` da API (veja o README na raiz)
e faça login com ele.

`npm run build` gera o build de produção em `dist/`; sirva com qualquer
servidor de arquivos estáticos, apontando `VITE_API_BASE_URL` (em tempo de
build) para a URL pública da API.

## Rodando via Docker (deploy)

Este diretório tem um `Dockerfile` (build multi-stage: compila com Node e
serve o resultado com nginx) e um `nginx.conf` com fallback de SPA. Ele é
consumido pelo serviço `web` do `docker-compose.yml` na raiz do repositório
— não precisa rodar nada manualmente aqui: `docker compose up -d --build`
na raiz já builda e sobe o frontend junto com a API e o banco. Veja o README
da raiz (seção "Instalação com Docker e PostgreSQL") para as variáveis
`VITE_API_BASE_URL`, `WEB_PORT` e `CORS_ORIGINS` que precisam ser ajustadas
antes do primeiro build.

## Estrutura

```
src/
  api/         # um módulo por domínio da API (fetch wrappers finos)
  components/  # peças reutilizáveis (Table, Modal, StatTile, CategoryBars, ...)
  context/     # AuthContext (login/logout/usuário atual)
  pages/       # uma página por rota
  utils/       # formatação (moeda/data/percentual) e labels/cores fixas dos enums
```

`src/api/client.js` centraliza a chamada HTTP: anexa o Bearer token
(guardado em `localStorage`), decodifica erros da API (`detail` do
FastAPI) numa mensagem legível, e desloga automaticamente num 401.

## Decisões de escopo desta leva

- **Sem TypeScript.** Preferiu-se JavaScript puro para este primeiro corte
  — reduz a superfície de configuração (sem `tsconfig`, sem tipos a manter
  sincronizados com os schemas Pydantic) num momento em que o contrato da
  API (Fases 1 e 2) ainda pode mudar. Migrar para TS depois é incremental,
  arquivo por arquivo, se fizer sentido.
- **Sem biblioteca de gráficos.** O dashboard usa barras horizontais
  construídas à mão (`CategoryBars`) seguindo a paleta e as regras de cor
  categórica documentadas internamente (cor fixa por categoria, nunca por
  posição/ranking) — suficiente para os KPIs desta leva (tarefas por
  status/tipo) sem herdar uma dependência pesada.
- **Gantt básico, sem setas de dependência.** `GET /projects/{id}/gantt`
  já devolve as dependências; a tela mostra "N predecessora(s)" por tarefa
  em vez de desenhar as setas — desenhar dependências com precisão exige
  mais tempo de desenho/teste visual do que cabia nesta leva. `is_critical_path`
  também continua sendo um campo manual (ver README da API), não calculado.
- **Sem burndown chart no frontend ainda**, mesmo a API já expondo os dados
  (`GET /projects/{id}/report.burndown`) — é um gráfico de linha com duas
  séries ao longo do tempo, que fica para quando as telas de relatório
  avançado entrarem (junto com velocity, ROI e matriz de riscos).
- **Sem toggle manual de tema.** O modo escuro segue `prefers-color-scheme`
  do sistema operacional (os tokens de cor já têm os dois conjuntos de
  valores); um toggle manual na interface fica para depois, se for pedido.
