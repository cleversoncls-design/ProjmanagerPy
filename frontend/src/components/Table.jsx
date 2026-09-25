/**
 * Tabela genérica: columns = [{ key, header, align?, render?, nowrap? }], rows = [obj].
 * `render` recebe a linha inteira; sem `render`, usa `row[key]` cru.
 * `nowrap` numa coluna impede quebra de linha na célula (útil pra nomes
 * longos que, quebrando em várias linhas, inflam a altura da linha inteira
 * — com `nowrap` a coluna só fica mais larga e o scroll horizontal do
 * container, que já existe, resolve).
 * `dense` (na tabela) reduz o padding vertical das linhas e a fonte (de
 * text-sm/14px pra text-xs/12px) — usado em grades longas (ex.: tarefas)
 * onde ver mais linhas por tela importa mais que o respiro extra das
 * tabelas comuns; o padrão continua confortável.
 */
export default function Table({ columns, rows, getRowKey, emptyMessage = 'Nenhum registro encontrado.', dense = false }) {
  if (!rows || rows.length === 0) {
    return <p className="py-8 text-center text-sm text-[var(--text-muted)]">{emptyMessage}</p>
  }

  const headerPadding = dense ? 'px-2 py-0.5' : 'px-3 py-2'
  const cellPadding = dense ? 'px-2 py-0' : 'px-3 py-2.5'
  const bodyText = dense ? 'text-xs' : 'text-sm'

  return (
    <div className="overflow-x-auto">
      <table className={`w-full border-collapse ${bodyText}`}>
        <thead>
          <tr className="border-b border-[var(--border)]">
            {columns.map((column) => (
              <th
                key={column.key}
                className={`${headerPadding} text-xs font-medium uppercase tracking-wide text-[var(--text-muted)] ${
                  column.align === 'right' ? 'text-right' : 'text-left'
                }`}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)} className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--page)]">
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`${cellPadding} text-[var(--text-primary)] ${column.align === 'right' ? 'text-right tabular' : 'text-left'} ${
                    column.nowrap ? 'whitespace-nowrap' : ''
                  }`}
                >
                  {column.render ? column.render(row) : (row[column.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
