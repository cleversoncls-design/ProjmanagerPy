/** Contrato de "stat tile" do skill de dataviz: label (sentence case, sem
 * dois-pontos), value (semibold, algarismos proporcionais — nunca
 * tabular-nums num número grande e solto), hint opcional. */
export default function StatTile({ label, value, hint, tone = 'default' }) {
  const toneClass = tone === 'critical' ? 'text-[var(--status-critical)]' : 'text-[var(--text-primary)]'
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] px-5 py-4">
      <p className="text-xs font-medium text-[var(--text-secondary)]">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold ${toneClass}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-[var(--text-muted)]">{hint}</p>}
    </div>
  )
}
