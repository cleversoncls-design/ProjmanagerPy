import { useEffect, useMemo, useState } from 'react'
import * as timesheetsApi from '../api/timesheets'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as projectsApi from '../api/projects'
import * as tasksApi from '../api/tasks'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import Table from '../components/Table'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import { FormField, TextInput, Select, TextArea } from '../components/FormField'
import IconButton from '../components/IconButton'
import Modal from '../components/Modal'
import { CheckIcon, XIcon, PencilIcon, TrashIcon } from '../components/icons'
import { formatDate, formatTime, formatHoursDuration, minutesToHM, hmToMinutes } from '../utils/format'
import { MANAGEMENT_ROLES, TIMESHEET_STATUS_TONE } from '../utils/labels'

// Editar/excluir só ficam disponíveis enquanto o apontamento não tiver sido
// Aprovado — depois de aprovado ele já entrou em `Task.actual_hours` (e
// possivelmente faturamento), então mudar/apagar sem controle quebraria
// esse número (ver _require_own_editable_entry no backend, que também
// recusa nesse caso — isto aqui só evita oferecer o botão, nunca é a única
// trava). Mais pra frente isso ganha uma segunda trava: bloqueio mensal
// (mês fechado), ainda não implementado.
function isEditable(entry) {
  return entry.status !== 'APPROVED'
}

function todayIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

const EMPTY_FORM = { date: todayIso(), project_id: '', task_id: '', start_time: '', end_time: '', break_minutes: '00:00', description: '' }

/** Prévia do total calculado (Hora Fim − Hora Início − Intervalo), já em
 * formato de horas "HH:MM" — só pra mostrar ao consultor antes de salvar; o
 * valor que vale de verdade é sempre recalculado no backend (nunca
 * digitado, nem confiado do cliente, mesmo padrão de `Project.sold_value`).
 * `form.break_minutes` é um "HH:MM" (o <input type="time"> do campo
 * Intervalo, usado como seletor de duração) — convertido pra minutos aqui
 * antes da conta. */
function previewHours(form) {
  if (!form.start_time || !form.end_time) return null
  const [sh, sm] = form.start_time.split(':').map(Number)
  const [eh, em] = form.end_time.split(':').map(Number)
  const span = eh * 60 + em - (sh * 60 + sm)
  const brk = hmToMinutes(form.break_minutes)
  if (!(span > 0) || brk >= span) return null
  return formatHoursDuration((span - brk) / 60)
}

export default function TimesheetsPage() {
  const { user } = useAuth()
  const { labels, t } = useLanguage()
  const canManage = MANAGEMENT_ROLES.includes(user.role)

  const [projects, setProjects] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])

  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [deletingEntry, setDeletingEntry] = useState(null)

  const [mine, setMine] = useState([])
  const [loadingMine, setLoadingMine] = useState(true)
  const [pending, setPending] = useState([])
  const [loadingPending, setLoadingPending] = useState(true)
  const [listError, setListError] = useState('')
  const [actingId, setActingId] = useState(null)

  useEffect(() => {
    projectsApi
      .listProjects()
      .then((rows) => {
        setProjects(rows)
        Promise.all(rows.map((p) => tasksApi.listTasks(p.id).catch(() => []))).then((lists) => setAllTasks(lists.flat()))
      })
      .catch(() => {})
    resourcesApi.listResources().then(setResources).catch(() => {})
    usersApi.listUsers().then(setUsers).catch(() => {})
  }, [])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourcesById = useMemo(
    () => Object.fromEntries(resources.map((r) => [r.id, { ...r, userName: usersById[r.user_id]?.name || r.role_title }])),
    [resources, usersById],
  )
  const projectsById = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p])), [projects])
  const tasksById = useMemo(() => Object.fromEntries(allTasks.map((task) => [task.id, task])), [allTasks])
  const taskOptions = useMemo(() => allTasks.filter((task) => task.project_id === form.project_id), [allTasks, form.project_id])
  const ownResource = useMemo(() => resources.find((r) => r.user_id === user.id) || null, [resources, user.id])

  function loadMine() {
    if (!ownResource) {
      setMine([])
      setLoadingMine(false)
      return
    }
    setLoadingMine(true)
    timesheetsApi
      .listTimesheets({ resource_id: ownResource.id })
      .then(setMine)
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingMine(false))
  }

  useEffect(loadMine, [ownResource])

  function loadPending() {
    if (!canManage) return
    setLoadingPending(true)
    timesheetsApi
      .listTimesheets({ status_filter: 'PENDING' })
      .then(setPending)
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingPending(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadPending, [canManage])

  function updateField(field) {
    return (event) => {
      const value = event.target.value
      setForm((prev) => (field === 'project_id' ? { ...prev, project_id: value, task_id: '' } : { ...prev, [field]: value }))
    }
  }

  function entryDescription(entry) {
    if (entry.task_id) {
      const task = tasksById[entry.task_id]
      const project = task ? projectsById[task.project_id] : null
      return {
        projectLabel: project ? `${project.code} — ${project.name}` : '—',
        taskLabel: task ? `${task.wbs_code} ${task.name}` : '—',
        typeLabel: task ? labels.TASK_TYPE_LABELS[task.task_type] : '—',
      }
    }
    if (entry.project_id) {
      const project = projectsById[entry.project_id]
      return { projectLabel: project ? `${project.code} — ${project.name}` : '—', taskLabel: t('Avulso'), typeLabel: labels.TASK_TYPE_LABELS.ADHOC }
    }
    return { projectLabel: t('Interno'), taskLabel: '—', typeLabel: t('Interno') }
  }

  function formTypeLabel() {
    if (form.task_id) {
      const task = tasksById[form.task_id]
      return task ? labels.TASK_TYPE_LABELS[task.task_type] : '—'
    }
    if (form.project_id) return labels.TASK_TYPE_LABELS.ADHOC
    return t('Interno')
  }

  /** Converte um apontamento já salvo pro formato que o formulário usa —
   * o inverso do `payload` montado em handleSubmit. `entry.project_id` só
   * vem preenchido num apontamento avulso (sem task_id); com task_id, o
   * projeto é o da própria tarefa (tasksById), já que TimesheetRead não
   * repete o project_id nesse caso. */
  function entryToForm(entry) {
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

  function handleEditClick(entry) {
    setEditingId(entry.id)
    setForm(entryToForm(entry))
    setFormError('')
  }

  function handleCancelEdit() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setFormError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setSaving(true)
    try {
      const payload = {
        date: form.date,
        start_time: form.start_time,
        end_time: form.end_time,
        break_minutes: hmToMinutes(form.break_minutes),
        description: form.description || null,
      }
      if (form.task_id) payload.task_id = form.task_id
      else if (form.project_id) payload.project_id = form.project_id
      if (editingId) await timesheetsApi.updateTimesheet(editingId, payload)
      else await timesheetsApi.createTimesheet(payload)
      setForm(EMPTY_FORM)
      setEditingId(null)
      loadMine()
    } catch (err) {
      setFormError(err.message)
    } finally {
      setSaving(false)
    }
  }

  async function handleStatus(entry, newStatus) {
    setActingId(entry.id)
    setListError('')
    try {
      await timesheetsApi.updateTimesheetStatus(entry.id, newStatus)
      loadPending()
      loadMine()
    } catch (err) {
      setListError(err.message)
    } finally {
      setActingId(null)
    }
  }

  const preview = previewHours(form)

  return (
    <div>
      <PageHeader title={t('Apontamento de horas')} subtitle={t('Registre e aprove horas trabalhadas nos projetos.')} />

      {!ownResource ? (
        <Card className="mb-4">
          <p className="text-sm text-[var(--text-secondary)]">
            {t('Seu usuário não tem um recurso vinculado — peça a um Administrador para vincular um recurso para poder apontar horas.')}
          </p>
        </Card>
      ) : (
        <Card title={editingId ? t('Editar apontamento') : t('Novo apontamento')} className="mb-4">
          {editingId && (
            <p className="-mt-2 mb-4 text-xs text-[var(--text-muted)]">{t('A alteração volta o status para Pendente e exige nova aprovação.')}</p>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Data')} required>
                <TextInput type="date" required value={form.date} onChange={updateField('date')} />
              </FormField>
              <FormField label={t('Projeto')} hint={t('Deixe em branco para hora administrativa interna.')}>
                <Select value={form.project_id} onChange={updateField('project_id')}>
                  <option value="">{t('Interno')}</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.code} — {project.name}
                    </option>
                  ))}
                </Select>
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <FormField label={t('Tarefa')} hint={!form.project_id ? t('Selecione um projeto para escolher a tarefa.') : undefined}>
                <Select value={form.task_id} onChange={updateField('task_id')} disabled={!form.project_id}>
                  <option value="">{t('Sem tarefa (apontamento no projeto)')}</option>
                  {taskOptions.map((task) => (
                    <option key={task.id} value={task.id}>
                      {task.wbs_code} — {task.name}
                    </option>
                  ))}
                </Select>
              </FormField>
              <FormField label={t('Tipo de apontamento')} hint={t('Segue automaticamente o tipo da tarefa (Gestão/Consultoria).')}>
                <div className="flex h-[38px] items-center rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 text-sm text-[var(--text-secondary)]">
                  {formTypeLabel()}
                </div>
              </FormField>
            </div>
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <FormField label={t('Hora início')} required>
                <TextInput type="time" required value={form.start_time} onChange={updateField('start_time')} />
              </FormField>
              <FormField label={t('Hora fim')} required>
                <TextInput type="time" required value={form.end_time} onChange={updateField('end_time')} />
              </FormField>
              <FormField label={t('Intervalo')}>
                <TextInput type="time" step="300" value={form.break_minutes} onChange={updateField('break_minutes')} />
              </FormField>
              <FormField label={t('Total calculado')}>
                <div className="flex h-[38px] items-center rounded-lg border border-[var(--border)] bg-[var(--page)] px-3 text-sm font-medium text-[var(--text-primary)]">
                  {preview ?? '—'}
                </div>
              </FormField>
            </div>
            <FormField label={t('Descrição')}>
              <TextArea rows={2} value={form.description} onChange={updateField('description')} />
            </FormField>

            <ErrorBanner message={formError} />

            <div className="flex justify-end gap-2 pt-1">
              {editingId && (
                <Button type="button" variant="secondary" onClick={handleCancelEdit} disabled={saving}>
                  {t('Cancelar')}
                </Button>
              )}
              <Button type="submit" disabled={saving}>
                {saving ? t('Salvando…') : t('Salvar')}
              </Button>
            </div>
          </form>
        </Card>
      )}

      <ErrorBanner message={listError} />

      <Card title={t('Meus apontamentos')} className="mb-4">
        {loadingMine ? (
          <Spinner />
        ) : (
          <Table
            columns={[
              { key: 'date', header: t('Data'), render: (row) => formatDate(row.date) },
              { key: 'project', header: t('Projeto'), render: (row) => entryDescription(row).projectLabel },
              { key: 'task', header: t('Tarefa'), render: (row) => entryDescription(row).taskLabel },
              { key: 'type', header: t('Tipo'), render: (row) => entryDescription(row).typeLabel },
              { key: 'time', header: t('Horário'), render: (row) => (row.start_time ? `${formatTime(row.start_time)}–${formatTime(row.end_time)}` : '—') },
              { key: 'hours', header: t('Total'), align: 'right', render: (row) => formatHoursDuration(row.hours_spent) },
              {
                key: 'status',
                header: t('Status'),
                render: (row) => (
                  <div className="flex items-center gap-1.5">
                    <StatusPill label={labels.TIMESHEET_STATUS_LABELS[row.status] || row.status} tone={TIMESHEET_STATUS_TONE[row.status]} />
                    {row.unscheduled && <StatusPill label={t('Fora da agenda')} tone="serious" />}
                  </div>
                ),
              },
              {
                key: 'actions',
                header: '',
                align: 'right',
                render: (row) =>
                  isEditable(row) ? (
                    <div className="flex justify-end gap-1.5">
                      <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => handleEditClick(row)} />
                      <IconButton icon={TrashIcon} label={t('Excluir')} variant="danger" onClick={() => setDeletingEntry(row)} />
                    </div>
                  ) : (
                    <span className="text-xs text-[var(--text-muted)]" title={t('Apontamento aprovado — não pode mais ser alterado ou excluído.')}>
                      —
                    </span>
                  ),
              },
            ]}
            rows={mine}
            getRowKey={(row) => row.id}
            emptyMessage={t('Nenhum apontamento registrado ainda.')}
          />
        )}
      </Card>

      {canManage && (
        <Card title={t('Aprovações pendentes')}>
          {loadingPending ? (
            <Spinner />
          ) : pending.length === 0 ? (
            <p className="text-sm text-[var(--text-secondary)]">{t('Nenhum apontamento pendente.')}</p>
          ) : (
            <div className="space-y-1.5">
              {pending.map((entry) => {
                const { projectLabel, taskLabel, typeLabel } = entryDescription(entry)
                const blockedForMe = entry.unscheduled && user.role !== 'ADMIN'
                return (
                  <div key={entry.id} className="rounded-lg border border-[var(--border)] px-3 py-2.5 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium text-[var(--text-primary)]">{formatDate(entry.date)}</span>
                        <span className="text-[var(--text-secondary)]">
                          {resourcesById[entry.resource_id]?.userName || '—'} · {projectLabel} · {taskLabel} · {typeLabel}
                        </span>
                        {entry.start_time && (
                          <span className="text-[var(--text-muted)]">
                            {formatTime(entry.start_time)}–{formatTime(entry.end_time)} ({formatHoursDuration(entry.hours_spent)})
                          </span>
                        )}
                        {entry.unscheduled && <StatusPill label={t('Fora da agenda')} tone="serious" />}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          disabled={actingId === entry.id || blockedForMe}
                          title={blockedForMe ? t('Só o Administrador pode aprovar apontamentos fora da agenda.') : undefined}
                          onClick={() => handleStatus(entry, 'APPROVED')}
                        >
                          <CheckIcon size={15} /> {t('Aprovar')}
                        </Button>
                        <Button type="button" variant="danger" disabled={actingId === entry.id} onClick={() => handleStatus(entry, 'REJECTED')}>
                          <XIcon size={15} /> {t('Rejeitar')}
                        </Button>
                      </div>
                    </div>
                    {entry.description && <p className="mt-1 text-xs text-[var(--text-muted)]">{entry.description}</p>}
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      )}

      {deletingEntry && (
        <TimesheetDeleteModal
          entry={deletingEntry}
          entryLabel={entryDescription(deletingEntry)}
          onClose={() => setDeletingEntry(null)}
          onDeleted={() => {
            setDeletingEntry(null)
            if (editingId === deletingEntry.id) handleCancelEdit()
            loadMine()
          }}
        />
      )}
    </div>
  )
}

/** Modal de confirmação pra excluir um apontamento — mesmo padrão de
 * ProjectDeleteModal/UserDeleteModal (Projects/UsersPage): a API (DELETE
 * /timesheets/{id}) já recusa (422) se o apontamento estiver Aprovado, mas
 * a tela nem oferece o botão nesse caso (ver isEditable) — este modal só
 * evita um clique acidental apagar um Pendente/Rejeitado. */
function TimesheetDeleteModal({ entry, entryLabel, onClose, onDeleted }) {
  const { t } = useLanguage()
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')

  async function handleDelete() {
    setDeleting(true)
    setError('')
    try {
      await timesheetsApi.deleteTimesheet(entry.id)
      onDeleted()
    } catch (err) {
      setError(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <Modal title={t('Excluir apontamento')} onClose={onClose}>
      <div className="space-y-4">
        <p className="text-sm text-[var(--text-secondary)]">
          {t('Tem certeza que quer excluir este apontamento?')}{' '}
          <span className="font-medium text-[var(--text-primary)]">
            {formatDate(entry.date)} · {entryLabel.projectLabel} · {entryLabel.taskLabel}
          </span>
          ? {t('Essa ação não pode ser desfeita.')}
        </p>
        <ErrorBanner message={error} />
        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            {t('Cancelar')}
          </Button>
          <Button type="button" variant="danger" disabled={deleting} onClick={handleDelete}>
            {deleting ? t('Excluindo…') : t('Excluir')}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
