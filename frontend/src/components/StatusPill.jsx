const TONE_COLOR = {
  good: 'var(--status-good)',
  warning: 'var(--status-warning)',
  serious: 'var(--status-serious)',
  critical: 'var(--status-critical)',
  muted: 'var(--text-muted)',
}

/** Nunca comunica só por cor: o texto do rótulo sempre acompanha a bolinha
 * de status — ver regra "status color never alone" da paleta de dataviz. */
export default function StatusPill({ label, tone = 'muted' }) {
  const color = TONE_COLOR[tone] || TONE_COLOR.muted
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-[var(--border)] px-2.5 py-1 text-xs font-medium text-[var(--text-secondary)]">
      <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  )
}
