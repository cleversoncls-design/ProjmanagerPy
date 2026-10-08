import { translate } from '../i18n/translations'

export const ROLE_LABELS = {
  ADMIN: 'Administrador',
  INTERNAL_PM: 'Gerente de projetos',
  CONSULTANT: 'Consultor',
  CLIENT_PM: 'PM do cliente',
  CLIENT_USER: 'Usuário-chave',
  // Pedido do usuário: acessos equivalentes ao Administrador, exceto
  // cadastrar/editar/excluir usuário (ver ADMIN_LIKE_ROLES/MANAGEMENT_ROLES/
  // INTERNAL_ROLES abaixo e app/deps.py no backend).
  SERVICE_MANAGER: 'Gerente de Serviços',
  GENERAL_DIRECTOR: 'Diretor Geral',
}

// Função (categoria) e Nível (senioridade) do Recurso (pedido do usuário,
// "melhorias parte 4") — substituem o antigo campo de texto livre
// "role_title". Dois campos independentes (ver app/models.py
// ResourceFunction/Resource.level): RESOURCE_LEVEL_LABELS usa as chaves 1 a
// 4 (número simples, não um enum — permite comparação >= direta no filtro
// de "Nível mínimo" da tarefa, ver resourceFunctionLevelLabel abaixo e o
// filtro de recursos em ProjectDetailPage.jsx).
export const RESOURCE_FUNCTION_LABELS = {
  CONSULTANT: 'Consultor',
  DEVELOPER: 'Desenvolvedor',
  SPECIALIST: 'Especialista',
  PROJECT_MANAGER: 'Gerente de Projetos',
}

export const RESOURCE_LEVEL_LABELS = {
  1: 'Nível 1',
  2: 'Nível 2',
  3: 'Nível 3',
  4: 'Nível 4',
}

// Onde a tarefa pode ser executada (pedido do usuário, "melhorias parte
// 5") — campo puramente informativo (ver app/models.py TaskModality), sem
// nenhuma validação/filtro associado.
export const TASK_MODALITY_LABELS = {
  REMOTE: 'Remotamente',
  ON_SITE: 'Presencial',
  BOTH: 'Ambos',
}

// Gerente de Serviços/Diretor Geral (pedido do usuário) têm acessos
// equivalentes ao Administrador, exceto cadastrar/editar/excluir usuário —
// por isso entram em todo grupo abaixo que já incluía ADMIN, espelhando
// MANAGEMENT_ROLES/INTERNAL_ROLES/ADMIN_LIKE_ROLES do backend
// (app/deps.py). A única exceção (tela de Usuários em si, não a de
// Recursos) é tratada dentro de UsersPage.jsx, não aqui.
export const MANAGEMENT_ROLES = ['ADMIN', 'INTERNAL_PM', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR']
export const INTERNAL_ROLES = ['ADMIN', 'INTERNAL_PM', 'CONSULTANT', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR']

// --- Menu por perfil (pedido do usuário: Administrativo / Gerentes de
// Projetos / Consultores) — MANAGEMENT_ROLES/INTERNAL_ROLES acima continuam
// valendo pra quem PODE ESCREVER em cada tela (criar projeto/tarefa,
// aprovar apontamento etc.), que não mudou; os grupos abaixo são só pra
// decidir quais itens aparecem no menu de cada perfil. ---
// Administrador, Gerente de Serviços e Diretor Geral administram Clientes
// e Usuários — Gerente de Projetos perdeu esses dois itens do menu
// (confirmado com o usuário).
export const ADMIN_LIKE_ROLES = ['ADMIN', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR']
// Dashboard ("Painel"): só ADMIN_LIKE_ROLES. Gerente de Projetos e
// Consultor já não tinham esse item; na reorganização de menus (pedido do
// usuário) PM do Cliente também perdeu o Painel, e Usuário-chave ficou sem
// nenhum item de menu por enquanto (ver nota em ROLE_HOME_PATH abaixo) —
// mesma restrição aplicada no backend (GET /dashboard, ver
// app/routers/reports.py).
export const DASHBOARD_ROLES = ['ADMIN', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR']
// Projetos (lista + detalhe do projeto): todo mundo, menos Consultor (que
// nunca teve esse item — continua vendo Agenda de Consultores, Apontamento
// de horas e Ordens de Serviço) e Usuário-chave (reorganização de menus:
// perfil ficou sem nenhum acesso por enquanto, pedido do usuário). PM do
// Cliente mantém Projetos — único item do menu dele agora — mas sempre
// somente leitura (ver require_project_access em app/deps.py).
export const PROJECTS_VISIBLE_ROLES = ['ADMIN', 'INTERNAL_PM', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR', 'CLIENT_PM']

// Relatórios: pedido do usuário ("pode implementar os 2 modelos e colocar
// na opção de relatorios" — Status Report Interno/Cliente, depois dos
// mockups validados no canvas de design) — PM do cliente passou a ter
// acesso ao menu "Relatórios" pela primeira vez, mas só enxerga o Status
// Report do próprio projeto (ver ReportsIndexPage.jsx), nunca "Horas por
// tipo" (que continua só MANAGEMENT_ROLES — expõe horas/ausência de TODOS
// os recursos da empresa). Backend equivalente: EXTERNAL_ROLES em
// app/deps.py tem leitura normal em GET /projects/{id}/status-reports.
export const STATUS_REPORT_VISIBLE_ROLES = ['ADMIN', 'INTERNAL_PM', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR', 'CLIENT_PM']

// Menu "Conhecimento" (pedido do usuário, "NOVAS MELHORIAS": processo de
// registro de conhecimento dos consultores) — três telas, três acessos
// DISTINTOS dos de cima, exatamente como o usuário especificou (mesmos
// três conjuntos no backend, ver app/deps.py KNOWLEDGE_CATALOG_ROLES/
// KNOWLEDGE_SELF_ASSESSMENT_ROLES/KNOWLEDGE_REVIEW_ROLES). Nenhum perfil
// de cliente (EXTERNAL_ROLES) vê nada deste menu — é gestão interna de
// equipe, não dado de projeto.
export const KNOWLEDGE_CATALOG_ROLES = MANAGEMENT_ROLES
export const KNOWLEDGE_SELF_ASSESSMENT_ROLES = ['CONSULTANT', 'INTERNAL_PM']
// Revisão e Aprovação: ADMIN fica de fora de propósito (o usuário não
// listou Administrador pra esta tela) — diferente de MANAGEMENT_ROLES.
export const KNOWLEDGE_REVIEW_ROLES = ['INTERNAL_PM', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR']

// Primeira tela de cada perfil ao logar (ou ao cair em "/" depois de ser
// barrado por ProtectedRoute em alguma rota) — precisa ser uma rota que o
// próprio perfil tenha acesso, senão vira redirecionamento em loop.
//
// Reorganização de menus (pedido do usuário): Consultor perdeu Agenda de
// Consultores do menu (agora MANAGEMENT_ROLES, ver Sidebar.jsx/App.jsx),
// então sua home mudou pra Apontamento de horas. PM do Cliente perdeu o
// Painel, então cai direto em Projetos (único item que ainda tem). Usuário-
// chave ficou sem nenhum item de menu — "/no-access" é uma rota própria,
// sem checagem de `roles` (ver App.jsx/NoAccessPage.jsx), pra não virar
// loop de redirecionamento.
export const ROLE_HOME_PATH = {
  ADMIN: '/',
  INTERNAL_PM: '/projects',
  CONSULTANT: '/timesheets',
  CLIENT_PM: '/projects',
  CLIENT_USER: '/no-access',
  SERVICE_MANAGER: '/',
  GENERAL_DIRECTOR: '/',
}

export const PROJECT_STATUS_LABELS = {
  PLANNING: 'Planejamento',
  ACTIVE: 'Ativo',
  ON_HOLD: 'Em espera',
  COMPLETED: 'Concluído',
  CANCELLED: 'Cancelado',
  // Projeto-base pro botão "Copiar estrutura de outro projeto" — nunca
  // entra em indicador/dashboard (ver _scoped_projects/roi() em
  // routers/reports.py).
  MODELO: 'Modelo',
}

// Cor de status "semânfora" (good/warning/serious/critical) — reservada,
// nunca reaproveitada como cor categórica de série.
export const PROJECT_STATUS_TONE = {
  PLANNING: 'muted',
  ACTIVE: 'good',
  ON_HOLD: 'warning',
  COMPLETED: 'good',
  CANCELLED: 'critical',
  MODELO: 'muted',
}

export const TASK_STATUS_LABELS = {
  NOT_STARTED: 'Não iniciada',
  IN_PROGRESS: 'Em andamento',
  COMPLETED: 'Concluída',
  DELAYED: 'Atrasada',
  // "Desativar tarefa" (pedido do usuário) — estado final distinto de
  // COMPLETED; tradução ES em translations.js (chave "Encerrada" -> "Cerrada").
  CLOSED: 'Encerrada',
}

export const TASK_STATUS_TONE = {
  NOT_STARTED: 'muted',
  IN_PROGRESS: 'warning',
  COMPLETED: 'good',
  DELAYED: 'critical',
  CLOSED: 'muted',
}

// Classificador de tipo de projeto (lista fixa, pedido do usuário) — espelha
// `ProjectType` em app/models.py.
export const PROJECT_TYPE_LABELS = {
  FIXED_PRICE: 'Projeto Fechado',
  OPEN_HOURS: 'Projeto Horas Abertas',
  HOUR_BANK: 'Banco de Horas',
  SUPPORT: 'Sustentação',
  INTERNAL: 'Internos',
  COMMERCIAL: 'Comercial',
  INVESTMENT: 'Investimento',
}

export const TASK_TYPE_LABELS = {
  MANAGEMENT: 'Gestão',
  CONSULTING: 'Consultoria',
  // Timesheet avulso sem task_id (ver financials_by_task_type na API) não
  // tem task_type — usado só na quebra financeira do projeto, nunca em
  // Task.task_type em si.
  ADHOC: 'Avulso',
  // "Traslado" (deslocamento, pedido do usuário) — mesma ideia do ADHOC
  // acima (chave sintética, não é um TaskType de verdade), mas com bucket
  // próprio em financials_by_task_type pra separar do resto do avulso.
  TRASLADO: 'Traslado',
  // Consumo apropriado no sistema anterior (ProjectLegacyConsumption) —
  // bucket sintético de financials_by_task_type, só aparece com lançamentos.
  LEGACY: 'Consumo anterior (sistema legado)',
}

// Cor categórica fixa por entidade (nunca por posição/ranking — um filtro
// que muda a contagem não pode "repintar" quem sobrou). Mesma cor em
// qualquer tela que mostrar a mesma categoria.
export const TASK_STATUS_COLORS = {
  NOT_STARTED: 'var(--series-1)',
  IN_PROGRESS: 'var(--series-4)',
  COMPLETED: 'var(--series-3)',
  DELAYED: 'var(--series-8)',
  CLOSED: 'var(--series-5)',
}

export const TASK_TYPE_COLORS = {
  MANAGEMENT: 'var(--series-2)',
  CONSULTING: 'var(--series-1)',
}

export const APPROVAL_STATUS_LABELS = {
  NOT_REQUIRED: 'Não exigida',
  PENDING: 'Aguardando cliente',
  APPROVED: 'Aprovada',
  REJECTED: 'Rejeitada',
}

export const APPROVAL_STATUS_TONE = {
  NOT_REQUIRED: 'muted',
  PENDING: 'warning',
  APPROVED: 'good',
  REJECTED: 'critical',
}

// Versões abreviadas de TASK_STATUS_LABELS/APPROVAL_STATUS_LABELS — só pra
// caber melhor nas colunas Status/Aprovação do cliente da grade de tarefas
// (ver Table na aba Tarefas em ProjectDetailPage.jsx), que é bem apertada
// com várias colunas. Só o valor "não iniciado/não exigida" (o mais comum
// e o mais longo relativo ao espaço) é abreviado; os outros valores (Em
// andamento, Concluída, Atrasada, Aguardando cliente, Aprovada, Rejeitada)
// continuam por extenso, como pedido. Em outros lugares (dropdown de editar
// tarefa, gráfico "Tarefas por status" da Visão geral) continua usando
// TASK_STATUS_LABELS/APPROVAL_STATUS_LABELS por extenso normalmente.
// "Iniciada"/"exigida" se escrevem igual em Espanhol, então a mesma sigla
// serve pros dois idiomas sem precisar de tradução em separado.
export const TASK_STATUS_LABELS_SHORT = {
  ...TASK_STATUS_LABELS,
  NOT_STARTED: 'N/I',
}

export const APPROVAL_STATUS_LABELS_SHORT = {
  ...APPROVAL_STATUS_LABELS,
  NOT_REQUIRED: 'N/E',
}

export const WEEKDAY_LABELS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

// A cor do projeto deixou de ser uma das 8 chaves categóricas fixas — ver
// utils/colorPalette.js (PROJECT_COLOR_PALETTE, 256 cores nomeadas) e
// components/ColorListPicker.jsx.

export const USER_STATUS_LABELS = {
  ACTIVE: 'Ativo',
  INACTIVE: 'Inativo',
  BLOCKED: 'Bloqueado',
}

export const USER_STATUS_TONE = {
  ACTIVE: 'good',
  INACTIVE: 'muted',
  BLOCKED: 'critical',
}

// Status do apontamento de horas (Timesheet) — vocabulário próprio (mais
// direto que APPROVAL_STATUS_LABELS, que é sobre a validação da TAREFA
// pelo cliente, um fluxo diferente e sem relação com este).
export const TIMESHEET_STATUS_LABELS = {
  PENDING: 'Pendente',
  APPROVED: 'Aprovado',
  REJECTED: 'Rejeitado',
}

// Ausência da empresa (Timesheet.absence_type, pedido do usuário) —
// classificada igual ao "Traslado" (ver TASK_TYPE_LABELS.TRASLADO acima),
// só que sempre custo interno (sem projeto/tarefa vinculado). Decisão
// confirmada com o usuário: qualquer aprovador vê o tipo exato, sem
// mascarar por perfil — por isso um único dicionário de rótulos, sem
// variante "resumida" pra ocultar o tipo de ninguém.
export const ABSENCE_TYPE_LABELS = {
  VACATION: 'Férias',
  MEDICAL_LEAVE: 'Licença Médica',
  MATERNITY_LEAVE: 'Licença Maternidade',
  ABSENCE: 'Ausência',
  DAY_OFF: 'Folga',
}

// Classificador Normal/Retrabalho do apontamento em tarefa do projeto
// (Timesheet.work_classification, pedido do usuário) — ver
// WorkClassification em app/models.py.
export const WORK_CLASSIFICATION_LABELS = {
  NORMAL: 'Normal',
  REWORK: 'Retrabalho',
}

// Motivo(s) do retrabalho (Timesheet.rework_reasons, pedido do usuário) —
// lista fixa de múltipla escolha, ver ReworkReason em app/models.py.
export const REWORK_REASON_LABELS = {
  PRODUCT_ERROR: 'Erro de Produto',
  INITIAL_CONFIG_ERROR: 'Erro de Configuração inicial',
  DATA_LOAD_ERROR: 'Erro de dados carregados',
  USER_DELAY_OR_ABSENCE: 'Atraso / Falta de Usuários',
  ACCESS_ISSUE_SERVICE_SERVER: 'Problemas de Acesso (Serviços / Servidor)',
  ACCESS_ISSUE_NETWORK: 'Problemas de Acesso (Rede)',
  CONSULTANT_CHANGE: 'Troca de Consultor',
  POWER_OUTAGE: 'Falta de Energia Elétrica',
}

export const TIMESHEET_STATUS_TONE = {
  PENDING: 'warning',
  APPROVED: 'good',
  REJECTED: 'critical',
}

export const DEPENDENCY_TYPE_LABELS = {
  FS: 'Término → Início',
  SS: 'Início → Início',
  FF: 'Término → Término',
  SF: 'Início → Término',
}

export const DEPENDENCY_TYPE_SHORT = {
  FS: 'TI',
  SS: 'II',
  FF: 'TT',
  SF: 'IT',
}

// Bolinha de status da tarefa (ver services.task_dot_colors no backend):
// branca = por iniciar, verde = no prazo, amarela = mistura (tarefa-pai com
// filhas em status diferentes), vermelha = atrasada. Nunca comunica só por
// cor — o rótulo sempre acompanha a bolinha nos lugares em que aparece.
export const STATUS_DOT_COLORS = {
  white: '#ffffff',
  green: 'var(--status-good)',
  yellow: 'var(--status-warning)',
  red: 'var(--status-critical)',
}

export const STATUS_DOT_LABELS = {
  white: 'Por iniciar',
  green: 'No prazo',
  yellow: 'Mistura de status',
  red: 'Atrasada',
}

// Semáforo RAG do Status Report (ver RagStatus em app/models.py) — os 5
// indicadores (Prazo/Custo/Margem/Escopo/Risco) dos mockups "Interno" e
// "Cliente" validados no canvas de design.
// "No prazo" (versão anterior) só fazia sentido pro indicador Prazo —
// "Custo: No prazo"/"Margem: No prazo" não tinham sentido nenhum (bug
// visível na tela real, reportado pelo usuário). "Em dia" é neutro e
// funciona igual nos 5 indicadores (Prazo/Custo/Margem/Escopo/Risco).
export const RAG_STATUS_LABELS = {
  GOOD: 'Em dia',
  WARNING: 'Atenção',
  CRITICAL: 'Crítico',
}

export const RAG_STATUS_TONE = {
  GOOD: 'good',
  WARNING: 'warning',
  CRITICAL: 'critical',
}

// Mesmas 3 cores de RAG_STATUS_TONE/StatusPill, mas como valor `var(--...)`
// cru — usado onde o selo não serve (traço de uma barra SVG, texto de um
// número) e cor sólida (não o fundo suave de StatusPill) é o que faz
// sentido. Pedido do usuário: "os indicadores da foto" (mockup tinha barras
// de Custo/Margem coloridas pelo mesmo semáforo do badge). SÓ pra tela —
// ver RAG_STATUS_PRINT_COLOR abaixo pro equivalente da impressão.
export const RAG_STATUS_CSS_COLOR = {
  GOOD: 'var(--status-good)',
  WARNING: 'var(--status-warning)',
  CRITICAL: 'var(--status-critical)',
}

// Paleta dos gráficos do Status Report (StatusReportComparisonBar/
// BurndownChart/GanttMini — ver frontend/src/components/) em duas
// variantes. SCREEN usa `var(--...)`, acompanhando o tema claro/escuro do
// app — é o padrão de todo o resto do app (StatusPill, RAG_STATUS_CSS_COLOR
// acima etc.). PRINT usa hex fixo: a suposição original era que a folha
// impressa, por ser renderizada via portal no MESMO documento
// (`window.print()` em StatusReportsPage.jsx), herdaria as mesmas variáveis
// — só que isso se mostrou falso na prática (reportado pelo usuário com
// print da folha: todo badge/barra/linha saía sem cor nenhuma, só contorno
// preto) — aparentemente o pipeline de impressão do Chrome não resolve
// `var(--...)` (nem `color-mix()`) no documento impresso, por motivo não
// totalmente claro. Pra impressão, que é sempre fundo branco (não tem "modo
// escuro" de papel), usa-se direto os valores do tema claro de
// app/index.css — nunca dependa de `var(--...)` dentro de conteúdo que vai
// pra StatusReportPrintSheet.jsx.
export const STATUS_REPORT_CHART_COLORS_SCREEN = {
  textPrimary: 'var(--text-primary)',
  textSecondary: 'var(--text-secondary)',
  textMuted: 'var(--text-muted)',
  grid: 'var(--grid)',
  good: 'var(--status-good)',
  warning: 'var(--status-warning)',
  critical: 'var(--status-critical)',
  series1: 'var(--series-1)',
  series2: 'var(--series-2)',
  series7: 'var(--series-7)',
}

export const STATUS_REPORT_CHART_COLORS_PRINT = {
  textPrimary: '#0b0b0b',
  textSecondary: '#52514e',
  textMuted: '#898781',
  grid: '#e1e0d9',
  good: '#0ca30c',
  warning: '#fab219',
  critical: '#d03b3b',
  series1: '#2a78d6',
  series2: '#eb6834',
  series7: '#4a3aa7',
}

export const RAG_STATUS_PRINT_COLOR = {
  GOOD: STATUS_REPORT_CHART_COLORS_PRINT.good,
  WARNING: STATUS_REPORT_CHART_COLORS_PRINT.warning,
  CRITICAL: STATUS_REPORT_CHART_COLORS_PRINT.critical,
}

// Equivalente hex-fixo de TASK_TYPE_COLORS (abaixo) pro Gantt nível 1+2 do
// Status Report (StatusReportGanttMini.jsx) — a tela usa TASK_TYPE_COLORS
// (var(--...)) normalmente, direto; só a impressão precisa deste mapa
// (var(--...) não resolve no pipeline de impressão, mesmo motivo de
// RAG_STATUS_PRINT_COLOR acima).
export const TASK_TYPE_PRINT_COLOR = {
  CONSULTING: STATUS_REPORT_CHART_COLORS_PRINT.series1,
  MANAGEMENT: STATUS_REPORT_CHART_COLORS_PRINT.series2,
}

// Risco (RiskLevel/RiskStatus em app/models.py) — usados pela primeira vez
// numa tela (o CRUD já existia no backend, ver app/routers/risks.py, mas
// sem UI) dentro do Status Report (risks_snapshot).
export const RISK_LEVEL_LABELS = {
  LOW: 'Baixa',
  MED: 'Média',
  HIGH: 'Alta',
}

export const RISK_LEVEL_TONE = {
  LOW: 'good',
  MED: 'warning',
  HIGH: 'critical',
}

export const RISK_STATUS_LABELS = {
  OPEN: 'Aberto',
  MITIGATED: 'Mitigado',
  CLOSED: 'Fechado',
}

export const RISK_STATUS_TONE = {
  OPEN: 'critical',
  MITIGATED: 'warning',
  CLOSED: 'good',
}

// Conhecimento (KnowledgeRequirement/KnowledgeStatus em app/models.py) —
// cadastro de Funcionalidades, autoavaliação e Revisão/Aprovação.
export const KNOWLEDGE_REQUIREMENT_LABELS = {
  REQUIRED: 'Necessário',
  DESIRABLE: 'Desejável',
}

export const KNOWLEDGE_REQUIREMENT_TONE = {
  REQUIRED: 'critical',
  DESIRABLE: 'warning',
}

// Escala de nível de conhecimento (pedido do usuário, com o texto exato de
// cada nível) — usada em ResourceKnowledge.self_level/reviewed_level (0 a
// 4). Chaves numéricas (não string) de propósito, mesmo critério de
// RESOURCE_LEVEL_LABELS acima — comparação/indexação direta por número.
export const KNOWLEDGE_LEVEL_LABELS = {
  0: 'Nível 0 - Não conhece',
  1: 'Nível 1 - Conhece o conceito',
  2: 'Nível 2 - Conhece e implanta com apoio',
  3: 'Nível 3 - Conhece e implanta sem apoio',
  4: 'Nível 4 - Especialista',
}

// Versão curta (sem o "Nível N -") pra caber em colunas de tabela estreitas
// (tela de Revisão e Aprovação, que lista Sistema/Módulo/Funcionalidade
// junto).
export const KNOWLEDGE_LEVEL_SHORT_LABELS = {
  0: 'Não conhece',
  1: 'Conhece o conceito',
  2: 'Implanta com apoio',
  3: 'Implanta sem apoio',
  4: 'Especialista',
}

export const KNOWLEDGE_STATUS_LABELS = {
  DRAFT: 'Rascunho',
  SUBMITTED: 'Aguardando revisão',
  APPROVED: 'Aprovado',
  REJECTED: 'Rejeitado',
}

export const KNOWLEDGE_STATUS_TONE = {
  DRAFT: 'warning',
  SUBMITTED: 'warning',
  APPROVED: 'good',
  REJECTED: 'critical',
}

// --- Versões traduzidas dos rótulos acima (para o idioma da interface) ----
// As constantes exportadas acima continuam sendo o texto em Português
// (usado como chave de tradução em toda a base — ver i18n/translations.js).
// `getLabels(lang)` devolve cópias com os MESMOS valores traduzidos, prontas
// pra uso direto em `labels.TASK_STATUS_LABELS[status]` etc.; em pt-BR
// (padrão) o resultado é idêntico às constantes originais.

function translateMap(map, lang) {
  const out = {}
  for (const [key, value] of Object.entries(map)) {
    out[key] = translate(lang, value)
  }
  return out
}

export function getLabels(lang) {
  return {
    ROLE_LABELS: translateMap(ROLE_LABELS, lang),
    RESOURCE_FUNCTION_LABELS: translateMap(RESOURCE_FUNCTION_LABELS, lang),
    RESOURCE_LEVEL_LABELS: translateMap(RESOURCE_LEVEL_LABELS, lang),
    TASK_MODALITY_LABELS: translateMap(TASK_MODALITY_LABELS, lang),
    PROJECT_STATUS_LABELS: translateMap(PROJECT_STATUS_LABELS, lang),
    PROJECT_TYPE_LABELS: translateMap(PROJECT_TYPE_LABELS, lang),
    TASK_STATUS_LABELS: translateMap(TASK_STATUS_LABELS, lang),
    TASK_STATUS_LABELS_SHORT: translateMap(TASK_STATUS_LABELS_SHORT, lang),
    TASK_TYPE_LABELS: translateMap(TASK_TYPE_LABELS, lang),
    APPROVAL_STATUS_LABELS: translateMap(APPROVAL_STATUS_LABELS, lang),
    APPROVAL_STATUS_LABELS_SHORT: translateMap(APPROVAL_STATUS_LABELS_SHORT, lang),
    USER_STATUS_LABELS: translateMap(USER_STATUS_LABELS, lang),
    DEPENDENCY_TYPE_LABELS: translateMap(DEPENDENCY_TYPE_LABELS, lang),
    DEPENDENCY_TYPE_SHORT: translateMap(DEPENDENCY_TYPE_SHORT, lang),
    STATUS_DOT_LABELS: translateMap(STATUS_DOT_LABELS, lang),
    RAG_STATUS_LABELS: translateMap(RAG_STATUS_LABELS, lang),
    RISK_LEVEL_LABELS: translateMap(RISK_LEVEL_LABELS, lang),
    RISK_STATUS_LABELS: translateMap(RISK_STATUS_LABELS, lang),
    KNOWLEDGE_REQUIREMENT_LABELS: translateMap(KNOWLEDGE_REQUIREMENT_LABELS, lang),
    KNOWLEDGE_LEVEL_LABELS: translateMap(KNOWLEDGE_LEVEL_LABELS, lang),
    KNOWLEDGE_LEVEL_SHORT_LABELS: translateMap(KNOWLEDGE_LEVEL_SHORT_LABELS, lang),
    KNOWLEDGE_STATUS_LABELS: translateMap(KNOWLEDGE_STATUS_LABELS, lang),
    WEEKDAY_LABELS: WEEKDAY_LABELS.map((day) => translate(lang, day)),
    TIMESHEET_STATUS_LABELS: translateMap(TIMESHEET_STATUS_LABELS, lang),
    ABSENCE_TYPE_LABELS: translateMap(ABSENCE_TYPE_LABELS, lang),
    WORK_CLASSIFICATION_LABELS: translateMap(WORK_CLASSIFICATION_LABELS, lang),
    REWORK_REASON_LABELS: translateMap(REWORK_REASON_LABELS, lang),
  }
}

// Rótulo combinado de Função + Nível do recurso — usado em toda tela que
// hoje mostra "o cargo do recurso" como texto (ex.: nome de exibição
// quando o usuário vinculado não está disponível). Substitui o antigo
// `resource.role_title` (texto livre); `labels` é o resultado de
// `getLabels(lang)` já traduzido. Qualquer um dos dois campos pode estar
// vazio (ainda não preenchido, ver Resource.function/level no backend).
export function resourceFunctionLevelLabel(resource, labels) {
  if (!resource) return ''
  const functionLabel = resource.function ? labels.RESOURCE_FUNCTION_LABELS[resource.function] : ''
  const levelLabel = resource.level ? labels.RESOURCE_LEVEL_LABELS[resource.level] : ''
  if (functionLabel && levelLabel) return `${functionLabel} · ${levelLabel}`
  return functionLabel || levelLabel || ''
}
