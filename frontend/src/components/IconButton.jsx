/** Botão só com ícone — usado onde uma barra de ações tem texto demais
 * (grade de Tarefas: Exportar/Salvar linha de base/Recalcular WBS/
 * Recalcular tudo/Nova tarefa, e as ações Editar/Mover por linha). O
 * rótulo continua existindo, só que como `title` (dica nativa do
 * navegador ao passar o mouse) e `aria-label` (leitor de tela) em vez de
 * texto visível — nunca button sem nome acessível algum. Mesmas variantes
 * de cor do Button. */
const VARIANT_CLASS = {
  primary: 'bg-[var(--series-1)] text-white hover:opacity-90 disabled:opacity-50',
  secondary:
    'border border-[var(--border)] bg-[var(--surface)] text-[var(--text-primary)] hover:bg-[var(--page)] disabled:opacity-50',
  ghost: 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-50',
  danger:
    'border border-transparent text-[var(--status-critical)] hover:bg-[var(--status-critical)]/10 disabled:opacity-50',
}

export default function IconButton({ icon: IconComponent, label, variant = 'secondary', size = 17, className = '', ...props }) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      {...props}
      className={`inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg transition-colors disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${className}`}
    >
      <IconComponent size={size} />
    </button>
  )
}
