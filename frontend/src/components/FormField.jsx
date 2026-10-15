const baseInputClass =
  'w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:border-[var(--series-1)] focus:outline-none focus:ring-1 focus:ring-[var(--series-1)]'

export function FormField({ label, required, hint, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">
        {label}
        {required && <span className="text-[var(--status-critical)]"> *</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-xs text-[var(--text-muted)]">{hint}</span>}
    </label>
  )
}

export function TextInput(props) {
  return <input {...props} className={`${baseInputClass} ${props.className || ''}`} />
}

export function Select({ children, ...props }) {
  return (
    <select {...props} className={`${baseInputClass} ${props.className || ''}`}>
      {children}
    </select>
  )
}

export function TextArea(props) {
  return <textarea {...props} className={`${baseInputClass} ${props.className || ''}`} />
}
