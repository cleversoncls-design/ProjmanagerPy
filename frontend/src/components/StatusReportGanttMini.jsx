import { formatDate } from '../utils/format'

const WIDTH = 600
const ROW_H = 20
const PAD_LEFT = 150
const PAD_RIGHT = 10
const PAD_TOP = 10
const PAD_BOTTOM = 18
const MAX_ROWS = 10

function todayUtc() {
  return new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`)
}

function truncate(text, max) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/** Mini-cronograma (gantt) do período do Status Report — pedido do
 * usuário: "os indicadores da foto" (o mockup validado tinha um gráfico de
 * marcos/tarefas, não só a lista de texto "semana anterior × próxima
 * semana" que a tela já tinha). Reaproveita exatamente as duas listas já
 * congeladas no relatório (tasks_done/tasks_next, com planned_start_date/
 * planned_end_date — ver build_status_report_snapshot); não inventa um
 * 3º estado "em risco" como o mockup original porque o snapshot não grava
 * o status AO VIVO da tarefa, só se ela estava finalizada ou não no
 * momento do fechamento — então a barra é verde (concluída no período) ou
 * azul (prevista pro período seguinte). Tarefa sem planned_start_date não
 * entra aqui (não dá pra posicioná-la na linha do tempo) mas continua
 * aparecendo nas tabelas de texto logo abaixo — nada se perde, só o
 * desenho fica incompleto pra ela. Lista ordenada por data e limitada a
 * MAX_ROWS pra não estourar a página impressa; o resto some com uma nota
 * "+N tarefas" (continuam nas tabelas abaixo). */
export default function StatusReportGanttMini({ tasksDone, tasksNext, periodStart, periodEnd, doneLabel, nextLabel, emptyMessage, moreLabel }) {
  const rows = [
    ...tasksDone.filter((t) => t.planned_start_date).map((t) => ({ ...t, kind: 'done' })),
    ...tasksNext.filter((t) => t.planned_start_date).map((t) => ({ ...t, kind: 'next' })),
  ].sort((a, b) => a.planned_start_date.localeCompare(b.planned_start_date))

  if (rows.length === 0) {
    return <p style={{ color: 'var(--text-muted)', fontSize: '12px', margin: 0 }}>{emptyMessage}</p>
  }

  const visibleRows = rows.slice(0, MAX_ROWS)
  const hiddenCount = rows.length - visibleRows.length

  const allDates = [
    new Date(`${periodStart}T00:00:00Z`),
    new Date(`${periodEnd}T00:00:00Z`),
    ...visibleRows.map((t) => new Date(`${t.planned_start_date}T00:00:00Z`)),
    ...visibleRows.filter((t) => t.planned_end_date).map((t) => new Date(`${t.planned_end_date}T00:00:00Z`)),
  ]
  const minTime = Math.min(...allDates.map((d) => d.getTime()))
  const maxTime = Math.max(...allDates.map((d) => d.getTime()))
  const span = Math.max(maxTime - minTime, 86400000)
  const plotW = WIDTH - PAD_LEFT - PAD_RIGHT
  const xScale = (date) => PAD_LEFT + ((date.getTime() - minTime) / span) * plotW
  const dayWidth = plotW / (span / 86400000)

  const height = PAD_TOP + PAD_BOTTOM + visibleRows.length * ROW_H
  const today = todayUtc()
  const showToday = today.getTime() >= minTime && today.getTime() <= maxTime
  const todayX = showToday ? xScale(today) : null

  return (
    <div>
      <div style={{ display: 'flex', gap: '14px', marginBottom: '4px', fontSize: '10px', color: 'var(--text-secondary)' }}>
        <LegendSwatch color="var(--status-good)" label={doneLabel} />
        <LegendSwatch color="var(--series-1)" label={nextLabel} />
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} width="100%" style={{ display: 'block', overflow: 'visible' }}>
        {showToday && <line x1={todayX} y1={0} x2={todayX} y2={height - PAD_BOTTOM} stroke="var(--text-muted)" strokeWidth="1" strokeDasharray="2 2" />}
        {visibleRows.map((task, i) => {
          const y = PAD_TOP + i * ROW_H
          const start = new Date(`${task.planned_start_date}T00:00:00Z`)
          const end = task.planned_end_date ? new Date(`${task.planned_end_date}T00:00:00Z`) : start
          const barX = xScale(start)
          const barW = Math.max(xScale(end) - barX, dayWidth * 0.6, 4)
          const color = task.kind === 'done' ? 'var(--status-good)' : 'var(--series-1)'
          return (
            <g key={task.id}>
              <text x={2} y={y + ROW_H / 2} dy="3.5" fontSize="9.5" fill="var(--text-secondary)">
                {truncate(`${task.wbs_code} — ${task.name}`, 24)}
              </text>
              <rect x={barX} y={y + 3} width={barW} height={ROW_H - 10} rx="3" fill={color}>
                <title>
                  {task.wbs_code} — {task.name}: {formatDate(task.planned_start_date)}
                  {task.planned_end_date ? ` – ${formatDate(task.planned_end_date)}` : ''}
                </title>
              </rect>
            </g>
          )
        })}
        <line x1={PAD_LEFT} y1={height - PAD_BOTTOM + 4} x2={WIDTH - PAD_RIGHT} y2={height - PAD_BOTTOM + 4} stroke="var(--grid)" strokeWidth="1" />
        <text x={PAD_LEFT} y={height - 4} fontSize="9" fill="var(--text-muted)">
          {formatDate(new Date(minTime).toISOString().slice(0, 10))}
        </text>
        <text x={WIDTH - PAD_RIGHT} y={height - 4} fontSize="9" fill="var(--text-muted)" textAnchor="end">
          {formatDate(new Date(maxTime).toISOString().slice(0, 10))}
        </text>
      </svg>
      {hiddenCount > 0 && <p style={{ marginTop: '4px', fontSize: '10px', color: 'var(--text-muted)' }}>{moreLabel(hiddenCount)}</p>}
    </div>
  )
}

function LegendSwatch({ color, label }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
      <span style={{ display: 'inline-block', width: '10px', height: '10px', borderRadius: '2px', backgroundColor: color }} />
      {label}
    </span>
  )
}
