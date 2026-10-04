export default function ErrorBanner({ message }) {
  if (!message) return null
  return (
    <div className="rounded-lg border border-[var(--status-critical)]/30 bg-[var(--status-critical)]/10 px-3.5 py-2.5 text-sm text-[var(--status-critical)]">
      {message}
    </div>
  )
}
