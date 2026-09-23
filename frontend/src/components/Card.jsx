export default function Card({ title, action, children, className = '' }) {
  return (
    <div className={`rounded-xl border border-[var(--border)] bg-[var(--surface)] ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between border-b border-[var(--border)] px-5 py-3.5">
          {title && <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>}
          {action}
        </div>
      )}
      <div className="p-5">{children}</div>
    </div>
  )
}
