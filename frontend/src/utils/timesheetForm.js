import { formatHoursDuration, hmToMinutes, minutesToHM } from './format'

// Editar/excluir um apontamento (TimesheetsPage "Meus apontamentos" e a
// coluna de ações da Ordem de Serviço) ficam disponíveis independente do
// status — inclusive Aprovado ou Rejeitado (decisão confirmada com o
// usuário: editar sempre volta o apontamento pra Pendente e exige nova
// aprovação, ver PUT /timesheets/{id}). Antes disso um apontamento
// Aprovado ficava travado (já tinha entrado em Task.actual_hours); agora
// quem trava isso é só a trava mensal que ainda vai existir (mês fechado
// — ainda não implementada, ver `_require_own_editable_entry` no backend,
// que hoje só checa dono; é ali que a trava mensal vai entrar).
export function isTimesheetEditable() {
  return true
}

/** Formulário vazio pro card "Novo apontamento" (TimesheetsPage) — `date`
 * fica de fora aqui (cada tela decide o padrão: hoje, ou a data do
 * apontamento sendo editado). */
export function emptyTimesheetForm(date) {
  return {
    date,
    project_id: '',
    task_id: '',
    // Ticket interno (pendente) que originou a hora — opcional, só com tarefa.
    ticket_id: '',
    is_transit: false,
    absence_type: '',
    // % de Avanço da Tarefa + classificador Normal/Retrabalho (pedido do
    // usuário) — só fazem sentido com task_id setado; ver
    // applyExclusiveTimesheetField abaixo (zerados sempre que a tarefa
    // muda ou é limpa).
    task_progress_percentage: '',
    work_classification: 'NORMAL',
    rework_reasons: [],
    start_time: '',
    end_time: '',
    break_minutes: '00:00',
    description: '',
  }
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
    ticket_id: entry.ticket_id || '',
    is_transit: entry.is_transit || false,
    absence_type: entry.absence_type || '',
    task_progress_percentage: entry.task_progress_percentage ?? '',
    work_classification: entry.work_classification || 'NORMAL',
    rework_reasons: entry.rework_reasons || [],
    start_time: entry.start_time ? entry.start_time.slice(0, 5) : '',
    end_time: entry.end_time ? entry.end_time.slice(0, 5) : '',
    break_minutes: minutesToHM(entry.break_minutes),
    description: entry.description || '',
  }
}

/** Atualiza um dos campos mutuamente exclusivos do apontamento (Projeto/
 * Tarefa/Traslado/Tipo de ausência) — extraído pra um só lugar porque
 * TimesheetsPage.jsx e TimesheetEditModal.jsx tinham a mesma lógica
 * duplicada. Regra (pedido do usuário: ausência é sempre custo interno,
 * nunca pode vir junto de projeto/tarefa/Traslado — ver
 * _resolve_task_and_project no backend): marcar "Tipo de ausência" limpa
 * Projeto/Tarefa/Traslado; marcar qualquer um desses três limpa a
 * ausência. */
// % de Avanço da Tarefa + classificador Normal/Retrabalho (pedido do
// usuário) só fazem sentido com uma tarefa selecionada — este objeto é
// espalhado sempre que o campo Tarefa muda ou é limpo (direto ou via
// Traslado/Ausência/Projeto), pra nunca carregar o avanço/classificação de
// uma tarefa antiga para outro apontamento. `tasksById` (opcional,
// terceiro argumento) permite pré-preencher o % com o avanço ATUAL da
// tarefa escolhida — só uma sugestão inicial; o consultor pode ajustar
// antes de salvar.
const CLEAR_TASK_PROGRESS_FIELDS = { task_progress_percentage: '', work_classification: 'NORMAL', rework_reasons: [], ticket_id: '' }

export function applyExclusiveTimesheetField(prev, field, value, tasksById) {
  if (field === 'project_id') return { ...prev, project_id: value, task_id: '', is_transit: false, absence_type: value ? '' : prev.absence_type, ...CLEAR_TASK_PROGRESS_FIELDS }
  if (field === 'task_id') {
    const task = value && tasksById ? tasksById[value] : null
    return {
      ...prev,
      task_id: value,
      is_transit: value ? false : prev.is_transit,
      absence_type: value ? '' : prev.absence_type,
      ...CLEAR_TASK_PROGRESS_FIELDS,
      task_progress_percentage: value ? (task?.progress_percentage ?? '') : '',
    }
  }
  if (field === 'is_transit') return { ...prev, is_transit: value, task_id: value ? '' : prev.task_id, absence_type: value ? '' : prev.absence_type, ...(value ? CLEAR_TASK_PROGRESS_FIELDS : {}) }
  if (field === 'absence_type') {
    return {
      ...prev,
      absence_type: value,
      project_id: value ? '' : prev.project_id,
      task_id: value ? '' : prev.task_id,
      is_transit: value ? false : prev.is_transit,
      ...(value ? CLEAR_TASK_PROGRESS_FIELDS : {}),
    }
  }
  if (field === 'work_classification') return { ...prev, work_classification: value, rework_reasons: value === 'REWORK' ? prev.rework_reasons : [] }
  return { ...prev, [field]: value }
}

/** Marca/desmarca um motivo de retrabalho (lista de múltipla escolha) —
 * separado de `applyExclusiveTimesheetField` porque não é um campo de
 * valor único; usado pelo checklist de "Motivo do retrabalho" em
 * TimesheetFieldsForm.jsx. */
export function toggleReworkReason(form, reason) {
  const current = form.rework_reasons || []
  const next = current.includes(reason) ? current.filter((r) => r !== reason) : [...current, reason]
  return { ...form, rework_reasons: next }
}

/** Pedido do usuário: projeto selecionado sem tarefa e sem Traslado deixou
 * de ser permitido ("apontamento avulso") — precisa escolher uma tarefa OU
 * marcar Traslado. Mesma regra validada (de verdade) em
 * _resolve_task_and_project, routers/timesheets.py; usada aqui só pra
 * desabilitar o botão Salvar e mostrar o aviso antes de tentar submeter. */
export function timesheetFormNeedsTaskOrTransit(form) {
  return Boolean(form.project_id) && !form.task_id && !form.is_transit && !form.absence_type
}

/** Pedido do usuário: classificar como Retrabalho exige ao menos um motivo
 * selecionado. Mesma regra validada (de verdade) em _validate_rework,
 * routers/timesheets.py; usada aqui só pra desabilitar o botão Salvar e
 * mostrar o aviso antes de tentar submeter. */
export function timesheetFormNeedsReworkReason(form) {
  return Boolean(form.task_id) && form.work_classification === 'REWORK' && (form.rework_reasons || []).length === 0
}

/** Monta o payload de POST/PUT /timesheets a partir do formulário. */
export function timesheetFormToPayload(form) {
  const payload = {
    date: form.date,
    start_time: form.start_time,
    end_time: form.end_time,
    break_minutes: hmToMinutes(form.break_minutes),
    is_transit: Boolean(form.is_transit),
    absence_type: form.absence_type || null,
    description: form.description || null,
  }
  // Ausência nunca leva task_id nem project_id — é sempre custo interno da
  // empresa (decisão confirmada com o usuário; ver AbsenceType em
  // app/models.py). Traslado nunca leva task_id (sempre um projeto, nunca
  // uma tarefa específica — ver _resolve_task_and_project em
  // routers/timesheets.py).
  if (form.absence_type) {
    // sem project_id/task_id
  } else if (form.is_transit) {
    payload.project_id = form.project_id
  } else if (form.task_id) {
    payload.task_id = form.task_id
    // Mantém o vínculo com o ticket (editar o apontamento não pode soltá-lo).
    if (form.ticket_id) payload.ticket_id = form.ticket_id
    // % de Avanço da Tarefa + classificador Normal/Retrabalho (pedido do
    // usuário) — só enviados junto de task_id; vazio/'' vira null (campo
    // opcional, ver TimesheetCreate.task_progress_percentage).
    payload.task_progress_percentage = form.task_progress_percentage === '' || form.task_progress_percentage == null ? null : form.task_progress_percentage
    payload.work_classification = form.work_classification || 'NORMAL'
    payload.rework_reasons = form.work_classification === 'REWORK' ? form.rework_reasons || [] : []
  } else if (form.project_id) {
    payload.project_id = form.project_id
  }
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
