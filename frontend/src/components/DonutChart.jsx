const SIZE = 160
const STROKE = 26
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
// Espaço em branco entre fatias (2px de "gap de superfície" — ver
// marks-and-anatomy.md do skill de dataviz), convertido em graus do arco.
const GAP_DEG = 3

/** Donut (rosca) — pedido do usuário no lugar do total simples de
 * projetos: cada fatia é uma categoria (`items`: {key, label, value,
 * color}), cor vem de um mapa fixo por categoria (nunca da posição —
 * mesma regra de CategoryBars/utils/labels), nunca sem legenda (rótulo +
 * valor + % sempre ao lado, nunca só a cor) e sempre com o total no
 * centro. `title` em cada fatia funciona como tooltip nativo ao passar o
 * mouse — sem lib de gráfico nova neste projeto. */
export default function DonutChart({ items, total, centerLabel }) {
  const sum = total ?? items.reduce((acc, item) => acc + item.value, 0)
  let cursorDeg = -90 // começa no topo (12h), sentido horário

  const arcs = items
    .filter((item) => item.value > 0)
    .map((item) => {
      const fraction = sum > 0 ? item.value / sum : 0
      const arcDeg = Math.max(0, fraction * 360 - (items.length > 1 ? GAP_DEG : 0))
      const dashLength = (arcDeg / 360) * CIRCUMFERENCE
      const rotation = cursorDeg
      cursorDeg += fraction * 360
      const percent = sum > 0 ? Math.round((item.value / sum) * 100) : 0
      return { ...item, dashLength, rotation, percent }
    })

  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="relative shrink-0" style={{ width: SIZE, height: SIZE }}>
        <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
          <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="var(--grid)" strokeWidth={STROKE} />
          {arcs.map((arc) => (
            <circle
              key={arc.key}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              stroke={arc.color}
              strokeWidth={STROKE}
              strokeDasharray={`${arc.dashLength} ${CIRCUMFERENCE - arc.dashLength}`}
              strokeLinecap={items.length > 1 ? 'round' : 'butt'}
              transform={`rotate(${arc.rotation} ${SIZE / 2} ${SIZE / 2})`}
            >
              <title>
                {arc.label}: {arc.value} ({arc.percent}%)
              </title>
            </circle>
          ))}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold tabular text-[var(--text-primary)]">{sum}</span>
          {centerLabel && <span className="text-[10px] font-medium uppercase tracking-wide text-[var(--text-muted)]">{centerLabel}</span>}
        </div>
      </div>
      <ul className="space-y-2">
        {items.map((item) => {
          const percent = sum > 0 ? Math.round((item.value / sum) * 100) : 0
          return (
            <li key={item.key} className="flex items-center gap-2 text-sm">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: item.color }} />
              <span className="text-[var(--text-secondary)]">{item.label}</span>
              <span className="font-medium tabular text-[var(--text-primary)]">{item.value}</span>
              <span className="text-xs text-[var(--text-muted)]">({percent}%)</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
