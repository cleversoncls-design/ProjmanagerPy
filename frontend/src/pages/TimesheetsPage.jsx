import { useEffect, useMemo, useState } from 'react'
import * as timesheetsApi from '../api/timesheets'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as projectsApi from '../api/projects'
import * as clientsApi from '../api/clients'
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
import TimesheetFieldsForm from '../components/TimesheetFieldsForm'
import TimesheetDeleteModal from '../components/TimesheetDeleteModal'
import IconButton from '../components/IconButton'
import { FormField, TextInput, Select } from '../components/FormField'
import { CheckIcon, XIcon, PencilIcon, TrashIcon } from '../components/icons'
import { formatDate, formatTime, formatHoursDuration } from '../utils/format'
import { MANAGEMENT_ROLES, TIMESHEET_STATUS_TONE, resourceFunctionLevelLabel } from '../utils/labels'
import { emptyTimesheetForm, entryToTimesheetForm, previewTimesheetHours, timesheetFormToPayload, isTimesheetEditable } from '../utils/timesheetForm'

function todayIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

export default function TimesheetsPage() {
  const { user } = useAuth()
  const { labels, t } = useLanguage()
  const canManage = MANAGEMENT_ROLES.includes(user.role)

  const [projects, setProjects] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])

  const [form, setForm] = useState(() => emptyTimesheetForm(todayIso()))
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

  // Filtro por período (pedido do usuário) na lista de baixo — "Meus
  // apontamentos" por período + cliente + projeto; pro aprovador, período +
  // consultor + projeto em "Aprovações pendentes".
  const [mineFilters, setMineFilters] = useState({ start: '', end: '', client_id: '', project_id: '' })
  const [pendingFilters, setPendingFilters] = useState({ start: '', end: '', resource_id: '', project_id: '' })

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
    clientsApi.listClients().then(setClients).catch(() => {})
  }, [])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourcesById = useMemo(
    () =>
      Object.fromEntries(
        resources.map((r) => [r.id, { ...r, userName: usersById[r.user_id]?.name || resourceFunctionLevelLabel(r, labels) || r.id }]),
      ),
    [resources, usersById, labels],
  )
  const projectsById = useMemo(() => Object.fromEntries(projects.map((p) => [p.id, p])), [projects])
  const tasksById = useMemo(() => Object.fromEntries(allTasks.map((task) => [task.id, task])), [allTasks])
  // Tarefas "pai" (têm tarefas-filhas na EAP) continuam aparecendo no
  // seletor — pedido do usuário: elas ajudam o consultor a identificar a
  // etapa/tarefa-pai correspondente, já que tarefas-filha podem repetir
  // nome em etapas diferentes — mas ficam desabilitadas (apontamento só
  // nas tarefas-filha; a API também recusa, ver _resolve_task_and_project
  // em routers/timesheets.py).
  const parentTaskIds = useMemo(() => new Set(allTasks.map((task) => task.parent_task_id).filter(Boolean)), [allTasks])
  const taskOptions = useMemo(() => allTasks.filter((task) => task.project_id === form.project_id), [allTasks, form.project_id])
  const ownResource = useMemo(() => resources.find((r) => r.user_id === user.id) || null, [resources, user.id])
  // Projeto do filtro de "Meus apontamentos" — quando um cliente é
  // escolhido, restringe a lista aos projetos daquele cliente (mesmo
  // padrão de projectOptions já usado no form de novo apontamento acima).
  const mineProjectOptions = useMemo(
    () => (mineFilters.client_id ? projects.filter((p) => p.client_id === mineFilters.client_id) : projects),
    [projects, mineFilters.client_id],
  )
  // Projeto do filtro de "Aprovações pendentes" — INTERNAL_PM só vê (e só
  // consegue aprovar, ver GET /timesheets no backend) os projetos onde é o
  // gerente; ADMIN continua enxergando todos. Evita o combo oferecer um
  // projeto que, selecionado, sempre voltaria lista vazia pro PM.
  const pendingProjectOptions = useMemo(
    () => (user.role === 'INTERNAL_PM' ? projects.filter((p) => p.manager_id === user.id) : projects),
    [projects, user.role, user.id],
  )

  function loadMine() {
    if (!ownResource) {
      setMine([])
      setLoadingMine(false)
      return
    }
    setLoadingMine(true)
    timesheetsApi
      .listTimesheets({
        resource_id: ownResource.id,
        start: mineFilters.start || undefined,
        end: mineFilters.end || undefined,
        client_id: mineFilters.client_id || undefined,
        project_id: mineFilters.project_id || undefined,
      })
      .then(setMine)
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingMine(false))
  }

  useEffect(loadMine, [ownResource, mineFilters.start, mineFilters.end, mineFilters.client_id, mineFilters.project_id])

  function loadPending() {
    if (!canManage) return
    setLoadingPending(true)
    timesheetsApi
      .listTimesheets({
        status_filter: 'PENDING',
        start: pendingFilters.start || undefined,
        end: pendingFilters.end || undefined,
        resource_id: pendingFilters.resource_id || undefined,
        project_id: pendingFilters.project_id || undefined,
      })
      .then(setPending)
      .catch((err) => setListError(err.message))
      .finally(() => setLoadingPending(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadPending, [canManage, pendingFilters.start, pendingFilters.end, pendingFilters.resource_id, pendingFilters.project_id])

  function updateMineFilter(field) {
    return (event) => {
      const value = event.target.value
      // Trocar o cliente limpa o projeto selecionado, já que a lista de
      // projetos do filtro muda (mineProjectOptions) — evita ficar com um
      // project_id de outro cliente aplicado sem aparecer mais no <select>.
      setMineFilters((prev) => (field === 'client_id' ? { ...prev, client_id: value, project_id: '' } : { ...prev, [field]: value }))
    }
  }

  function updatePendingFilter(field) {
    return (event) => setPendingFilters((prev) => ({ ...prev, [field]: event.target.value }))
  }

  function updateField(field) {
    return (event) => {
      const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value
      setForm((prev) => {
        if (field === 'project_id') return { ...prev, project_id: value, task_id: '', is_transit: false }
        if (field === 'task_id') return { ...prev, task_id: value, is_transit: value ? false : prev.is_transit }
        if (field === 'is_transit') return { ...prev, is_transit: value, task_id: value ? '' : prev.task_id }
        return { ...prev, [field]: value }
      })
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
      if (entry.is_transit) {
        return { projectLabel: project ? `${project.code} — ${project.name}` : '—', taskLabel: t('Traslado'), typeLabel: labels.TASK_TYPE_LABELS.TRASLADO }
      }
      return { projectLabel: project ? `${project.code} — ${project.name}` : '—', taskLabel: t('Avulso'), typeLabel: labels.TASK_TYPE_LABELS.ADHOC }
    }
    return { projectLabel: t('Interno'), taskLabel: '—', typeLabel: t('Interno') }
  }

  function formTypeLabel() {
    if (form.is_transit) return labels.TASK_TYPE_LABELS.TRASLADO
    if (form.task_id) {
      const task = tasksById[form.task_id]
      return task ? labels.TASK_TYPE_LABELS[task.task_type] : '—'
    }
    if (form.project_id) return labels.TASK_TYPE_LABELS.ADHOC
    return t('Interno')
  }

  function handleEditClick(entry) {
    setEditingId(entry.id)
    setForm(entryToTimesheetForm(entry, tasksById))
    setFormError('')
  }

  function handleCancelEdit() {
    setEditingId(null)
    setForm(emptyTimesheetForm(todayIso()))
    setFormError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError('')
    setSaving(true)
    try {
      const payload = timesheetFormToPayload(form)
      if (editingId) await timesheetsApi.updateTimesheet(editingId, payload)
      else await timesheetsApi.createTimesheet(payload)
      setForm(emptyTimesheetForm(todayIso()))
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

  const preview = previewTimesheetHours(form)

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
            <TimesheetFieldsForm
              form={form}
              updateField={updateField}
              projects={projects}
              taskOptions={taskOptions}
              parentTaskIds={parentTaskIds}
              formTypeLabel={formTypeLabel}
              preview={preview}
            />

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
        <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
          <FormField label={t('Data inicial')}>
            <TextInput type="date" value={mineFilters.start} onChange={updateMineFilter('start')} />
          </FormField>
          <FormField label={t('Data final')}>
            <TextInput type="date" value={mineFilters.end} onChange={updateMineFilter('end')} />
          </FormField>
          <FormField label={t('Cliente')}>
            <Select value={mineFilters.client_id} onChange={updateMineFilter('client_id')}>
              <option value="">{t('Todos')}</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.legal_name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Projeto')}>
            <Select value={mineFilters.project_id} onChange={updateMineFilter('project_id')}>
              <option value="">{t('Todos')}</option>
              {mineProjectOptions.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.code} — {project.name}
                </option>
              ))}
            </Select>
          </FormField>
        </div>
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
                  isTimesheetEditable(row) ? (
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
          <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <FormField label={t('Data inicial')}>
              <TextInput type="date" value={pendingFilters.start} onChange={updatePendingFilter('start')} />
            </FormField>
            <FormField label={t('Data final')}>
              <TextInput type="date" value={pendingFilters.end} onChange={updatePendingFilter('end')} />
            </FormField>
            <FormField label={t('Consultor')}>
              <Select value={pendingFilters.resource_id} onChange={updatePendingFilter('resource_id')}>
                <option value="">{t('Todos')}</option>
                {resources.map((r) => (
                  <option key={r.id} value={r.id}>
                    {resourcesById[r.id]?.userName || r.id}
                  </option>
                ))}
              </Select>
            </FormField>
            <FormField label={t('Projeto')}>
              <Select value={pendingFilters.project_id} onChange={updatePendingFilter('project_id')}>
                <option value="">{t('Todos')}</option>
                {pendingProjectOptions.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.code} — {project.name}
                  </option>
                ))}
              </Select>
            </FormField>
          </div>
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
