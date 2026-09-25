import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as reportsApi from '../api/reports'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import StatTile from '../components/StatTile'
import CategoryBars from '../components/CategoryBars'
import StatusPill from '../components/StatusPill'
import Table from '../components/Table'
import Spinner from '../components/Spinner'
import ErrorBanner from '../components/ErrorBanner'
import { formatCurrency, formatDate, formatPercent } from '../utils/format'
import { PROJECT_STATUS_TONE, TASK_STATUS_COLORS, TASK_TYPE_COLORS } from '../utils/labels'
import { useLanguage } from '../context/LanguageContext'

// Ordenado por valor para leitura mais fácil (maior primeiro) — a cor de
// cada categoria vem de um mapa fixo (colorMap), nunca da posição aqui, então
// reordenar não "repinta" ninguém.
function toBarItems(counts, labelMap, colorMap) {
  return Object.entries(counts || {})
    .map(([key, value]) => ({ key, label: labelMap[key] || key, value, color: colorMap[key] }))
    .sort((a, b) => b.value - a.value)
}

export default function DashboardPage() {
  const { labels } = useLanguage()
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    reportsApi
      .getDashboard()
      .then((result) => {
        if (active) setData(result)
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false))
    return () => {
      active = false
    }
  }, [])

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Visão geral do portfólio de projetos." />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label="Projetos" value={data.projects_total} tone="default" />
            <StatTile label="Tarefas" value={data.tasks_total} tone="primary" />
            <StatTile
              label="Tarefas atrasadas"
              value={data.tasks_overdue}
              tone={data.tasks_overdue > 0 ? 'critical' : 'good'}
            />
            <StatTile label="Progresso médio" value={formatPercent(data.avg_progress_percentage)} tone="good" />
          </div>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Tarefas por status">
              {data.tasks_total > 0 ? (
                <CategoryBars items={toBarItems(data.tasks_by_status, labels.TASK_STATUS_LABELS, TASK_STATUS_COLORS)} />
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Nenhuma tarefa cadastrada ainda.</p>
              )}
            </Card>
            <Card title="Tarefas por tipo">
              {data.tasks_total > 0 ? (
                <CategoryBars items={toBarItems(data.tasks_by_type, labels.TASK_TYPE_LABELS, TASK_TYPE_COLORS)} />
              ) : (
                <p className="text-sm text-[var(--text-muted)]">Nenhuma tarefa cadastrada ainda.</p>
              )}
            </Card>
          </div>

          <Card title="Portfólio">
            <Table
              columns={[
                {
                  key: 'code',
                  header: 'Projeto',
                  render: (row) => (
                    <Link to={`/projects/${row.id}`} className="font-medium text-[var(--series-1)] hover:underline">
                      {row.code} — {row.name}
                    </Link>
                  ),
                },
                {
                  key: 'status',
                  header: 'Status',
                  render: (row) => <StatusPill label={labels.PROJECT_STATUS_LABELS[row.status] || row.status} tone={PROJECT_STATUS_TONE[row.status]} />,
                },
                { key: 'percent_complete', header: '% concluído', align: 'right', render: (row) => formatPercent(row.percent_complete) },
                { key: 'tasks_remaining', header: 'Tarefas restantes', align: 'right' },
                {
                  key: 'margin',
                  header: 'Margem',
                  align: 'right',
                  render: (row) => (row.margin === null || row.margin === undefined ? '—' : formatCurrency(row.margin)),
                },
                {
                  key: 'next_milestone_name',
                  header: 'Próximo marco',
                  render: (row) =>
                    row.next_milestone_name ? `${row.next_milestone_name} (${formatDate(row.next_milestone_date)})` : '—',
                },
              ]}
              rows={data.portfolio}
              getRowKey={(row) => row.id}
              emptyMessage="Nenhum projeto no seu escopo ainda."
            />
          </Card>
        </div>
      )}
    </div>
  )
}
