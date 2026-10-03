import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import { BarChartIcon, ChevronRightIcon } from '../components/icons'
import { MANAGEMENT_ROLES } from '../utils/labels'

/** Índice do menu "Relatórios" (pedido do usuário) — cada novo relatório é
 * só mais uma entrada em REPORTS abaixo. "Horas por tipo" expõe horas/
 * ausência de TODOS os recursos da empresa — continua só MANAGEMENT_ROLES.
 * "Status Report" (pedido do usuário: "pode implementar os 2 modelos e
 * colocar na opção de relatorios") é o primeiro relatório desta tela que
 * o PM do cliente também enxerga — escopado ao próprio projeto, sem dado
 * financeiro (ver StatusReportsPage.jsx/app/routers/status_reports.py). */
const REPORTS = [
  {
    to: '/reports/hours-breakdown',
    title: 'Horas por tipo (Projeto, Traslado e Ausência)',
    description: 'Totais da empresa e por consultor — horas de projeto por cliente, Traslado e cada tipo de ausência, num período.',
    roles: MANAGEMENT_ROLES,
  },
  {
    to: '/reports/status-report',
    title: 'Status Report',
    description: 'Fechamento do período por projeto — indicadores, cronograma, riscos e próximos passos.',
  },
]

export default function ReportsIndexPage() {
  const { user } = useAuth()
  const { t } = useLanguage()
  const visibleReports = REPORTS.filter((report) => !report.roles || report.roles.includes(user?.role))
  return (
    <div>
      <PageHeader title={t('Relatórios')} subtitle={t('Escolha um relatório para abrir.')} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {visibleReports.map((report) => (
          <Link
            key={report.to}
            to={report.to}
            className="group flex items-start gap-3.5 rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5 transition-colors hover:border-[var(--series-1)]"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--series-1)]/10 text-[var(--series-1)]">
              <BarChartIcon size={20} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-[var(--text-primary)]">{t(report.title)}</p>
              <p className="mt-1 text-xs text-[var(--text-secondary)]">{t(report.description)}</p>
            </div>
            <ChevronRightIcon size={16} className="mt-1 shrink-0 text-[var(--text-muted)] transition-colors group-hover:text-[var(--series-1)]" />
          </Link>
        ))}
      </div>
    </div>
  )
}
