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

function sumAbsenceHours(absenceHours) {
  return Object.values(absenceHours || {}).reduce((total, hours) => total + Number(hours), 0)
}

/** Relatório "Horas por tipo" (pedido do usuário, menu Relatórios) — o
 * primeiro a juntar, num só lugar, horas de Projeto (cliente), Traslado e
 * Ausência, que hoje só davam pra ver espalhadas (Financeiro é por projeto
 * e nunca mostra Ausência; Aprovações/Meus apontamentos são lista crua,
 * sem totalizador). Dois níveis (decisão confirmada): totais da empresa
 * (cards no topo, com cada tipo de ausência aberto) + quebra por consultor
 * (tabela, com Ausência somada — o detalhe por tipo fica nos cards do
 * total geral, pra não deixar a tabela larga demais). */
export default function HoursBreakdownReportPage() {
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
  // Mesmo critério de filtros já usados em outras telas (Agenda, Meus
  // apontamentos): trocar o cliente restringe a lista de projetos do filtro.
  const projectOptions = useMemo(
    () => (filters.client_id ? projects.filter((p) => p.client_id === filters.client_id) : projects),
    [projects, filters.client_id],
  )

  function loadReport() {
    setLoading(true)
    setError('')
    reportsApi
      .getHoursBreakdown({
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
  const totalGeral = totals
    ? Number(totals.project_hours) + Number(totals.transit_hours) + Number(totals.internal_hours) + sumAbsenceHours(totals.absence_hours)
    : 0

  return (
    <div>
      <PageHeader
        title={t('Horas por tipo (Projeto, Traslado e Ausência)')}
        subtitle={t('Totais da empresa e por consultor — horas de projeto por cliente, Traslado e cada tipo de ausência, num período.')}
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
                <StatTile compact label={t('Horas de projeto')} value={formatHoursDuration(totals.project_hours)} tone="primary" />
                <StatTile compact label={t('Traslado')} value={formatHoursDuration(totals.transit_hours)} tone="default" />
                <StatTile compact label={t('Interno')} value={formatHoursDuration(totals.internal_hours)} tone="default" />
                <StatTile compact label={t('Total geral')} value={formatHoursDuration(totalGeral)} tone="good" />
                {Object.entries(labels.ABSENCE_TYPE_LABELS).map(([value, label]) => (
                  <StatTile key={value} compact label={label} value={formatHoursDuration(totals.absence_hours[value])} tone="warning" />
                ))}
              </div>
            </Card>

            <Card title={t('Por consultor')} className="mb-4">
              <Table
                columns={[
                  { key: 'resource', header: t('Consultor'), render: (row) => row.resource_name },
                  { key: 'project', header: t('Horas de projeto'), align: 'right', render: (row) => formatHoursDuration(row.project_hours) },
                  { key: 'transit', header: t('Traslado'), align: 'right', render: (row) => formatHoursDuration(row.transit_hours) },
                  {
                    key: 'absence',
                    header: t('Ausência'),
                    align: 'right',
                    render: (row) => formatHoursDuration(sumAbsenceHours(row.absence_hours)),
                  },
                  { key: 'internal', header: t('Interno'), align: 'right', render: (row) => formatHoursDuration(row.internal_hours) },
                  {
                    key: 'total',
                    header: t('Total'),
                    align: 'right',
                    render: (row) =>
                      formatHoursDuration(
                        Number(row.project_hours) + Number(row.transit_hours) + Number(row.internal_hours) + sumAbsenceHours(row.absence_hours),
                      ),
                  },
                ]}
                rows={report.by_resource}
                getRowKey={(row) => row.resource_id}
                emptyMessage={t('Nenhum apontamento no período.')}
              />
            </Card>

            <Card title={t('Por projeto')}>
              <Table
                columns={[
                  { key: 'client', header: t('Cliente'), render: (row) => row.client_name },
                  { key: 'project', header: t('Projeto'), render: (row) => `${row.project_code} — ${row.project_name}` },
                  { key: 'hours', header: t('Horas'), align: 'right', render: (row) => formatHoursDuration(row.hours) },
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
