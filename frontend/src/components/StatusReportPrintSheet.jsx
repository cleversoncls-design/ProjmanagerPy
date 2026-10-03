import { useLanguage } from '../context/LanguageContext'
import { formatCurrency, formatDate, formatHoursDuration, formatPercent } from '../utils/format'

const RAG_FIELDS = [
  { key: 'rag_schedule', label: 'Prazo' },
  { key: 'rag_cost', label: 'Custo' },
  { key: 'rag_margin', label: 'Margem' },
  { key: 'rag_scope', label: 'Escopo' },
  { key: 'rag_risk', label: 'Risco' },
]

const RAG_PRINT_COLOR = {
  GOOD: '#1a7f37',
  WARNING: '#9a6700',
  CRITICAL: '#cf222e',
}

/** Folha impressa de um Status Report (pedido do usuário: "onde imprimir o
 * status?") — mesmo padrão de ServiceOrderPrintSheet: componente separado,
 * renderizado via portal em document.body só na hora de imprimir (ver
 * StatusReportsPage.jsx), com o `@page`/`break-after` já definidos em
 * index.css. O conteúdo é exatamente o que a tela de detalhe já mostra
 * pro perfil de quem está imprimindo — os campos financeiros/burndown já
 * chegam `null`/`[]` do backend pra EXTERNAL_ROLES (ver
 * app/routers/status_reports.py), então o PM do cliente nunca imprime o
 * que não devia ver, sem precisar de nenhuma lógica extra aqui. */
export default function StatusReportPrintSheet({ report, project, preparedByName }) {
  const { t, labels } = useLanguage()
  const hasFinancials = report.hours_consumed !== null || report.cost_actual !== null || report.cost_planned !== null

  return (
    <div className="status-report-print-page" style={{ fontFamily: 'Arial, Helvetica, sans-serif', color: '#1a1a1a', fontSize: '11px' }}>
      <div style={{ borderBottom: '2px solid #1a1a1a', paddingBottom: '10px', marginBottom: '14px' }}>
        <h1 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>{t('Status Report')}</h1>
        <p style={{ margin: '2px 0 0', fontSize: '13px' }}>
          {project ? `${project.code} — ${project.name}` : ''}
        </p>
        <p style={{ margin: '4px 0 0', fontSize: '11px', color: '#444' }}>
          {t('Período')}: {formatDate(report.period_start)} – {formatDate(report.period_end)}
          {' · '}
          {t('Preparado por')}: {preparedByName || '—'}
          {' · '}
          {t('Criado em')}: {formatDate(report.created_at)}
        </p>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '14px' }}>
        {RAG_FIELDS.map((field) => (
          <span
            key={field.key}
            style={{
              border: `1px solid ${RAG_PRINT_COLOR[report[field.key]]}`,
              color: RAG_PRINT_COLOR[report[field.key]],
              borderRadius: '999px',
              padding: '3px 10px',
              fontSize: '10px',
              fontWeight: 700,
            }}
          >
            {t(field.label)}: {labels.RAG_STATUS_LABELS[report[field.key]]}
          </span>
        ))}
      </div>

      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '14px' }}>
        <tbody>
          <tr>
            <PrintStat label={t('Avanço do cronograma')} value={formatPercent(report.schedule_actual_pct)} />
            <PrintStat label={t('Previsto')} value={formatPercent(report.schedule_planned_pct)} />
            {hasFinancials && <PrintStat label={t('Horas consumidas')} value={formatHoursDuration(report.hours_consumed)} />}
            {hasFinancials && <PrintStat label={t('Custo realizado')} value={formatCurrency(report.cost_actual)} />}
            {hasFinancials && (
              <PrintStat
                label={t('Margem realizada')}
                value={report.margin_actual_pct !== null ? formatPercent(report.margin_actual_pct) : '—'}
              />
            )}
          </tr>
        </tbody>
      </table>

      <PrintSection title={t('Resumo executivo')}>{report.executive_summary}</PrintSection>
      <PrintSection title={t('Próximos passos')}>{report.next_steps_client}</PrintSection>
      {report.next_steps_internal && (
        <PrintSection title={t('Ações internas (não compartilhadas com o cliente)')}>{report.next_steps_internal}</PrintSection>
      )}

      <div style={{ display: 'flex', gap: '16px', marginBottom: '14px' }}>
        <div style={{ flex: 1 }}>
          <PrintTable
            title={t('Concluído na semana anterior')}
            rows={report.tasks_done}
            emptyMessage={t('Nenhuma tarefa concluída no período.')}
          />
        </div>
        <div style={{ flex: 1 }}>
          <PrintTable
            title={t('Previsto para a próxima semana')}
            rows={report.tasks_next}
            emptyMessage={t('Nenhuma tarefa prevista para o próximo período.')}
          />
        </div>
      </div>

      <h2 style={{ fontSize: '12px', fontWeight: 700, borderBottom: '1px solid #ccc', paddingBottom: '3px', marginBottom: '6px' }}>
        {t('Riscos')}
      </h2>
      {report.risks_snapshot.length === 0 ? (
        <p style={{ color: '#666' }}>{t('Nenhum risco registrado neste período.')}</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid #ccc' }}>
              <th style={{ padding: '3px 4px' }}>{t('Descrição')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Probabilidade')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Impacto')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Status')}</th>
            </tr>
          </thead>
          <tbody>
            {report.risks_snapshot.map((risk) => (
              <tr key={risk.id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '3px 4px' }}>{risk.description}</td>
                <td style={{ padding: '3px 4px' }}>{labels.RISK_LEVEL_LABELS[risk.probability]}</td>
                <td style={{ padding: '3px 4px' }}>{labels.RISK_LEVEL_LABELS[risk.impact]}</td>
                <td style={{ padding: '3px 4px' }}>{labels.RISK_STATUS_LABELS[risk.status]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function PrintStat({ label, value }) {
  return (
    <td style={{ padding: '4px 10px 4px 0', verticalAlign: 'top' }}>
      <div style={{ fontSize: '9px', textTransform: 'uppercase', color: '#666', fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: '14px', fontWeight: 700 }}>{value}</div>
    </td>
  )
}

function PrintSection({ title, children }) {
  return (
    <div style={{ marginBottom: '10px' }}>
      <h2 style={{ fontSize: '9px', textTransform: 'uppercase', color: '#666', fontWeight: 700, margin: '0 0 2px' }}>{title}</h2>
      <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{children}</p>
    </div>
  )
}

function PrintTable({ title, rows, emptyMessage }) {
  return (
    <div>
      <h2 style={{ fontSize: '10px', fontWeight: 700, borderBottom: '1px solid #ccc', paddingBottom: '3px', marginBottom: '4px' }}>
        {title}
      </h2>
      {rows.length === 0 ? (
        <p style={{ color: '#666' }}>{emptyMessage}</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: '14px' }}>
          {rows.map((row) => (
            <li key={row.id}>
              {row.wbs_code} — {row.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
