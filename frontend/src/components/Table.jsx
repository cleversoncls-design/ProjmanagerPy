/**
 * Tabela genérica: columns = [{ key, header, align?, render? }], rows = [obj].
 * `render` recebe a linha inteira; sem `render`, usa `row[key]` cru.
 */
export default function Table({ columns, rows, getRowKey, emptyMessage = 'Nenhum registro encontrado.' }) {
  if (!rows || rows.length === 0) {
    return <p className="py-8 text-center text-sm text-[var(--text-muted)]">{emptyMessage}</p>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--border)]">
            {columns.map((column) => (
              <th
                key={column.key}
                className={`px-3 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-muted)] ${
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
                  className={`px-3 py-2.5 text-[var(--text-primary)] ${column.align === 'right' ? 'text-right tabular' : 'text-left'}`}
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
