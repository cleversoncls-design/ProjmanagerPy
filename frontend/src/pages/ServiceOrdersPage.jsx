import { useEffect, useMemo, useState } from 'react'
import * as reportsApi from '../api/reports'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as clientsApi from '../api/clients'
import * as projectsApi from '../api/projects'
import * as tasksApi from '../api/tasks'
import * as timesheetsApi from '../api/timesheets'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import IconButton from '../components/IconButton'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import StatusPill from '../components/StatusPill'
import TimesheetEditModal from '../components/TimesheetEditModal'
import TimesheetDeleteModal from '../components/TimesheetDeleteModal'
import { FormField, TextInput, Select } from '../components/FormField'
import { CheckIcon, XIcon, PencilIcon, TrashIcon } from '../components/icons'
import { formatDate, formatTime, formatHoursDuration, minutesToHM } from '../utils/format'
import { MANAGEMENT_ROLES, TIMESHEET_STATUS_TONE } from '../utils/labels'
import { isTimesheetEditable } from '../utils/timesheetForm'

function todayIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}

function daysAgoIso(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

const EMPTY_FILTERS = { resource_id: '', client_id: '', project_id: '', start: daysAgoIso(30), end: todayIso() }

export default function ServiceOrdersPage() {
  const { user } = useAuth()
  const { labels, t } = useLanguage()
  const canManage = MANAGEMENT_ROLES.includes(user.role)

  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [projects, setProjects] = useState([])
  const [allTasks, setAllTasks] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actingId, setActingId] = useState(null)
  const [editingEntry, setEditingEntry] = useState(null)
  const [deletingEntry, setDeletingEntry] = useState(null)

  useEffect(() => {
    resourcesApi.listResources().then(setResources).catch(() => {})
    usersApi.listUsers().then(setUsers).catch(() => {})
    clientsApi.listClients().then(setClients).catch(() => {})
    // Tarefas de todos os projetos — só usadas pra popular o combo Tarefa
    // do modal de Editar (TimesheetEditModal), mesmo padrão de
    // TimesheetsPage.jsx (ver allTasks lá).
    projectsApi.listProjects().then((rows) => {
      setProjects(rows)
      Promise.all(rows.map((p) => tasksApi.listTasks(p.id).catch(() => []))).then((lists) => setAllTasks(lists.flat()))
    })
  }, [])

  const usersById = useMemo(() => Object.fromEntries(users.map((u) => [u.id, u])), [users])
  const resourceOptions = useMemo(
    () => resources.map((r) => ({ ...r, userName: usersById[r.user_id]?.name || r.role_title })),
    [resources, usersById],
  )
  const projectOptions = useMemo(
    () => (filters.client_id ? projects.filter((p) => p.client_id === filters.client_id) : projects),
    [projects, filters.client_id],
  )
  const tasksById = useMemo(() => Object.fromEntries(allTasks.map((task) => [task.id, task])), [allTasks])
  // Recurso do usuário logado — só ele (nunca outro consultor, mesmo pra
  // quem gerencia) enxerga Editar/Excluir numa linha da OS; ver mesma regra
  // em TimesheetsPage "Meus apontamentos".
  const ownResource = useMemo(() => resources.find((r) => r.user_id === user.id) || null, [resources, user.id])

  function loadOrders() {
    setLoading(true)
    setError('')
    reportsApi
      .getServiceOrders({
        resource_id: filters.resource_id || undefined,
        client_id: filters.client_id || undefined,
        project_id: filters.project_id || undefined,
        start: filters.start || undefined,
        end: filters.end || undefined,
      })
      .then(setOrders)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(loadOrders, [filters.resource_id, filters.client_id, filters.project_id, filters.start, filters.end])

  function updateFilter(field) {
    return (event) => setFilters((prev) => ({ ...prev, [field]: event.target.value }))
  }

  async function handleStatus(activity, newStatus) {
    setActingId(activity.id)
    setError('')
    try {
      await timesheetsApi.updateTimesheetStatus(activity.id, newStatus)
      loadOrders()
    } catch (err) {
      setError(err.message)
    } finally {
      setActingId(null)
    }
  }

  /** Rótulo pro modal de Editar/o modal de Excluir — a atividade da OS já
   * traz wbs_code/task_name resolvidos (sem precisar de tasksById/
   * projectsById como em TimesheetsPage), então monta direto a partir da
   * própria linha + do cabeçalho da Ordem de Serviço (`order`). */
  function activityLabel(order, activity) {
    return {
      projectLabel: `${order.project_code} — ${order.project_name}`,
      taskLabel: activity.wbs_code ? `${activity.wbs_code} ${activity.task_name}` : t('Avulso'),
    }
  }

  /** `ServiceOrderActivity` não repete `date`/`project_id` (vêm do
   * `ServiceOrderRow` que a contém) — completa os dois antes de passar pro
   * TimesheetEditModal, que espera o mesmo formato de TimesheetRead (ver
   * entryToTimesheetForm em utils/timesheetForm.js). `project_id` do
   * pedido é sempre o projeto efetivo da atividade (Task.project_id ou
   * Timesheet.project_id — o mesmo `project_col` usado em
   * services.py::service_orders), então serve tanto pro caso avulso
   * quanto o com tarefa (nesse último, entryToTimesheetForm nem usa este
   * campo — pega o projeto da própria tarefa). */
  function openEdit(order, activity) {
    setEditingEntry({ ...activity, date: order.date, project_id: order.project_id })
  }

  return (
    <div>
      <PageHeader
        title={t('Ordens de Serviço')}
        subtitle={t('Prévia da OS a partir dos apontamentos — o modelo final de impressão ainda será definido.')}
        action={
          <Button variant="secondary" className="print:hidden" onClick={() => window.print()}>
            {t('Imprimir')}
          </Button>
        }
      />

      <Card className="mb-4 print:hidden">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <FormField label={t('Consultor')}>
            <Select value={filters.resource_id} onChange={updateFilter('resource_id')}>
              <option value="">{t('Todos')}</option>
              {resourceOptions.map((resource) => (
                <option key={resource.id} value={resource.id}>
                  {resource.userName}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Cliente')}>
            <Select value={filters.client_id} onChange={updateFilter('client_id')}>
              <option value="">{t('Todos')}</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.legal_name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Projeto')}>
            <Select value={filters.project_id} onChange={updateFilter('project_id')}>
              <option value="">{t('Todos')}</option>
              {projectOptions.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.code} — {project.name}
                </option>
              ))}
            </Select>
          </FormField>
          <FormField label={t('Data inicial')}>
            <TextInput type="date" value={filters.start} onChange={updateFilter('start')} />
          </FormField>
          <FormField label={t('Data final')}>
            <TextInput type="date" value={filters.end} onChange={updateFilter('end')} />
          </FormField>
        </div>
      </Card>

      <ErrorBanner message={error} />

      {loading ? (
        <Spinner />
      ) : orders.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--text-secondary)]">{t('Nenhuma Ordem de Serviço no período filtrado.')}</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {orders.map((order) => (
            <Card key={`${order.date}-${order.project_id}-${order.resource_id}`} className="break-inside-avoid">
              <div className="mb-4 flex flex-wrap items-start justify-between gap-3 border-b border-[var(--border)] pb-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-muted)]">{t('Ordem de Serviço')}</p>
                  <p className="text-base font-semibold text-[var(--text-primary)]">{formatDate(order.date)}</p>
                </div>
                <div className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm md:grid-cols-4">
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">{t('Código do cliente')}</p>
                    <p className="font-medium text-[var(--text-primary)]">{order.client_code}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">{t('Cliente')}</p>
                    <p className="font-medium text-[var(--text-primary)]">{order.client_name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">{t('Código do projeto')}</p>
                    <p className="font-medium text-[var(--text-primary)]">{order.project_code}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">{t('Projeto')}</p>
                    <p className="font-medium text-[var(--text-primary)]">{order.project_name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">{t('Consultor')}</p>
                    <p className="font-medium text-[var(--text-primary)]">{order.resource_name}</p>
                  </div>
                  <div>
                    <p className="text-xs text-[var(--text-muted)]">{t('Total de horas')}</p>
                    <p className="font-medium text-[var(--text-primary)]">{formatHoursDuration(order.total_hours)}</p>
                  </div>
                </div>
              </div>

              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    <th className="px-2 py-1.5">{t('Atividade')}</th>
                    <th className="px-2 py-1.5">{t('Horário')}</th>
                    <th className="px-2 py-1.5 text-right">{t('Intervalo')}</th>
                    <th className="px-2 py-1.5 text-right">{t('Total')}</th>
                    <th className="px-2 py-1.5">{t('Descrição')}</th>
                    <th className="px-2 py-1.5">{t('Status')}</th>
                    <th className="px-2 py-1.5 text-right print:hidden">{''}</th>
                  </tr>
                </thead>
                <tbody>
                  {order.activities.map((activity) => {
                    const own = ownResource && order.resource_id === ownResource.id
                    const canApprove = canManage && activity.status === 'PENDING'
                    const canEdit = own && isTimesheetEditable(activity)
                    const blockedForMe = activity.unscheduled && user.role !== 'ADMIN'
                    return (
                      <tr key={activity.id} className="border-b border-[var(--border)] last:border-0">
                        <td className="px-2 py-1.5 text-[var(--text-primary)]">
                          {activity.wbs_code ? `${activity.wbs_code} — ${activity.task_name}` : t('Avulso')}
                        </td>
                        <td className="px-2 py-1.5 whitespace-nowrap text-[var(--text-secondary)]">
                          {formatTime(activity.start_time)}–{formatTime(activity.end_time)}
                        </td>
                        <td className="px-2 py-1.5 text-right text-[var(--text-secondary)]">{minutesToHM(activity.break_minutes)}</td>
                        <td className="px-2 py-1.5 text-right font-medium text-[var(--text-primary)]">{formatHoursDuration(activity.hours)}</td>
                        <td className="px-2 py-1.5 text-[var(--text-secondary)]">{activity.description || '—'}</td>
                        <td className="px-2 py-1.5">
                          <div className="flex items-center gap-1.5">
                            <StatusPill
                              label={labels.TIMESHEET_STATUS_LABELS[activity.status] || activity.status}
                              tone={TIMESHEET_STATUS_TONE[activity.status]}
                            />
                            {activity.unscheduled && <StatusPill label={t('Fora da agenda')} tone="serious" />}
                          </div>
                        </td>
                        <td className="px-2 py-1.5 text-right print:hidden">
                          {canApprove || canEdit ? (
                            <div className="flex justify-end gap-1.5">
                              {canApprove && (
                                <>
                                  <IconButton
                                    icon={CheckIcon}
                                    label={t('Aprovar')}
                                    disabled={actingId === activity.id || blockedForMe}
                                    title={blockedForMe ? t('Só o Administrador pode aprovar apontamentos fora da agenda.') : t('Aprovar')}
                                    onClick={() => handleStatus(activity, 'APPROVED')}
                                  />
                                  <IconButton
                                    icon={XIcon}
                                    label={t('Rejeitar')}
                                    variant="danger"
                                    disabled={actingId === activity.id}
                                    onClick={() => handleStatus(activity, 'REJECTED')}
                                  />
                                </>
                              )}
                              {canEdit && (
                                <>
                                  <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => openEdit(order, activity)} />
                                  <IconButton
                                    icon={TrashIcon}
                                    label={t('Excluir')}
                                    variant="danger"
                                    onClick={() => setDeletingEntry({ activity: { ...activity, date: order.date }, label: activityLabel(order, activity) })}
                                  />
                                </>
                              )}
                            </div>
                          ) : (
                            <span className="text-xs text-[var(--text-muted)]">—</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}

      {editingEntry && (
        <TimesheetEditModal
          entry={editingEntry}
          projects={projects}
          allTasks={allTasks}
          tasksById={tasksById}
          labels={labels}
          onClose={() => setEditingEntry(null)}
          onSaved={() => {
            setEditingEntry(null)
            loadOrders()
          }}
        />
      )}

      {deletingEntry && (
        <TimesheetDeleteModal
          entry={deletingEntry.activity}
          entryLabel={deletingEntry.label}
          onClose={() => setDeletingEntry(null)}
          onDeleted={() => {
            setDeletingEntry(null)
            loadOrders()
          }}
        />
      )}
    </div>
  )
}
