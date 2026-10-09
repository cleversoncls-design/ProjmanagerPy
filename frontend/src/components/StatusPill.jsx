const TONE = {
  good: { bg: 'color-mix(in srgb, var(--status-good) 16%, transparent)', fg: 'var(--status-good)' },
  warning: { bg: 'color-mix(in srgb, var(--status-warning) 18%, transparent)', fg: 'var(--status-warning)' },
  serious: { bg: 'color-mix(in srgb, var(--status-serious) 18%, transparent)', fg: 'var(--status-serious)' },
  critical: { bg: 'color-mix(in srgb, var(--status-critical) 16%, transparent)', fg: 'var(--status-critical)' },
  muted: { bg: 'var(--page)', fg: 'var(--text-secondary)' },
}

/** Selo de status — fundo suave na cor do tom + texto na mesma cor, padrão
 * portado do app de referência Resultar Servicios (StatusPill em
 * components/app-ui.tsx). Nunca comunica só por cor: o rótulo do status
 * sempre acompanha o selo — ver regra "status color never alone" da
 * paleta de dataviz. */
// `title` é opcional — só usado onde `label` vem abreviado (ex.: "N/I" na
// grade de tarefas) pra mostrar o texto por extenso ao passar o mouse; sem
// ele, cai no próprio `label`.
export default function StatusPill({ label, tone = 'muted', title }) {
  const { bg, fg } = TONE[tone] || TONE.muted
  return (
    <span
      className="inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold"
      style={{ backgroundColor: bg, color: fg }}
      title={title || label}
    >
      {label}
    </span>
  )
}
