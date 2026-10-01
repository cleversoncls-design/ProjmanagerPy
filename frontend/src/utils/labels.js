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
// Dashboard: ADMIN_LIKE_ROLES e os perfis externos do cliente (perfil
// externo não entrou nesta reorganização, mantido como já era) — Gerente
// de Projetos e Consultor não têm esse item no menu.
export const DASHBOARD_ROLES = ['ADMIN', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR', 'CLIENT_PM', 'CLIENT_USER']
// Projetos (lista + detalhe do projeto): todo mundo, menos Consultor —
// que perdeu esse item no menu (continua vendo Agenda de Consultores,
// Apontamento de horas e Ordens de Serviço).
export const PROJECTS_VISIBLE_ROLES = ['ADMIN', 'INTERNAL_PM', 'SERVICE_MANAGER', 'GENERAL_DIRECTOR', 'CLIENT_PM', 'CLIENT_USER']

// Primeira tela de cada perfil ao logar (ou ao cair em "/" depois de ser
// barrado por ProtectedRoute em alguma rota) — precisa ser uma rota que o
// próprio perfil tenha acesso, senão vira redirecionamento em loop.
export const ROLE_HOME_PATH = {
  ADMIN: '/',
  INTERNAL_PM: '/projects',
  CONSULTANT: '/schedules',
  CLIENT_PM: '/',
  CLIENT_USER: '/',
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
    TASK_STATUS_LABELS: translateMap(TASK_STATUS_LABELS, lang),
    TASK_STATUS_LABELS_SHORT: translateMap(TASK_STATUS_LABELS_SHORT, lang),
    TASK_TYPE_LABELS: translateMap(TASK_TYPE_LABELS, lang),
    APPROVAL_STATUS_LABELS: translateMap(APPROVAL_STATUS_LABELS, lang),
    APPROVAL_STATUS_LABELS_SHORT: translateMap(APPROVAL_STATUS_LABELS_SHORT, lang),
    USER_STATUS_LABELS: translateMap(USER_STATUS_LABELS, lang),
    DEPENDENCY_TYPE_LABELS: translateMap(DEPENDENCY_TYPE_LABELS, lang),
    DEPENDENCY_TYPE_SHORT: translateMap(DEPENDENCY_TYPE_SHORT, lang),
    STATUS_DOT_LABELS: translateMap(STATUS_DOT_LABELS, lang),
    WEEKDAY_LABELS: WEEKDAY_LABELS.map((day) => translate(lang, day)),
    TIMESHEET_STATUS_LABELS: translateMap(TIMESHEET_STATUS_LABELS, lang),
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
