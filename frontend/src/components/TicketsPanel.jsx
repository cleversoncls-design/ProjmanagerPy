import { useEffect, useMemo, useState } from 'react'
import * as ticketsApi from '../api/tickets'
import * as projectsApi from '../api/projects'
import * as tasksApi from '../api/tasks'
import { useLanguage } from '../context/LanguageContext'
import Card from './Card'
import Button from './Button'
import Modal from './Modal'
import Spinner from './Spinner'
import ErrorBanner from './ErrorBanner'
import StatusPill from './StatusPill'
import Table from './Table'
import { FormField, TextInput, Select, TextArea } from './FormField'
import { PlusIcon } from './icons'
import { formatDateTime, formatHoursDuration, hmToMinutes } from '../utils/format'
import { TICKET_CRITICALITY_TONE, TICKET_STATUS_TONE } from '../utils/labels'

const CLOSED_PROJECT_STATUSES = ['COMPLETED', 'CANCELLED', 'MODELO']

function todayIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

/** Lista de tickets internos (pendentes) + abertura + detalhe com histórico.
 * Usada na página "Tickets" (todos os projetos) e na aba "Tickets" de um
 * projeto (`projectId` fixo). Ver app/routers/tickets.py. */
export default function TicketsPanel({ projectId = null }) {
  const { t, labels } = useLanguage()
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filters, setFilters] = useState({ scope: 'all', status_filter: '', criticality: '', open_only: true })
  const [showNew, setShowNew] = useState(false)
  const [openTicketId, setOpenTicketId] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    ticketsApi
      .listTickets({
        project_id: projectId || undefined,
        scope: filters.scope,
        status_filter: filters.status_filter || undefined,
        criticality: filters.criticality || undefined,
        open_only: filters.open_only || undefined,
      })
      .then(setRows)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [projectId, filters.scope, filters.status_filter, filters.criticality, filters.open_only])

  function updateFilter(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setFilters((prev) => ({ ...prev, [field]: value }))
    }
  }

  const columns = [
    {
      key: 'code',
      header: t('Ticket'),
      nowrap: true,
      render: (row) => (
        <button type="button" onClick={() => setOpenTicketId(row.id)} className="font-medium text-[var(--series-1)] hover:underline">
          {row.code}
        </button>
      ),
    },
    { key: 'title', header: t('Título'), render: (row) => row.title },
    ...(projectId ? [] : [{ key: 'project', header: t('Projeto'), nowrap: true, render: (row) => `${row.project_code}` }]),
    {
      key: 'task',
      header: t('Tarefa'),
      render: (row) => (row.task_name ? `${row.task_wbs} — ${row.task_name}` : '—'),
    },
    {
      key: 'criticality',
      header: t('Criticidade'),
      render: (row) => <StatusPill label={labels.TICKET_CRITICALITY_LABELS[row.criticality]} tone={TICKET_CRITICALITY_TONE[row.criticality]} />,
    },
    {
      key: 'status',
      header: t('Status'),
      render: (row) => <StatusPill label={labels.TICKET_STATUS_LABELS[row.status]} tone={TICKET_STATUS_TONE[row.status]} />,
    },
    { key: 'requester', header: t('Solicitante'), render: (row) => row.requester_name || '—' },
    { key: 'assignee', header: t('Responsável'), render: (row) => row.assignee_name || '—' },
    { key: 'hours', header: t('Horas'), align: 'right', render: (row) => formatHoursDuration(row.hours_logged) },
    { key: 'created_at', header: t('Aberto em'), nowrap: true, render: (row) => formatDateTime(row.created_at) },
  ]

  return (
    <div className="space-y-4">
      <Card
        title={t('Tickets (pendentes)')}
        action={
          <Button onClick={() => setShowNew(true)}>
            <PlusIcon size={15} /> {t('Novo ticket')}
          </Button>
        }
      >
        <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
          <FormField label={t('Exibir')}>
            <Select value={filters.scope} onChange={updateFilter('scope')}>
              <option value="all">{t('Tudo que posso ver')}</option>
              <option value="requested">{t('Abertos por mim')}</option>
              <option value="assigned">{t('Direcionados a mim')}</option>
            </Select>
          </FormField>
          <FormField label={t('Status')}>
            <Select value={filters.status_filter} onChange={updateFilter('status_filter')}>
              <option value="">{t('Todos')}</option>
              {Object.entries(labels.TICKET_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Criticidade')}>
            <Select value={filters.criticality} onChange={updateFilter('criticality')}>
              <option value="">{t('Todas')}</option>
              {Object.entries(labels.TICKET_CRITICALITY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Fechados')}>
            <label className="flex h-[38px] items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--text-secondary)]">
              <input type="checkbox" checked={!filters.open_only} onChange={(event) => setFilters((prev) => ({ ...prev, open_only: !event.target.checked }))} />
              {t('Mostrar fechados')}
            </label>
          </FormField>
        </div>
        <ErrorBanner message={error} />
        {loading ? <Spinner /> : <Table columns={columns} rows={rows} getRowKey={(row) => row.id} emptyMessage={t('Nenhum ticket encontrado.')} />}
      </Card>

      {showNew && (
        <NewTicketModal
          projectId={projectId}
          onClose={() => setShowNew(false)}
          onCreated={(ticket) => {
            setShowNew(false)
            load()
            setOpenTicketId(ticket.id)
          }}
        />
      )}
      {openTicketId && <TicketDetailModal ticketId={openTicketId} onClose={() => setOpenTicketId(null)} onChanged={load} />}
    </div>
  )
}

function NewTicketModal({ projectId, onClose, onCreated }) {
  const { t, labels } = useLanguage()
  const [projects, setProjects] = useState([])
  const [tasks, setTasks] = useState([])
  const [form, setForm] = useState({
    project_id: projectId || '',
    task_id: '',
    criticality: 'MEDIUM',
    title: '',
    description: '',
  })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    projectsApi
      .listProjects()
      .then((rows) => setProjects(rows.filter((project) => !CLOSED_PROJECT_STATUSES.includes(project.status))))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!form.project_id) {
      setTasks([])
      return
    }
    tasksApi
      .listTasks(form.project_id)
      .then(setTasks)
      .catch(() => setTasks([]))
  }, [form.project_id])

  const tasksById = useMemo(() => Object.fromEntries(tasks.map((task) => [task.id, task])), [tasks])
  // Só tarefas-folha (o tempo do ticket é apontado na tarefa); mostra a
  // tarefa-pai ("Tarefa Principal") antes do nome, pra identificar a etapa.
  const leafTasks = useMemo(() => {
    const parentIds = new Set(tasks.map((task) => task.parent_task_id).filter(Boolean))
    return tasks.filter((task) => !parentIds.has(task.id) && task.status !== 'CLOSED')
  }, [tasks])

  function updateField(field) {
    return (event) => {
      const value = event.target.value
      setForm((prev) => (field === 'project_id' ? { ...prev, project_id: value, task_id: '' } : { ...prev, [field]: value }))
    }
  }

  function taskLabel(task) {
    const parent = task.parent_task_id ? tasksById[task.parent_task_id] : null
    return `${parent ? `${parent.name} › ` : ''}${task.wbs_code} — ${task.name}`
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setSaving(true)
    try {
      const created = await ticketsApi.createTicket({
        project_id: form.project_id,
        task_id: form.task_id,
        criticality: form.criticality,
        title: form.title,
        description: form.description,
      })
      onCreated(created)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal title={t('Novo ticket')} onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <FormField label={t('Projeto')} required>
            <Select required value={form.project_id} onChange={updateField('project_id')} disabled={Boolean(projectId)}>
              <option value="">{t('Selecione…')}</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.code} — {project.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Tarefa do projeto')} required hint={t('Tarefa à qual o incidente está relacionado — o tempo gasto será apontado nela.')}>
            <Select required value={form.task_id} onChange={updateField('task_id')} disabled={!form.project_id}>
              <option value="">{t('Selecione uma tarefa…')}</option>
              {leafTasks.map((task) => (
                <option key={task.id} value={task.id}>
                  {taskLabel(task)}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
        <FormField label={t('Criticidade')} required>
          <Select required value={form.criticality} onChange={updateField('criticality')}>
            {Object.entries(labels.TICKET_CRITICALITY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label} — {t(CRITICALITY_HINTS[value])}
              </option>
            ))}
          </Select>
        </FormField>
        <FormField label={t('Título breve')} required>
          <TextInput required maxLength={200} value={form.title} onChange={updateField('title')} placeholder={t('Resumo claro do problema')} />
        </FormField>
        <FormField
          label={t('Descrição detalhada')}
          required
          hint={t('Passo a passo para reproduzir o erro e comportamento esperado × comportamento observado.')}
        >
          <TextArea required rows={7} value={form.description} onChange={updateField('description')} />
        </FormField>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? t('Salvando…') : t('Registrar ticket')}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

const CRITICALITY_HINTS = {
  LOW: 'não impede a operação',
  MEDIUM: 'dificulta o processo, mas existem alternativas',
  HIGH: 'impede o funcionamento de um processo-chave',
  CRITICAL: 'interrupção total do serviço / bloqueio geral',
}

// Mensagem obrigatória nestas mudanças de status (espelha tickets.py).
function statusNeedsMessage(ticket, target) {
  if (target === 'WAITING_REQUESTER' || target === 'RESOLVED') return true
  if (target === 'IN_PROGRESS' && (ticket.status === 'RESOLVED' || ticket.status === 'CLOSED')) return true
  if (target === 'CLOSED' && ticket.status !== 'RESOLVED') return true
  return false
}

function statusActionLabel(ticket, target, t) {
  if (target === 'IN_PROGRESS' && ticket.status === 'ASSIGNED') return t('Iniciar atendimento')
  if (target === 'IN_PROGRESS' && ticket.status === 'WAITING_REQUESTER') return t('Voltar ao atendimento')
  if (target === 'IN_PROGRESS') return t('Reabrir (não resolvido)')
  if (target === 'WAITING_REQUESTER') return t('Pedir informação ao solicitante')
  if (target === 'RESOLVED') return t('Marcar como resolvido')
  if (target === 'CLOSED' && ticket.status === 'RESOLVED') return t('Confirmar solução e fechar')
  return t('Encerrar / cancelar ticket')
}

function TicketDetailModal({ ticketId, onClose, onChanged }) {
  const { t, labels } = useLanguage()
  const [ticket, setTicket] = useState(null)
  const [assignees, setAssignees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // null | 'assign' | 'criticality' | 'time' | { status }
  const [action, setAction] = useState(null)
  const [comment, setComment] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [newCriticality, setNewCriticality] = useState('')
  const [message, setMessage] = useState('')
  const [timeForm, setTimeForm] = useState({ date: todayIso(), start_time: '', end_time: '', break_time: '00:00', description: '' })

  useEffect(() => {
    ticketsApi
      .getTicket(ticketId)
      .then(setTicket)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }, [ticketId])

  useEffect(() => {
    if (ticket?.can_assign && assignees.length === 0) {
      ticketsApi
        .listTicketAssignees()
        .then(setAssignees)
        .catch(() => {})
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticket?.can_assign])

  async function run(fn) {
    setBusy(true)
    setError('')
    try {
      const updated = await fn()
      setTicket(updated)
      setAction(null)
      setMessage('')
      onChanged()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  function openAction(next) {
    setAction(next)
    setMessage('')
    setError('')
  }

  if (loading) {
    return (
      <Modal title={t('Ticket')} onClose={onClose} wide>
        <Spinner />
      </Modal>
    )
  }
  if (!ticket) {
    return (
      <Modal title={t('Ticket')} onClose={onClose} wide>
        <ErrorBanner message={error} />
      </Modal>
    )
  }

  const closed = ticket.status === 'CLOSED'
  const statusAction = action && typeof action === 'object' ? action.status : null

  return (
    <Modal title={`${ticket.code} — ${ticket.title}`} onClose={onClose} wide>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill label={labels.TICKET_STATUS_LABELS[ticket.status]} tone={TICKET_STATUS_TONE[ticket.status]} />
          <StatusPill label={`${t('Criticidade')}: ${labels.TICKET_CRITICALITY_LABELS[ticket.criticality]}`} tone={TICKET_CRITICALITY_TONE[ticket.criticality]} />
        </div>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <Info label={t('Projeto')} value={`${ticket.project_code} — ${ticket.project_name}`} />
          <Info
            label={t('Tarefa')}
            value={ticket.task_name ? `${ticket.parent_task_name ? `${ticket.parent_task_name} › ` : ''}${ticket.task_wbs} — ${ticket.task_name}` : '—'}
          />
          <Info label={t('Solicitante')} value={ticket.requester_name ? `${ticket.requester_name} (${ticket.requester_email})` : '—'} />
          <Info label={t('Responsável')} value={ticket.assignee_name || t('Ainda não direcionado')} />
          <Info label={t('Aberto em')} value={formatDateTime(ticket.created_at)} />
          <Info
            label={t('Horas apontadas')}
            value={`${formatHoursDuration(ticket.hours_logged)} (${t('aprovadas')}: ${formatHoursDuration(ticket.hours_approved)})`}
          />
        </dl>

        <div>
          <p className="mb-1 text-xs font-medium text-[var(--text-secondary)]">{t('Descrição detalhada')}</p>
          <p className="whitespace-pre-wrap rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 py-2 text-sm">{ticket.description}</p>
        </div>

        {!closed && (
          <div className="flex flex-wrap gap-2">
            {ticket.can_assign && (
              <Button variant="secondary" onClick={() => openAction('assign')}>
                {ticket.assignee_id ? t('Redirecionar') : t('Direcionar')}
              </Button>
            )}
            {ticket.can_log_time && (
              <Button variant="secondary" onClick={() => openAction('time')}>
                {t('Apontar tempo')}
              </Button>
            )}
            {ticket.can_change_criticality && (
              <Button
                variant="secondary"
                onClick={() => {
                  setNewCriticality(ticket.criticality)
                  openAction('criticality')
                }}
              >
                {t('Alterar criticidade')}
              </Button>
            )}
          </div>
        )}
        {(ticket.allowed_statuses.length > 0 || closed) && (
          <div className="flex flex-wrap gap-2">
            {ticket.allowed_statuses.map((target) => (
              <Button key={target} variant={target === 'CLOSED' && ticket.status === 'RESOLVED' ? 'primary' : 'secondary'} onClick={() => openAction({ status: target })}>
                {statusActionLabel(ticket, target, t)}
              </Button>
            ))}
          </div>
        )}

        {action === 'assign' && (
          <ActionBox title={t('Direcionar ticket')} onCancel={() => setAction(null)}>
            <FormField label={t('Responsável')} required hint={t('Consultores e desenvolvedores internos com Recurso.')}>
              <Select value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)}>
                <option value="">{t('Selecione…')}</option>
                {assignees
                  .filter((person) => person.id !== ticket.assignee_id)
                  .map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name}
                    </option>
                  ))}
              </Select>
            </FormField>
            <FormField label={t('Mensagem (opcional)')}>
              <TextArea rows={2} value={message} onChange={(event) => setMessage(event.target.value)} />
            </FormField>
            <Button disabled={busy || !assigneeId} onClick={() => run(() => ticketsApi.assignTicket(ticket.id, { assignee_id: assigneeId, message }))}>
              {t('Confirmar')}
            </Button>
          </ActionBox>
        )}

        {action === 'criticality' && (
          <ActionBox title={t('Alterar criticidade')} onCancel={() => setAction(null)}>
            <FormField label={t('Criticidade')}>
              <Select value={newCriticality} onChange={(event) => setNewCriticality(event.target.value)}>
                {Object.entries(labels.TICKET_CRITICALITY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label={t('Motivo (opcional)')}>
              <TextArea rows={2} value={message} onChange={(event) => setMessage(event.target.value)} />
            </FormField>
            <Button
              disabled={busy || newCriticality === ticket.criticality}
              onClick={() => run(() => ticketsApi.changeTicketCriticality(ticket.id, { criticality: newCriticality, message }))}
            >
              {t('Confirmar')}
            </Button>
          </ActionBox>
        )}

        {statusAction && (
          <ActionBox title={statusActionLabel(ticket, statusAction, t)} onCancel={() => setAction(null)}>
            <FormField
              label={statusNeedsMessage(ticket, statusAction) ? t('Mensagem') : t('Mensagem (opcional)')}
              required={statusNeedsMessage(ticket, statusAction)}
            >
              <TextArea rows={3} value={message} onChange={(event) => setMessage(event.target.value)} />
            </FormField>
            <Button
              disabled={busy || (statusNeedsMessage(ticket, statusAction) && !message.trim())}
              onClick={() => run(() => ticketsApi.changeTicketStatus(ticket.id, { status: statusAction, message }))}
            >
              {t('Confirmar')}
            </Button>
          </ActionBox>
        )}

        {action === 'time' && (
          <ActionBox title={t('Apontar tempo neste ticket')} onCancel={() => setAction(null)}>
            <p className="text-xs text-[var(--text-muted)]">
              {t('Cria um apontamento de horas na tarefa do ticket (pendente de aprovação), como o apontamento normal.')}
            </p>
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <FormField label={t('Data')} required>
                <TextInput type="date" value={timeForm.date} onChange={(event) => setTimeForm((prev) => ({ ...prev, date: event.target.value }))} />
              </FormField>
              <FormField label={t('Hora início')} required>
                <TextInput type="time" value={timeForm.start_time} onChange={(event) => setTimeForm((prev) => ({ ...prev, start_time: event.target.value }))} />
              </FormField>
              <FormField label={t('Hora fim')} required>
                <TextInput type="time" value={timeForm.end_time} onChange={(event) => setTimeForm((prev) => ({ ...prev, end_time: event.target.value }))} />
              </FormField>
              <FormField label={t('Intervalo')}>
                <TextInput type="time" value={timeForm.break_time} onChange={(event) => setTimeForm((prev) => ({ ...prev, break_time: event.target.value }))} />
              </FormField>
            </div>
            <FormField label={t('O que foi feito')}>
              <TextArea rows={2} value={timeForm.description} onChange={(event) => setTimeForm((prev) => ({ ...prev, description: event.target.value }))} />
            </FormField>
            <Button
              disabled={busy || !timeForm.date || !timeForm.start_time || !timeForm.end_time}
              onClick={() =>
                run(async () => {
                  const updated = await ticketsApi.logTicketTime(ticket.id, {
                    date: timeForm.date,
                    start_time: timeForm.start_time,
                    end_time: timeForm.end_time,
                    break_minutes: hmToMinutes(timeForm.break_time),
                    description: timeForm.description || null,
                  })
                  setTimeForm((prev) => ({ ...prev, start_time: '', end_time: '', break_time: '00:00', description: '' }))
                  return updated
                })
              }
            >
              {t('Registrar tempo')}
            </Button>
          </ActionBox>
        )}

        <ErrorBanner message={error} />

        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Histórico')}</p>
          <ol className="space-y-2">
            {ticket.interactions.map((item) => (
              <li key={item.id} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm">
                <div className="flex flex-wrap items-baseline justify-between gap-2 text-xs text-[var(--text-muted)]">
                  <span className="font-medium text-[var(--text-secondary)]">{item.author_name || '—'}</span>
                  <span>{formatDateTime(item.created_at)}</span>
                </div>
                <p className="mt-0.5 font-medium text-[var(--text-primary)]">{interactionTitle(item, labels, t)}</p>
                {item.message && <p className="mt-1 whitespace-pre-wrap text-[var(--text-primary)]">{item.message}</p>}
              </li>
            ))}
          </ol>
        </div>

        {ticket.can_comment && (
          <div className="space-y-2">
            <FormField label={t('Nova interação')}>
              <TextArea rows={3} value={comment} onChange={(event) => setComment(event.target.value)} />
            </FormField>
            <div className="flex justify-end">
              <Button
                disabled={busy || !comment.trim()}
                onClick={() =>
                  run(async () => {
                    const updated = await ticketsApi.commentTicket(ticket.id, comment)
                    setComment('')
                    return updated
                  })
                }
              >
                {t('Enviar')}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

function interactionTitle(item, labels, t) {
  switch (item.kind) {
    case 'CREATED':
      return `${t('Ticket aberto')} (${labels.TICKET_CRITICALITY_LABELS[item.to_value] || item.to_value})`
    case 'ASSIGNMENT':
      return item.from_value
        ? `${t('Redirecionado')}: ${item.from_value} → ${item.to_value}`
        : `${t('Direcionado para')} ${item.to_value}`
    case 'STATUS':
      return `${t('Status')}: ${labels.TICKET_STATUS_LABELS[item.from_value] || item.from_value} → ${labels.TICKET_STATUS_LABELS[item.to_value] || item.to_value}`
    case 'CRITICALITY':
      return `${t('Criticidade')}: ${labels.TICKET_CRITICALITY_LABELS[item.from_value] || item.from_value} → ${labels.TICKET_CRITICALITY_LABELS[item.to_value] || item.to_value}`
    case 'TIME':
      return `${t('Tempo apontado')}: ${formatHoursDuration(item.to_value)} (${item.from_value})`
    default:
      return t('Comentário')
  }
}

function Info({ label, value }) {
  return (
    <div>
      <dt className="text-xs text-[var(--text-muted)]">{label}</dt>
      <dd className="text-[var(--text-primary)]">{value}</dd>
    </div>
  )
}

function ActionBox({ title, onCancel, children }) {
  const { t } = useLanguage()
  return (
    <div className="space-y-3 rounded-lg border border-[var(--border)] bg-[var(--page)] p-3">
      <div className="flex items-center justify-between">
        <p className="text-sm font-semibold text-[var(--text-primary)]">{title}</p>
        <button type="button" onClick={onCancel} className="text-xs text-[var(--text-muted)] hover:underline">
          {t('Cancelar')}
        </button>
      </div>
      {children}
    </div>
  )
}
