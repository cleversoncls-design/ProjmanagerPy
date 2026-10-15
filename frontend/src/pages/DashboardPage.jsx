import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import * as reportsApi from '../api/reports'
import PageHeader from '../components/PageHeader'
import Card from '../components/Card'
import StatTile from '../components/StatTile'
import CategoryBars from '../components/CategoryBars'
import DonutChart from '../components/DonutChart'
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

// Só os 3 status "em andamento" entram no donut (pedido do usuário) —
// Concluído/Cancelado viram KPI à parte (todo projeto finalizado, não faz
// sentido fatiar % de "quanto do portfólio terminou" junto com o que ainda
// está em curso). Ordem fixa (nunca por valor) e cor reaproveitada do
// mesmo mapa de tom que StatusPill/StatTile já usam pra estes status —
// nunca uma paleta nova só pro gráfico.
const PROJECT_STATUS_CHART_ORDER = ['PLANNING', 'ACTIVE', 'ON_HOLD']
const PROJECT_STATUS_CHART_COLOR = {
  PLANNING: 'var(--text-muted)',
  ACTIVE: 'var(--status-good)',
  ON_HOLD: 'var(--status-warning)',
}

export default function DashboardPage() {
  const { labels, t } = useLanguage()
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
      <PageHeader title={t('Dashboard')} subtitle={t('Visão geral do portfólio de projetos.')} />

      {loading && <Spinner />}
      <ErrorBanner message={error} />

      {data && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatTile label={t('Projetos')} value={data.projects_total} tone="default" />
            <StatTile label={t('Tarefas')} value={data.tasks_total} tone="primary" />
            <StatTile
              label={t('Tarefas atrasadas')}
              value={data.tasks_overdue}
              tone={data.tasks_overdue > 0 ? 'critical' : 'good'}
            />
            <StatTile label={t('Progresso médio')} value={formatPercent(data.avg_progress_percentage)} tone="good" />
            <StatTile label={t('Projetos concluídos')} value={data.projects_by_status?.COMPLETED || 0} tone="good" />
            <StatTile label={t('Projetos cancelados')} value={data.projects_by_status?.CANCELLED || 0} tone="critical" />
          </div>

          <Card title={t('Projetos por status')}>
            <DonutChart
              items={PROJECT_STATUS_CHART_ORDER.map((status) => ({
                key: status,
                label: labels.PROJECT_STATUS_LABELS[status] || status,
                value: data.projects_by_status?.[status] || 0,
                color: PROJECT_STATUS_CHART_COLOR[status],
              }))}
              centerLabel={t('Projetos')}
            />
          </Card>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title={t('Tarefas por status')}>
              {data.tasks_total > 0 ? (
                <CategoryBars items={toBarItems(data.tasks_by_status, labels.TASK_STATUS_LABELS, TASK_STATUS_COLORS)} />
              ) : (
                <p className="text-sm text-[var(--text-muted)]">{t('Nenhuma tarefa cadastrada ainda.')}</p>
              )}
            </Card>
            <Card title={t('Tarefas por tipo')}>
              {data.tasks_total > 0 ? (
                <CategoryBars items={toBarItems(data.tasks_by_type, labels.TASK_TYPE_LABELS, TASK_TYPE_COLORS)} />
              ) : (
                <p className="text-sm text-[var(--text-muted)]">{t('Nenhuma tarefa cadastrada ainda.')}</p>
              )}
            </Card>
          </div>

          <Card title={t('Portfólio')}>
            <Table
              columns={[
                {
                  key: 'code',
                  header: t('Projeto'),
                  render: (row) => (
                    <Link to={`/projects/${row.id}`} className="font-medium text-[var(--series-1)] hover:underline">
                      {row.code} — {row.name}
                    </Link>
                  ),
                },
                {
                  key: 'status',
                  header: t('Status'),
                  render: (row) => <StatusPill label={labels.PROJECT_STATUS_LABELS[row.status] || row.status} tone={PROJECT_STATUS_TONE[row.status]} />,
                },
                { key: 'percent_complete', header: t('% concluído'), align: 'right', render: (row) => formatPercent(row.percent_complete) },
                { key: 'tasks_remaining', header: t('Tarefas restantes'), align: 'right' },
                {
                  key: 'margin',
                  header: t('Margem'),
                  align: 'right',
                  render: (row) => (row.margin === null || row.margin === undefined ? '—' : formatCurrency(row.margin)),
                },
                {
                  key: 'next_milestone_name',
                  header: t('Próximo marco'),
                  render: (row) =>
                    row.next_milestone_name ? `${row.next_milestone_name} (${formatDate(row.next_milestone_date)})` : '—',
                },
              ]}
              rows={data.portfolio}
              getRowKey={(row) => row.id}
              emptyMessage={t('Nenhum projeto no seu escopo ainda.')}
            />
          </Card>
        </div>
      )}
    </div>
  )
}
