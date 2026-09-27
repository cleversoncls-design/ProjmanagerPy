import { useEffect, useMemo, useState } from 'react'
import * as reportsApi from '../api/reports'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as clientsApi from '../api/clients'
import * as projectsApi from '../api/projects'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import Button from '../components/Button'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, TextInput, Select } from '../components/FormField'
import { formatDate, formatTime } from '../utils/format'

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
  const { t } = useLanguage()

  const [filters, setFilters] = useState(EMPTY_FILTERS)
  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [projects, setProjects] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    resourcesApi.listResources().then(setResources).catch(() => {})
    usersApi.listUsers().then(setUsers).catch(() => {})
    clientsApi.listClients().then(setClients).catch(() => {})
    projectsApi.listProjects().then(setProjects).catch(() => {})
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
                    <p className="font-medium text-[var(--text-primary)]">{Number(order.total_hours).toFixed(2)}</p>
                  </div>
                </div>
              </div>

              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">
                    <th className="px-2 py-1.5">{t('Atividade')}</th>
                    <th className="px-2 py-1.5">{t('Horário')}</th>
                    <th className="px-2 py-1.5 text-right">{t('Intervalo (min)')}</th>
                    <th className="px-2 py-1.5 text-right">{t('Total')}</th>
                    <th className="px-2 py-1.5">{t('Descrição')}</th>
                  </tr>
                </thead>
                <tbody>
                  {order.activities.map((activity, index) => (
                    <tr key={index} className="border-b border-[var(--border)] last:border-0">
                      <td className="px-2 py-1.5 text-[var(--text-primary)]">
                        {activity.wbs_code ? `${activity.wbs_code} — ${activity.task_name}` : t('Avulso')}
                      </td>
                      <td className="px-2 py-1.5 whitespace-nowrap text-[var(--text-secondary)]">
                        {formatTime(activity.start_time)}–{formatTime(activity.end_time)}
                      </td>
                      <td className="px-2 py-1.5 text-right text-[var(--text-secondary)]">{activity.break_minutes}</td>
                      <td className="px-2 py-1.5 text-right font-medium text-[var(--text-primary)]">{Number(activity.hours).toFixed(2)}</td>
                      <td className="px-2 py-1.5 text-[var(--text-secondary)]">{activity.description || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
