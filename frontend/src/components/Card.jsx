/** `dense` reduz o respiro do cabeçalho e do corpo do card — usado em
 * grades longas (ex.: tarefas) onde o espaço livre em volta da tabela
 * some parte da tela útil; o padrão continua confortável para os outros
 * cards (KPIs, relatórios, formulários) que não passam essa prop. */
export default function Card({ title, action, children, className = '', dense = false }) {
  const headerPadding = dense ? 'px-3 py-2' : 'px-5 py-3.5'
  const bodyPadding = dense ? 'p-2' : 'p-5'
  return (
    <div className={`rounded-2xl border border-[var(--border)] bg-[var(--surface)] ${className}`}>
      {(title || action) && (
        <div className={`flex items-center justify-between border-b border-[var(--border)] ${headerPadding}`}>
          {title && <h2 className="text-sm font-semibold text-[var(--text-primary)]">{title}</h2>}
          {action}
        </div>
      )}
      <div className={bodyPadding}>{children}</div>
    </div>
  )
}
