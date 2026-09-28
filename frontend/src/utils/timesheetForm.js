import { formatHoursDuration, hmToMinutes, minutesToHM } from './format'

// Editar/excluir um apontamento (TimesheetsPage "Meus apontamentos" e a
// coluna de ações da Ordem de Serviço) só ficam disponíveis enquanto ele
// não tiver sido Aprovado — depois de aprovado ele já entrou em
// `Task.actual_hours` (e possivelmente faturamento), então mudar/apagar
// sem controle quebraria esse número (ver _require_own_editable_entry no
// backend, que também recusa nesse caso — isto aqui só evita oferecer o
// botão, nunca é a única trava). Mais pra frente isso ganha uma segunda
// trava: bloqueio mensal (mês fechado), ainda não implementado.
export function isTimesheetEditable(entry) {
  return entry.status !== 'APPROVED'
}

/** Formulário vazio pro card "Novo apontamento" (TimesheetsPage) — `date`
 * fica de fora aqui (cada tela decide o padrão: hoje, ou a data do
 * apontamento sendo editado). */
export function emptyTimesheetForm(date) {
  return { date, project_id: '', task_id: '', start_time: '', end_time: '', break_minutes: '00:00', description: '' }
}

/** Converte um apontamento já salvo (TimesheetRead/ServiceOrderActivity)
 * pro formato que o formulário usa — o inverso do `payload` montado em
 * handleSubmit (TimesheetsPage.jsx). `entry.project_id` só vem preenchido
 * num apontamento avulso (sem task_id); com task_id, o projeto é o da
 * própria tarefa (`tasksById`), já que TimesheetRead não repete o
 * project_id nesse caso. Usado tanto pelo "Editar" de TimesheetsPage
 * quanto pelo TimesheetEditModal (aberto a partir da Ordem de Serviço). */
export function entryToTimesheetForm(entry, tasksById) {
  const task = entry.task_id ? tasksById[entry.task_id] : null
  return {
    date: entry.date,
    project_id: entry.task_id ? task?.project_id || '' : entry.project_id || '',
    task_id: entry.task_id || '',
    start_time: entry.start_time ? entry.start_time.slice(0, 5) : '',
    end_time: entry.end_time ? entry.end_time.slice(0, 5) : '',
    break_minutes: minutesToHM(entry.break_minutes),
    description: entry.description || '',
  }
}

/** Monta o payload de POST/PUT /timesheets a partir do formulário. */
export function timesheetFormToPayload(form) {
  const payload = {
    date: form.date,
    start_time: form.start_time,
    end_time: form.end_time,
    break_minutes: hmToMinutes(form.break_minutes),
    description: form.description || null,
  }
  if (form.task_id) payload.task_id = form.task_id
  else if (form.project_id) payload.project_id = form.project_id
  return payload
}

/** Prévia do total calculado (Hora Fim − Hora Início − Intervalo), já em
 * formato de horas "HH:MM" — só pra mostrar ao consultor antes de salvar; o
 * valor que vale de verdade é sempre recalculado no backend (nunca
 * digitado, nem confiado do cliente, mesmo padrão de `Project.sold_value`).
 * `form.break_minutes` é um "HH:MM" (o <input type="time"> do campo
 * Intervalo, usado como seletor de duração) — convertido pra minutos aqui
 * antes da conta. */
export function previewTimesheetHours(form) {
  if (!form.start_time || !form.end_time) return null
  const [sh, sm] = form.start_time.split(':').map(Number)
  const [eh, em] = form.end_time.split(':').map(Number)
  const span = eh * 60 + em - (sh * 60 + sm)
  const brk = hmToMinutes(form.break_minutes)
  if (!(span > 0) || brk >= span) return null
  return formatHoursDuration((span - brk) / 60)
}
