import { useEffect, useMemo, useState } from 'react'
import * as reportsApi from '../api/reports'
import * as resourcesApi from '../api/resources'
import * as usersApi from '../api/users'
import * as clientsApi from '../api/clients'
import * as projectsApi from '../api/projects'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import StatTile from '../components/StatTile'
import Table from '../components/Table'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { FormField, Select, TextInput } from '../components/FormField'
import { formatHoursDuration } from '../utils/format'
import { resourceFunctionLevelLabel } from '../utils/labels'

function firstDayOfMonthIso() {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
}

function lastDayOfMonthIso() {
  const now = new Date()
  const last = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return `${last.getFullYear()}-${String(last.getMonth() + 1).padStart(2, '0')}-${String(last.getDate()).padStart(2, '0')}`
}

function formatPct(value) {
  if (value === null || value === undefined) return '—'
  return `${Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%`
}

/** Relatório "Horas normais × retrabalho" (pedido do usuário, menu
 * Relatórios): separa as horas de projeto entre normais e retrabalho e,
 * no retrabalho, soma por motivo. Conta pendentes + aprovadas; ausências,
 * traslado e horas internas ficam fora da análise (a ausência aparece só
 * como número de referência). Ver rework_hours_report em app/services.py. */
export default function ReworkReportPage() {
  const { t, labels } = useLanguage()

  const [resources, setResources] = useState([])
  const [users, setUsers] = useState([])
  const [clients, setClients] = useState([])
  const [projects, setProjects] = useState([])

  const [filters, setFilters] = useState({
    start: firstDayOfMonthIso(),
    end: lastDayOfMonthIso(),
    resource_id: '',
    client_id: '',
    project_id: '',
  })

  const [report, setReport] = useState(null)
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
    () =>
      resources.map((resource) => ({
        ...resource,
        userName: usersById[resource.user_id]?.name || resourceFunctionLevelLabel(resource, labels) || resource.id,
      })),
    [resources, usersById, labels],
  )
  const projectOptions = useMemo(
    () => (filters.client_id ? projects.filter((p) => p.client_id === filters.client_id) : projects),
    [projects, filters.client_id],
  )

  function loadReport() {
    setLoading(true)
    setError('')
    reportsApi
      .getReworkReport({
        start: filters.start || undefined,
        end: filters.end || undefined,
        resource_id: filters.resource_id || undefined,
        client_id: filters.client_id || undefined,
        project_id: filters.project_id || undefined,
      })
      .then(setReport)
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false))
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(loadReport, [filters.start, filters.end, filters.resource_id, filters.client_id, filters.project_id])

  function updateFilter(field) {
    return (event) => {
      const value = event.target.value
      setFilters((prev) => (field === 'client_id' ? { ...prev, client_id: value, project_id: '' } : { ...prev, [field]: value }))
    }
  }

  const totals = report?.totals
  // Motivos com horas primeiro (maior → menor); os zerados vão para o fim,
  // mantendo todos os motivos visíveis na tabela.
  const reasonRows = useMemo(
    () => [...(report?.by_reason || [])].sort((a, b) => Number(b.hours) - Number(a.hours)),
    [report],
  )
  const showAbsence = !filters.client_id && !filters.project_id

  return (
    <div>
      <PageHeader
        title={t('Horas normais × retrabalho')}
        subtitle={t('Horas de projeto separadas entre normais e retrabalho, com a soma de cada tipo de retrabalho (pendentes e aprovadas).')}
      />

      <Card className="mb-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
          <FormField label={t('Data inicial')}>
            <TextInput type="date" value={filters.start} onChange={updateFilter('start')} />
          </FormField>
          <FormField label={t('Data final')}>
            <TextInput type="date" value={filters.end} onChange={updateFilter('end')} />
          </FormField>
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
        </div>
      </Card>

      <ErrorBanner message={error} />

      {loading ? (
        <Spinner />
      ) : (
        report && (
          <>
            <Card title={t('Totais do período')} className="mb-4">
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <StatTile compact label={t('Horas normais')} value={formatHoursDuration(totals.normal_hours)} tone="primary" />
                <StatTile compact label={t('Horas de retrabalho')} value={formatHoursDuration(totals.rework_hours)} tone="warning" />
                <StatTile compact label={t('Total de horas de projeto')} value={formatHoursDuration(totals.total_hours)} tone="good" />
                <StatTile compact label={t('% de retrabalho')} value={formatPct(totals.rework_percentage)} tone="default" />
              </div>
              {showAbsence && (
                <p className="mt-3 text-xs text-[var(--text-muted)]">
                  {t('Referência (fora da análise): horas de ausência no período')}: {formatHoursDuration(totals.absence_hours)}
                </p>
              )}
            </Card>

            <Card title={t('Retrabalho por motivo')} className="mb-4">
              <Table
                columns={[
                  { key: 'reason', header: t('Motivo'), render: (row) => labels.REWORK_REASON_LABELS[row.reason] || row.reason },
                  { key: 'hours', header: t('Horas'), align: 'right', render: (row) => formatHoursDuration(row.hours) },
                  {
                    key: 'share',
                    header: t('% do retrabalho'),
                    render: (row) => (
                      <div className="flex items-center gap-2">
                        <div className="h-[8px] w-28 rounded-full bg-[var(--grid)]">
                          <div
                            className="h-[8px] rounded-full bg-[var(--series-1)]"
                            style={{ width: `${Math.min(100, Number(row.percentage || 0))}%` }}
                          />
                        </div>
                        <span className="tabular text-xs">{formatPct(row.percentage)}</span>
                      </div>
                    ),
                  },
                  { key: 'entries', header: t('Apontamentos'), align: 'right', render: (row) => row.entries },
                ]}
                rows={reasonRows}
                getRowKey={(row) => row.reason}
                emptyMessage={t('Nenhum retrabalho no período.')}
              />
            </Card>

            <Card title={t('Por consultor')} className="mb-4">
              <Table
                columns={[
                  { key: 'resource', header: t('Consultor'), render: (row) => row.resource_name },
                  { key: 'normal', header: t('Horas normais'), align: 'right', render: (row) => formatHoursDuration(row.normal_hours) },
                  { key: 'rework', header: t('Retrabalho'), align: 'right', render: (row) => formatHoursDuration(row.rework_hours) },
                  { key: 'pct', header: t('% de retrabalho'), align: 'right', render: (row) => formatPct(row.rework_percentage) },
                ]}
                rows={report.by_resource}
                getRowKey={(row) => row.resource_id}
                emptyMessage={t('Nenhuma hora de projeto no período.')}
              />
            </Card>

            <Card title={t('Por projeto')}>
              <Table
                columns={[
                  { key: 'client', header: t('Cliente'), render: (row) => row.client_name },
                  { key: 'project', header: t('Projeto'), render: (row) => `${row.project_code} — ${row.project_name}` },
                  { key: 'normal', header: t('Horas normais'), align: 'right', render: (row) => formatHoursDuration(row.normal_hours) },
                  { key: 'rework', header: t('Retrabalho'), align: 'right', render: (row) => formatHoursDuration(row.rework_hours) },
                  { key: 'pct', header: t('% de retrabalho'), align: 'right', render: (row) => formatPct(row.rework_percentage) },
                ]}
                rows={report.by_project}
                getRowKey={(row) => row.project_id}
                emptyMessage={t('Nenhuma hora de projeto no período.')}
              />
            </Card>
          </>
        )
      )}
    </div>
  )
}
