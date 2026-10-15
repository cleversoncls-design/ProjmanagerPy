export default function Spinner({ label = 'Carregando…' }) {
  return (
    <div className="flex items-center gap-2 py-8 text-sm text-[var(--text-muted)]">
      <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-[var(--grid)] border-t-[var(--series-1)]" />
      {label}
    </div>
  )
}
