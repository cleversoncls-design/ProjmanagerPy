import { useEffect, useState } from 'react'
import * as ticketsApi from '../api/tickets'
import { useLanguage } from '../context/LanguageContext'
import Card from './Card'
import CategoryBars from './CategoryBars'
import ErrorBanner from './ErrorBanner'
import Spinner from './Spinner'
import StatTile from './StatTile'
import StatusPill from './StatusPill'
import Table from './Table'
import { formatHoursDuration } from '../utils/format'
import { TICKET_CRITICALITY_TONE, TICKET_STATUS_TONE } from '../utils/labels'

// Cores fixas por categoria (nunca pela posição na lista).
const CRITICALITY_COLORS = {
  LOW: 'var(--text-muted)',
  MEDIUM: 'var(--status-warning)',
  HIGH: 'var(--status-serious)',
  CRITICAL: 'var(--status-critical)',
}
const STATUS_COLORS = {
  OPEN: 'var(--status-warning)',
  ASSIGNED: 'var(--text-muted)',
  IN_PROGRESS: 'var(--series-1)',
  WAITING_REQUESTER: 'var(--status-serious)',
  RESOLVED: 'var(--status-good)',
  CLOSED: 'var(--grid)',
}

/** Indicadores dos tickets para gerentes. Respeita o projeto/cliente
 * escolhidos nos filtros da lista. `reloadKey` força nova busca quando algo
 * mudou num ticket. Endpoint: GET /tickets-indicators. */
export default function TicketIndicators({ projectId = null, clientId = '', reloadKey = 0 }) {
  const { t, labels } = useLanguage()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    setError('')
    ticketsApi
      .getTicketIndicators({ project_id: projectId || undefined, client_id: clientId || undefined })
      .then((result) => active && setData(result))
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [projectId, clientId, reloadKey])

  if (loading && !data) {
    return (
      <Card title={t('Indicadores dos tickets')}>
        <Spinner />
      </Card>
    )
  }
  if (error) {
    return (
      <Card title={t('Indicadores dos tickets')}>
        <ErrorBanner message={error} />
      </Card>
    )
  }
  if (!data) return null

  const criticalityItems = Object.keys(labels.TICKET_CRITICALITY_LABELS)
    .reverse()
    .map((key) => ({
      key,
      label: labels.TICKET_CRITICALITY_LABELS[key],
      value: data.open_by_criticality[key] || 0,
      color: CRITICALITY_COLORS[key],
    }))
  const statusItems = Object.keys(labels.TICKET_STATUS_LABELS).map((key) => ({
    key,
    label: labels.TICKET_STATUS_LABELS[key],
    value: data.by_status[key] || 0,
    color: STATUS_COLORS[key],
  }))
  const agingItems = data.aging_buckets.map((bucket, index) => ({
    key: bucket.label,
    label: t(bucket.label),
    value: bucket.count,
    color: ['var(--series-1)', 'var(--status-warning)', 'var(--status-serious)', 'var(--status-critical)'][index],
  }))

  const oldestColumns = [
    { key: 'code', header: t('Ticket'), nowrap: true, render: (row) => row.code },
    { key: 'title', header: t('Título'), render: (row) => row.title },
    { key: 'project', header: t('Projeto'), nowrap: true, render: (row) => row.project_code },
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
    { key: 'assignee', header: t('Responsável'), render: (row) => row.assignee_name || '—' },
    { key: 'age', header: t('Dias em aberto'), align: 'right', render: (row) => row.age_days },
  ]
  const projectColumns = [
    { key: 'project', header: t('Projeto'), render: (row) => `${row.project_code} — ${row.project_name}` },
    { key: 'total', header: t('Tickets'), align: 'right', render: (row) => row.tickets_total },
    { key: 'open', header: t('Abertos'), align: 'right', render: (row) => row.tickets_open },
    { key: 'logged', header: t('Horas apontadas'), align: 'right', render: (row) => formatHoursDuration(row.hours_logged) },
    { key: 'approved', header: t('Horas aprovadas'), align: 'right', render: (row) => formatHoursDuration(row.hours_approved) },
  ]
  const workloadColumns = [
    { key: 'name', header: t('Responsável'), render: (row) => row.name },
    { key: 'open', header: t('Tickets abertos'), align: 'right', render: (row) => row.open_tickets },
    { key: 'logged', header: t('Horas apontadas'), align: 'right', render: (row) => formatHoursDuration(row.hours_logged) },
  ]

  return (
    <Card title={t('Indicadores dos tickets')}>
      <div className="space-y-5">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatTile label={t('Tickets abertos')} value={data.open_tickets} hint={`${t('Fechados')}: ${data.closed_tickets}`} tone="primary" />
          <StatTile
            label={t('Idade média dos abertos')}
            value={data.average_age_days === null ? '—' : `${String(data.average_age_days).replace('.', ',')} ${t('dias')}`}
          />
          <StatTile label={t('Horas apontadas')} value={formatHoursDuration(data.hours_logged)} />
          <StatTile label={t('Horas aprovadas')} value={formatHoursDuration(data.hours_approved)} tone="good" />
        </div>

        <div className="grid gap-5 md:grid-cols-3">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Abertos por criticidade')}</p>
            <CategoryBars items={criticalityItems} />
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Tickets por status')}</p>
            <CategoryBars items={statusItems} />
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Tempo de espera dos abertos')}</p>
            <CategoryBars items={agingItems} />
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Abertos há mais tempo')}</p>
          <Table columns={oldestColumns} rows={data.oldest_open} getRowKey={(row) => row.id} emptyMessage={t('Nenhum ticket aberto.')} />
        </div>
        <div className="grid gap-5 md:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Horas gastas em tickets por projeto')}</p>
            <Table columns={projectColumns} rows={data.hours_by_project} getRowKey={(row) => row.project_id} emptyMessage={t('Sem dados.')} />
          </div>
          <div>
            <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)]">{t('Carga por responsável')}</p>
            <Table columns={workloadColumns} rows={data.workload} getRowKey={(row) => row.user_id} emptyMessage={t('Sem dados.')} />
          </div>
        </div>
      </div>
    </Card>
  )
}
