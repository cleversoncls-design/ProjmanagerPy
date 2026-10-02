import { Link } from 'react-router-dom'
import { useLanguage } from '../context/LanguageContext'
import PageHeader from '../components/PageHeader'
import { BarChartIcon, ChevronRightIcon } from '../components/icons'

/** Índice do menu "Relatórios" (pedido do usuário) — por enquanto só um
 * card (Horas por tipo), pensado pra receber mais relatórios depois sem
 * precisar redesenhar nada: cada novo relatório é só mais uma entrada em
 * REPORTS abaixo. */
const REPORTS = [
  {
    to: '/reports/hours-breakdown',
    title: 'Horas por tipo (Projeto, Traslado e Ausência)',
    description: 'Totais da empresa e por consultor — horas de projeto por cliente, Traslado e cada tipo de ausência, num período.',
  },
]

export default function ReportsIndexPage() {
  const { t } = useLanguage()
  return (
    <div>
      <PageHeader title={t('Relatórios')} subtitle={t('Escolha um relatório para abrir.')} />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {REPORTS.map((report) => (
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
