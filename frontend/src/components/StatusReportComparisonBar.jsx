/** Barra "bullet" comparando previsto x realizado de uma métrica financeira
 * do Status Report (Custo/Margem) — pedido do usuário: "os indicadores da
 * foto" (o mockup validado no canvas de design mostrava uma barra de
 * previsto x realizado pra Custo e pra Margem, não só o número seco que a
 * tela tinha até então). Uma barra só por métrica, não duas empilhadas: o
 * preenchimento é o REALIZADO, colorido com o mesmo semáforo RAG já
 * calculado pra essa dimensão (rag_cost/rag_margin — nunca uma cor nova só
 * pra esse gráfico, reaproveita o status que o usuário já vê no badge), e
 * um traço vertical marca o PREVISTO como referência ("bullet chart" —
 * mais direto de ler que duas barras lado a lado pra esse tipo de
 * comparação previsto x real).
 *
 * Estilo 100% inline (sem classe Tailwind) de propósito: o mesmo
 * componente é usado tanto na tela (StatusReportsPage) quanto na folha
 * impressa (StatusReportPrintSheet, renderizada via portal no mesmo
 * documento) — inline style garante a mesma renderização nos dois
 * lugares, igual ao padrão já usado em PrintStat/PrintSection ali.
 *
 * `planned`/`actual` nulos (projeto sem valor vendido/margem planejada —
 * ver build_status_report_snapshot) fazem o componente não renderizar
 * nada: não há previsto pra comparar. */
export default function StatusReportComparisonBar({ label, planned, actual, formatValue, color, previstoLabel, realizadoLabel }) {
  if (planned === null || planned === undefined || actual === null || actual === undefined) return null
  const p = Number(planned)
  const a = Number(actual)
  const scaleMax = Math.max(Math.abs(p), Math.abs(a), 0.01) * 1.15
  const actualPct = Math.min(100, (Math.abs(a) / scaleMax) * 100)
  const plannedPct = Math.min(100, (Math.abs(p) / scaleMax) * 100)
  const deltaPct = p !== 0 ? ((a - p) / Math.abs(p)) * 100 : null

  return (
    <div style={{ marginBottom: '12px' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'baseline', gap: '6px', marginBottom: '4px' }}>
        <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.03em', color: 'var(--text-muted)' }}>
          {label}
        </span>
        <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
          {previstoLabel} {formatValue(p)} · {realizadoLabel}{' '}
          <strong style={{ color }}>{formatValue(a)}</strong>
          {deltaPct !== null && (
            <span style={{ color: 'var(--text-muted)' }}>
              {' '}
              ({deltaPct >= 0 ? '+' : ''}
              {deltaPct.toFixed(1)}%)
            </span>
          )}
        </span>
      </div>
      <div style={{ position: 'relative', height: '10px', width: '100%', borderRadius: '999px', backgroundColor: 'var(--grid)' }}>
        <div
          style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: `${actualPct}%`, borderRadius: '999px', backgroundColor: color }}
        />
        <div
          title={`${previstoLabel} ${formatValue(p)}`}
          style={{
            position: 'absolute',
            top: '-3px',
            left: `calc(${plannedPct}% - 1px)`,
            width: '2px',
            height: '16px',
            backgroundColor: 'var(--text-primary)',
          }}
        />
      </div>
    </div>
  )
}
