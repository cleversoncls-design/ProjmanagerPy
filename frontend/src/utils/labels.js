export const ROLE_LABELS = {
  ADMIN: 'Administrador',
  INTERNAL_PM: 'Gerente de projetos',
  CONSULTANT: 'Consultor',
  CLIENT_PM: 'PM do cliente',
  CLIENT_USER: 'Usuário-chave',
}

export const MANAGEMENT_ROLES = ['ADMIN', 'INTERNAL_PM']
export const INTERNAL_ROLES = ['ADMIN', 'INTERNAL_PM', 'CONSULTANT']

export const PROJECT_STATUS_LABELS = {
  PLANNING: 'Planejamento',
  ACTIVE: 'Ativo',
  ON_HOLD: 'Em espera',
  COMPLETED: 'Concluído',
  CANCELLED: 'Cancelado',
}

// Cor de status "semânfora" (good/warning/serious/critical) — reservada,
// nunca reaproveitada como cor categórica de série.
export const PROJECT_STATUS_TONE = {
  PLANNING: 'muted',
  ACTIVE: 'good',
  ON_HOLD: 'warning',
  COMPLETED: 'good',
  CANCELLED: 'critical',
}

export const TASK_STATUS_LABELS = {
  NOT_STARTED: 'Não iniciada',
  IN_PROGRESS: 'Em andamento',
  COMPLETED: 'Concluída',
  DELAYED: 'Atrasada',
}

export const TASK_STATUS_TONE = {
  NOT_STARTED: 'muted',
  IN_PROGRESS: 'warning',
  COMPLETED: 'good',
  DELAYED: 'critical',
}

export const TASK_TYPE_LABELS = {
  MANAGEMENT: 'Gestão',
  CONSULTING: 'Consultoria',
  // Timesheet avulso sem task_id (ver financials_by_task_type na API) não
  // tem task_type — usado só na quebra financeira do projeto, nunca em
  // Task.task_type em si.
  ADHOC: 'Avulso',
}

// Cor categórica fixa por entidade (nunca por posição/ranking — um filtro
// que muda a contagem não pode "repintar" quem sobrou). Mesma cor em
// qualquer tela que mostrar a mesma categoria.
export const TASK_STATUS_COLORS = {
  NOT_STARTED: 'var(--series-1)',
  IN_PROGRESS: 'var(--series-4)',
  COMPLETED: 'var(--series-3)',
  DELAYED: 'var(--series-8)',
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

export const WEEKDAY_LABELS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']

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
