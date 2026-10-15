/**
 * Quebra categórica em barras horizontais finas (item[]: {key, label,
 * value, color}). `color` vem de um mapa fixo por chave (ver utils/labels)
 * — nunca da posição no array, para a cor de uma categoria não mudar só
 * porque a ordenação por valor mudou. Barra fina, ponta arredondada, valor
 * direto ao lado (ver marks-and-anatomy.md).
 */
export default function CategoryBars({ items }) {
  const max = Math.max(1, ...items.map((item) => item.value))
  return (
    <div className="space-y-2.5">
      {items.map((item) => {
        const widthPercent = Math.max(2, Math.round((item.value / max) * 100))
        return (
          <div key={item.key} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-xs text-[var(--text-secondary)]" title={item.label}>
              {item.label}
            </span>
            <div className="h-[10px] flex-1 rounded-full bg-[var(--grid)]">
              <div
                className="h-[10px] rounded-full"
                style={{ width: `${widthPercent}%`, backgroundColor: item.color || 'var(--text-muted)' }}
              />
            </div>
            <span className="w-8 shrink-0 text-right text-xs font-medium tabular text-[var(--text-primary)]">{item.value}</span>
          </div>
        )
      })}
    </div>
  )
}
