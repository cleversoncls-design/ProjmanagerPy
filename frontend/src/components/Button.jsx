const VARIANT_CLASS = {
  primary: 'bg-[var(--series-1)] text-white hover:opacity-90 disabled:opacity-50',
  secondary:
    'border border-[var(--border)] bg-[var(--surface)] text-[var(--text-primary)] hover:bg-[var(--page)] disabled:opacity-50',
  ghost: 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50',
  danger: 'bg-[var(--status-critical)] text-white hover:opacity-90 disabled:opacity-50',
}

export default function Button({ variant = 'primary', className = '', children, ...props }) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${className}`}
    >
      {children}
    </button>
  )
}
