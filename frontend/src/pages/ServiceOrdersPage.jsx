import { Fragment, useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
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
import ServiceOrderPrintSheet from '../components/ServiceOrderPrintSheet'
import ServiceOrderListPrintSheet from '../components/ServiceOrderListPrintSheet'
import { FormField, TextInput, Select } from '../components/FormField'
import { CheckIcon, XIcon, PencilIcon, TrashIcon, EyeIcon, PrinterIcon, DownloadIcon } from '../components/icons'
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

/** Chave estável de uma Ordem de Serviço (mesmo agrupamento do backend —
 * 1 OS por dia + projeto + consultor, ver `service_orders` em
 * services.py) — usada como key de linha, id de expansão (Detalhes) e alvo
 * de impressão de uma OS específica. */
function orderKey(order) {
  return `${order.date}-${order.project_id}-${order.resource_id}`
}

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
  // Detalhes: linhas expandidas mostrando os apontamentos de cada OS.
  const [expandedKeys, setExpandedKeys] = useState(() => new Set())
  // Impressão: null (nada), 'all' (botão do topo — lista de todas as OS
  // filtradas, agrupada por consultor, ver ServiceOrderListPrintSheet) ou
  // a orderKey de uma linha específica (botão Imprimir da linha — o
  // documento oficial de UMA OS, ver ServiceOrderPrintSheet).
  const [printTarget, setPrintTarget] = useState(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    resourcesApi.listResources().then(setResources).catch(() => {})
    usersApi.listUsers().then(setUsers).catch(() => {})
    clientsApi.listClients().then(setClients).catch(() => {})
    // Tarefas de todos os projetos — usadas tanto pro combo Tarefa do modal
    // de Editar (TimesheetEditModal) quanto pro "Tipo Apunte" da OS impressa
    // (ServiceOrderPrintSheet resolve Task.task_type a partir daqui).
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

  function toggleExpanded(key) {
    setExpandedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
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

  /** Aprovar/Rejeitar direto na linha-resumo da OS (sem abrir Detalhes) —
   * aplica a MESMA mudança de status a todos os apontamentos passados
   * (sempre só os PENDING/aprováveis, já filtrados por quem chama), uma
   * chamada por apontamento (mesma rota de sempre, PATCH /timesheets/
   * {id}/status — não existe endpoint de aprovação em lote). */
  async function handleBulkStatus(order, activities, newStatus) {
    setActingId(orderKey(order))
    setError('')
    try {
      for (const activity of activities) {
        await timesheetsApi.updateTimesheetStatus(activity.id, newStatus)
      }
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
   * entryToTimesheetForm em utils/timesheetForm.js). */
  function openEdit(order, activity) {
    setEditingEntry({ ...activity, date: order.date, project_id: order.project_id })
  }

  /** Resumo dos filtros ativos (rótulos, não os ids crus) pro cabeçalho da
   * impressão da lista (ServiceOrderListPrintSheet) — sempre mostra o
   * período; Consultor/Cliente/Projeto só entram quando o filtro está
   * ativo. */
  const filterSummaryLines = useMemo(() => {
    const lines = [`${t('Período')}: ${formatDate(filters.start)} – ${formatDate(filters.end)}`]
    if (filters.resource_id) {
      const resource = resourceOptions.find((r) => r.id === filters.resource_id)
      if (resource) lines.push(`${t('Consultor')}: ${resource.userName}`)
    }
    if (filters.client_id) {
      const client = clients.find((c) => c.id === filters.client_id)
      if (client) lines.push(`${t('Cliente')}: ${client.legal_name}`)
    }
    if (filters.project_id) {
      const project = projects.find((p) => p.id === filters.project_id)
      if (project) lines.push(`${t('Projeto')}: ${project.code} — ${project.name}`)
    }
    return lines
  }, [filters, resourceOptions, clients, projects, t])

  async function handleExport() {
    setExporting(true)
    setError('')
    try {
      await reportsApi.downloadServiceOrdersXlsx(
        {
          resource_id: filters.resource_id || undefined,
          client_id: filters.client_id || undefined,
          project_id: filters.project_id || undefined,
          start: filters.start || undefined,
          end: filters.end || undefined,
        },
        `ordens_de_servico_${filters.start}_${filters.end}.xlsx`,
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setExporting(false)
    }
  }

  const printOrders = useMemo(() => {
    if (!printTarget) return []
    if (printTarget === 'all') return orders
    return orders.filter((order) => orderKey(order) === printTarget)
  }, [printTarget, orders])

  // Dispara o diálogo de impressão do navegador assim que a folha (ou
  // folhas) alvo estiver renderizada no portal abaixo; volta pra null
  // depois (evento nativo 'afterprint' — cobre tanto imprimir quanto
  // cancelar o diálogo).
  useEffect(() => {
    if (printOrders.length === 0) return
    const raf = requestAnimationFrame(() => window.print())
    return () => cancelAnimationFrame(raf)
  }, [printOrders])

  useEffect(() => {
    function handleAfterPrint() {
      setPrintTarget(null)
    }
    window.addEventListener('afterprint', handleAfterPrint)
    return () => window.removeEventListener('afterprint', handleAfterPrint)
  }, [])

  return (
    <div className="print:hidden">
      <PageHeader
        title={t('Ordens de Serviço')}
        subtitle={t(
          'Cada Ordem de Serviço agrupa os apontamentos de um consultor, projeto e dia — clique em Detalhes para ver os itens.',
        )}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={handleExport} disabled={exporting || orders.length === 0}>
              <DownloadIcon size={16} />
              {t('Exportar (Excel)')}
            </Button>
            <Button variant="secondary" onClick={() => setPrintTarget('all')} disabled={orders.length === 0}>
              {t('Imprimir')}
            </Button>
          </div>
        }
      />

      <Card className="mb-4">
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
        <Card dense>
          <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-left text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                <th className="px-3 py-2">{t('Nº OS')}</th>
                <th className="px-3 py-2">{t('Data')}</th>
                <th className="px-3 py-2">{t('Cliente')}</th>
                <th className="px-3 py-2">{t('Projeto')}</th>
                <th className="px-3 py-2">{t('Consultor')}</th>
                <th className="px-3 py-2 text-center">{t('Itens')}</th>
                <th className="px-3 py-2 text-right">{t('Total')}</th>
                <th className="px-3 py-2">{t('Status')}</th>
                <th className="px-3 py-2 text-right">{''}</th>
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => {
                const key = orderKey(order)
                const expanded = expandedKeys.has(key)
                const own = Boolean(ownResource && order.resource_id === ownResource.id)
                const pendingActivities = order.activities.filter((a) => a.status === 'PENDING')
                const approvableActivities = pendingActivities.filter((a) => !(a.unscheduled && user.role !== 'ADMIN'))
                const canApproveRow = canManage && pendingActivities.length > 0
                const ownEditable = own ? order.activities.filter((a) => isTimesheetEditable(a)) : []
                const singleEditable = ownEditable.length === 1 ? ownEditable[0] : null
                const allApproved = order.activities.every((a) => a.status === 'APPROVED')
                const anyUnscheduled = order.activities.some((a) => a.unscheduled)

                return (
                  <Fragment key={key}>
                    <tr className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--page)]">
                      <td className="px-3 py-2 tabular text-[var(--text-secondary)]" title={t('Emitida em {date}', { date: formatDate(order.emitted_at) })}>
                        {order.order_number}
                      </td>
                      <td className="px-3 py-2 font-medium text-[var(--text-primary)]">{formatDate(order.date)}</td>
                      <td className="px-3 py-2">
                        <p className="text-[var(--text-primary)]">{order.client_name}</p>
                        <p className="text-xs text-[var(--text-muted)]">{order.client_code}</p>
                      </td>
                      <td className="px-3 py-2">
                        <p className="text-[var(--text-primary)]">{order.project_name}</p>
                        <p className="text-xs text-[var(--text-muted)]">{order.project_code}</p>
                      </td>
                      <td className="px-3 py-2 text-[var(--text-primary)]">{order.resource_name}</td>
                      <td className="px-3 py-2 text-center text-[var(--text-secondary)]">{order.activities.length}</td>
                      <td className="px-3 py-2 text-right font-medium text-[var(--text-primary)]">{formatHoursDuration(order.total_hours)}</td>
                      <td className="px-3 py-2">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <StatusPill
                            label={allApproved ? labels.TIMESHEET_STATUS_LABELS.APPROVED : labels.TIMESHEET_STATUS_LABELS.PENDING}
                            tone={allApproved ? TIMESHEET_STATUS_TONE.APPROVED : TIMESHEET_STATUS_TONE.PENDING}
                          />
                          {anyUnscheduled && <StatusPill label={t('Fora da agenda')} tone="serious" />}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex justify-end gap-1.5">
                          <IconButton
                            icon={EyeIcon}
                            label={t('Detalhes')}
                            variant={expanded ? 'primary' : 'secondary'}
                            onClick={() => toggleExpanded(key)}
                          />
                          {canApproveRow && (
                            <>
                              <IconButton
                                icon={CheckIcon}
                                label={t('Aprovar')}
                                disabled={actingId === key || approvableActivities.length === 0}
                                title={approvableActivities.length === 0 ? t('Só o Administrador pode aprovar apontamentos fora da agenda.') : t('Aprovar')}
                                onClick={() => handleBulkStatus(order, approvableActivities, 'APPROVED')}
                              />
                              <IconButton
                                icon={XIcon}
                                label={t('Rejeitar')}
                                variant="danger"
                                disabled={actingId === key}
                                onClick={() => handleBulkStatus(order, pendingActivities, 'REJECTED')}
                              />
                            </>
                          )}
                          {singleEditable && (
                            <>
                              <IconButton icon={PencilIcon} label={t('Editar')} onClick={() => openEdit(order, singleEditable)} />
                              <IconButton
                                icon={TrashIcon}
                                label={t('Excluir')}
                                variant="danger"
                                onClick={() =>
                                  setDeletingEntry({
                                    activity: { ...singleEditable, date: order.date },
                                    label: activityLabel(order, singleEditable),
                                  })
                                }
                              />
                            </>
                          )}
                          <IconButton icon={PrinterIcon} label={t('Imprimir')} onClick={() => setPrintTarget(key)} />
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr className="border-b border-[var(--border)] last:border-0 bg-[var(--page)]">
                        <td colSpan={9} className="px-3 py-3">
                          <table className="w-full border-collapse text-sm">
                            <thead>
                              <tr className="border-b border-[var(--border)] text-left text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                                <th className="px-2 py-1.5">{t('Atividade')}</th>
                                <th className="px-2 py-1.5">{t('Horário')}</th>
                                <th className="px-2 py-1.5 text-right">{t('Intervalo')}</th>
                                <th className="px-2 py-1.5 text-right">{t('Total')}</th>
                                <th className="px-2 py-1.5">{t('Descrição')}</th>
                                <th className="px-2 py-1.5">{t('Status')}</th>
                                <th className="px-2 py-1.5 text-right">{''}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {order.activities.map((activity) => {
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
                                    <td className="px-2 py-1.5 text-right">
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
                                                onClick={() =>
                                                  setDeletingEntry({ activity: { ...activity, date: order.date }, label: activityLabel(order, activity) })
                                                }
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
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
          </div>
        </Card>
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

      {printOrders.length > 0 &&
        createPortal(
          <div className="hidden print:block">
            {printTarget === 'all' ? (
              <ServiceOrderListPrintSheet orders={printOrders} filterSummary={filterSummaryLines} />
            ) : (
              printOrders.map((order) => <ServiceOrderPrintSheet key={orderKey(order)} order={order} tasksById={tasksById} />)
            )}
          </div>,
          document.body,
        )}
    </div>
  )
}
