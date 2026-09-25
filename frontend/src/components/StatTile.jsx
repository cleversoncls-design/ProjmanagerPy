const TONE_COLOR = {
  default: 'var(--text-primary)',
  primary: 'var(--series-1)',
  good: 'var(--status-good)',
  warning: 'var(--status-warning)',
  critical: 'var(--status-critical)',
}

/** Cartão de KPI — valor grande em cima, rótulo pequeno em maiúsculas
 * embaixo, faixa de 3px colorida no topo indicando o tom. Padrão portado
 * do app de referência Resultar Servicios (KpiCard em components/app-ui.tsx).
 * A cor do tom vem sempre do conjunto reservado de cores de status do skill
 * de dataviz (--status-*) ou da cor de marca (--series-1) — nunca uma cor
 * arbitrária nova — e o rótulo sempre acompanha, nunca só a cor. */
export default function StatTile({ label, value, hint, tone = 'default' }) {
  const borderColor = TONE_COLOR[tone] || TONE_COLOR.default
  return (
    <div
      className="rounded-xl border bg-[var(--surface)] px-5 py-4"
      style={{ borderColor: 'var(--border)', borderTopWidth: 3, borderTopColor: borderColor }}
    >
      <p className="text-2xl font-bold text-[var(--text-primary)]">{value}</p>
      <p className="mt-1.5 text-[11px] font-bold uppercase tracking-wide text-[var(--text-muted)]">{label}</p>
      {hint && <p className="mt-1 text-xs text-[var(--text-muted)]">{hint}</p>}
    </div>
  )
}
