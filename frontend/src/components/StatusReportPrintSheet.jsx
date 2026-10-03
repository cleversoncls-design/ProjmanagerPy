import { useLanguage } from '../context/LanguageContext'
import { formatCurrency, formatDate, formatHoursDuration, formatPercent, daysBetween } from '../utils/format'
import { RAG_STATUS_CSS_COLOR } from '../utils/labels'
import StatusReportComparisonBar from './StatusReportComparisonBar'
import StatusReportBurndownChart from './StatusReportBurndownChart'
import StatusReportGanttMini from './StatusReportGanttMini'
import resultarLogo from '../assets/resultar-logo-color.png'

const RAG_FIELDS = [
  { key: 'rag_schedule', label: 'Prazo' },
  { key: 'rag_cost', label: 'Custo' },
  { key: 'rag_margin', label: 'Margem' },
  { key: 'rag_scope', label: 'Escopo' },
  { key: 'rag_risk', label: 'Risco' },
]

/** Folha impressa de um Status Report (pedido do usuário: "onde imprimir o
 * status?", depois reforçado: "preciso que esteja igual ao modelo
 * apresentado anteriormente") — mesmo padrão de ServiceOrderPrintSheet:
 * componente separado, renderizado via portal em document.body só na hora
 * de imprimir (ver StatusReportsPage.jsx), com o `@page`/`break-after` já
 * definidos em index.css. Cabeçalho com marca + faixa de audiência,
 * barras de Custo/Margem, burndown e mini-cronograma agora batem com o
 * mockup "Interno"/"Cliente" validado no canvas de design — mesmos
 * componentes de gráfico usados na tela de detalhe (StatusReportsPage),
 * reaproveitados aqui porque usam só `style` inline (sem classe Tailwind),
 * então renderizam igual nos dois lugares. O conteúdo é exatamente o que
 * a tela de detalhe já mostra pro perfil de quem está imprimindo — os
 * campos financeiros/burndown já chegam `null`/`[]` do backend pra
 * EXTERNAL_ROLES (ver app/routers/status_reports.py), então o PM do
 * cliente nunca imprime o que não devia ver, sem precisar de nenhuma
 * lógica extra aqui. Cores via `var(--...)` (nunca hex solto): o portal
 * renderiza no MESMO documento da tela, então os tokens de app/index.css
 * resolvem igual na impressão. */
export default function StatusReportPrintSheet({ report, project, client, preparedByName, managerName }) {
  const { t, labels } = useLanguage()
  const hasFinancials = report.hours_consumed !== null || report.cost_actual !== null || report.cost_planned !== null
  const daysToEnd = project?.end_date ? daysBetween(new Date().toISOString().slice(0, 10), project.end_date) : null

  return (
    <div className="status-report-print-page" style={{ fontFamily: 'Arial, Helvetica, sans-serif', color: 'var(--text-primary)', fontSize: '11px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', borderBottom: '2px solid var(--text-primary)', paddingBottom: '10px', marginBottom: '10px' }}>
        <div>
          <span
            style={{
              display: 'inline-block',
              borderRadius: '999px',
              padding: '3px 10px',
              fontSize: '9px',
              fontWeight: 700,
              textTransform: 'uppercase',
              letterSpacing: '0.03em',
              backgroundColor: hasFinancials ? 'color-mix(in srgb, var(--series-7) 16%, transparent)' : 'color-mix(in srgb, var(--series-1) 16%, transparent)',
              color: hasFinancials ? 'var(--series-7)' : 'var(--series-1)',
            }}
          >
            {hasFinancials ? t('Uso interno — Diretoria e Gerências (não enviar ao cliente)') : t('Compartilhado com o cliente — acesso do Gerente de Projeto')}
          </span>
          <p style={{ margin: '6px 0 0', fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
            {hasFinancials ? t('Status Report — Interno') : t('Status Report')}
          </p>
          <h1 style={{ fontSize: '17px', fontWeight: 700, margin: '2px 0 0' }}>{project ? `${project.code} — ${project.name}` : ''}</h1>
          {client && <p style={{ margin: '2px 0 0', fontSize: '11px', color: 'var(--text-secondary)' }}>{t('Cliente')}: {client.legal_name}</p>}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', justifyContent: 'flex-end' }}>
            <img src={resultarLogo} alt="" style={{ height: '30px', width: '30px' }} />
            <div style={{ lineHeight: 1.1, textAlign: 'left' }}>
              <div style={{ fontSize: '13px', fontWeight: 800, letterSpacing: '0.02em' }}>RESULTAR</div>
              <div style={{ fontSize: '8px', fontWeight: 600, letterSpacing: '0.2em', color: 'var(--text-muted)' }}>SERVICIOS</div>
            </div>
          </div>
          <p style={{ margin: '6px 0 0', fontSize: '10px', color: 'var(--text-muted)' }}>
            {t('Período')}: {formatDate(report.period_start)} – {formatDate(report.period_end)}
            <br />
            {hasFinancials ? t('Preparado por') : t('Gerente do projeto')}: {(hasFinancials ? preparedByName : managerName) || '—'}
            <br />
            {t('Criado em')}: {formatDate(report.created_at)}
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '12px' }}>
        {RAG_FIELDS.map((field) => (
          <span
            key={field.key}
            style={{
              border: `1px solid ${RAG_STATUS_CSS_COLOR[report[field.key]]}`,
              color: RAG_STATUS_CSS_COLOR[report[field.key]],
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

      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '12px' }}>
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
            {!hasFinancials && daysToEnd !== null && <PrintStat label={t('Dias até o fim do projeto')} value={String(daysToEnd)} />}
          </tr>
        </tbody>
      </table>

      {hasFinancials && (report.cost_planned !== null || report.margin_planned_pct !== null) && (
        <PrintSection title={t('Custo e Margem — Previsto vs. Realizado')}>
          <StatusReportComparisonBar
            label={t('Custo')}
            planned={report.cost_planned}
            actual={report.cost_actual}
            formatValue={formatCurrency}
            color={RAG_STATUS_CSS_COLOR[report.rag_cost]}
            previstoLabel={t('Previsto')}
            realizadoLabel={t('Realizado')}
          />
          <StatusReportComparisonBar
            label={t('Margem')}
            planned={report.margin_planned_pct}
            actual={report.margin_actual_pct}
            formatValue={formatPercent}
            color={RAG_STATUS_CSS_COLOR[report.rag_margin]}
            previstoLabel={t('Previsto')}
            realizadoLabel={t('Realizado')}
          />
        </PrintSection>
      )}

      {hasFinancials && report.burndown.length > 0 && (
        <PrintSection title={t('Burndown — Horas restantes do orçamento')}>
          <StatusReportBurndownChart
            points={report.burndown}
            emptyMessage={t('Sem dados suficientes para calcular o burndown.')}
            legendPlanned={t('Previsto')}
            legendActual={t('Real')}
            todayLabel={t('Hoje')}
          />
        </PrintSection>
      )}

      <div style={{ marginBottom: '10px' }}>
        <h2 style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, margin: '0 0 4px' }}>
          {t('Cronograma — Marcos e tarefas')}
        </h2>
        <StatusReportGanttMini
          tasksDone={report.tasks_done}
          tasksNext={report.tasks_next}
          periodStart={report.period_start}
          periodEnd={report.period_end}
          doneLabel={t('Completado')}
          nextLabel={t('Previsto')}
          emptyMessage={t('Nenhuma tarefa com data para exibir no cronograma.')}
          moreLabel={(n) => `+${n} ${t('tarefa(s) a mais não exibida(s) no gráfico — veja as tabelas abaixo.')}`}
        />
      </div>

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

      <h2 style={{ fontSize: '12px', fontWeight: 700, borderBottom: '1px solid var(--grid)', paddingBottom: '3px', marginBottom: '6px' }}>
        {t('Riscos')}
      </h2>
      {report.risks_snapshot.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>{t('Nenhum risco registrado neste período.')}</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--grid)' }}>
              <th style={{ padding: '3px 4px' }}>{t('Descrição')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Probabilidade')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Impacto')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Status')}</th>
              <th style={{ padding: '3px 4px' }}>{t('Mitigação')}</th>
            </tr>
          </thead>
          <tbody>
            {report.risks_snapshot.map((risk) => (
              <tr key={risk.id} style={{ borderBottom: '1px solid var(--grid)' }}>
                <td style={{ padding: '3px 4px' }}>{risk.description}</td>
                <td style={{ padding: '3px 4px' }}>{labels.RISK_LEVEL_LABELS[risk.probability]}</td>
                <td style={{ padding: '3px 4px' }}>{labels.RISK_LEVEL_LABELS[risk.impact]}</td>
                <td style={{ padding: '3px 4px' }}>{labels.RISK_STATUS_LABELS[risk.status]}</td>
                <td style={{ padding: '3px 4px' }}>{risk.mitigation_plan || '—'}</td>
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
      <div style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: '14px', fontWeight: 700 }}>{value}</div>
    </td>
  )
}

function PrintSection({ title, children }) {
  return (
    <div style={{ marginBottom: '12px' }}>
      <h2 style={{ fontSize: '9px', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 700, margin: '0 0 4px' }}>{title}</h2>
      <div style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{children}</div>
    </div>
  )
}

function PrintTable({ title, rows, emptyMessage }) {
  return (
    <div>
      <h2 style={{ fontSize: '10px', fontWeight: 700, borderBottom: '1px solid var(--grid)', paddingBottom: '3px', marginBottom: '4px' }}>
        {title}
      </h2>
      {rows.length === 0 ? (
        <p style={{ color: 'var(--text-muted)' }}>{emptyMessage}</p>
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
