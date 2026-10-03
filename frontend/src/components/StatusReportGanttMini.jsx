import { formatDate } from '../utils/format'
import { STATUS_REPORT_CHART_COLORS_SCREEN, TASK_TYPE_COLORS } from '../utils/labels'

const WIDTH = 600
const ROW_H = 20
const PAD_LEFT = 160
const PAD_RIGHT = 10
const PAD_TOP = 10
const PAD_BOTTOM = 18
const MAX_ROWS = 14
const DEPTH_INDENT_PX = 10

function todayUtc() {
  return new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`)
}

function truncate(text, max) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}

/** Gantt (nível 1+2 da EAP) do Status Report — pedido do usuário, com 2
 * prints da EAP recolhida manualmente até o 2º nível: "imprima uma imagem
 * do GANTT considerando as informações até o segundo nível de tarefas pai
 * e filhas, em forma recolhida [...] respeitando as cores conforme
 * definido no projeto [...] quando uma atividade estiver concluída que
 * mude de cor" — pedido originalmente implementado (por engano) como um
 * botão avulso na aba Gantt de Projetos; o usuário corrigiu: é PARA CÁ,
 * dentro do Status Report (impressão interna e para o cliente).
 *
 * Substitui a versão anterior deste componente (que desenhava
 * tasks_done/tasks_next — lista achatada "concluído × previsto", sem
 * hierarquia nem cor por tipo). Agora desenha `report.gantt_snapshot`
 * (congelado na criação do relatório — ver
 * services._build_gantt_level2_snapshot/ProjectStatusReport.gantt_snapshot
 * em app/models.py): cada item já vem com `depth` (0 ou 1, nunca 3º nível
 * em diante), `task_type` (cor — mesma paleta do Gantt completo de
 * Projetos, TASK_TYPE_COLORS/TASK_TYPE_PRINT_COLOR) e `progress_percent`
 * já ponderado pelas horas das folhas descendentes reais (uma tarefa de
 * 2º nível que é um agrupador nunca tem sua própria progress_percentage
 * preenchida de forma útil — ver docstring de
 * services._task_progress_rollups). Ordem preservada como veio do
 * snapshot (hierárquica — pai antes das filhas, ordem da EAP), NUNCA
 * reordenada por data, pra indentação por profundidade fazer sentido
 * visualmente. `null`/lista vazia (relatório criado antes desta
 * funcionalidade existir, ou projeto sem tarefas agendadas no momento do
 * fechamento) mostra `emptyMessage` no lugar do desenho.
 *
 * `colors`/`taskTypeColors` default usam `var(--...)` (tema da tela);
 * StatusReportPrintSheet passa os equivalentes hex fixos
 * (`STATUS_REPORT_CHART_COLORS_PRINT`/`TASK_TYPE_PRINT_COLOR`) — `var(--...)`
 * não resolve no pipeline de impressão do navegador (mesmo bug já
 * corrigido nos outros gráficos desta tela). */
export default function StatusReportGanttMini({
  tasks,
  periodStart,
  periodEnd,
  consultingLabel,
  managementLabel,
  partialLabel,
  completedLabel,
  milestoneLabel,
  emptyMessage,
  moreLabel,
  colors = STATUS_REPORT_CHART_COLORS_SCREEN,
  taskTypeColors = TASK_TYPE_COLORS,
}) {
  const rows = (tasks || []).filter((t) => t.start_date)
  if (rows.length === 0) {
    return <p style={{ color: colors.textMuted, fontSize: '12px', margin: 0 }}>{emptyMessage}</p>
  }

  const visibleRows = rows.slice(0, MAX_ROWS)
  const hiddenCount = rows.length - visibleRows.length

  const allDates = [
    new Date(`${periodStart}T00:00:00Z`),
    new Date(`${periodEnd}T00:00:00Z`),
    ...visibleRows.map((t) => new Date(`${t.start_date}T00:00:00Z`)),
    ...visibleRows.filter((t) => t.end_date).map((t) => new Date(`${t.end_date}T00:00:00Z`)),
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
  const hasMilestone = visibleRows.some((t) => t.is_milestone)

  return (
    <div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '14px', marginBottom: '4px', fontSize: '10px', color: colors.textSecondary }}>
        <LegendSwatch color={taskTypeColors.CONSULTING} label={consultingLabel} />
        <LegendSwatch color={taskTypeColors.MANAGEMENT} label={managementLabel} />
        <LegendSwatch color={colors.warning} label={partialLabel} />
        <LegendSwatch color={colors.good} label={completedLabel} />
        {hasMilestone && <LegendSwatch color={colors.textMuted} label={milestoneLabel} diamond />}
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${height}`} width="100%" style={{ display: 'block', overflow: 'visible' }}>
        {showToday && <line x1={todayX} y1={0} x2={todayX} y2={height - PAD_BOTTOM} stroke={colors.textMuted} strokeWidth="1" strokeDasharray="2 2" />}
        {visibleRows.map((task, i) => {
          const y = PAD_TOP + i * ROW_H
          const start = new Date(`${task.start_date}T00:00:00Z`)
          const end = task.end_date ? new Date(`${task.end_date}T00:00:00Z`) : start
          const barX = xScale(start)
          const barColor = taskTypeColors[task.task_type] || colors.textMuted
          const progress = Math.min(100, Math.max(0, Number(task.progress_percent) || 0))
          const progressColor = progress >= 100 ? colors.good : progress > 0 ? colors.warning : null
          const label = `${task.wbs_code} — ${task.name}`
          const maxLabelChars = Math.max(6, 26 - task.depth * 4)
          return (
            <g key={task.id}>
              <text
                x={2 + task.depth * DEPTH_INDENT_PX}
                y={y + ROW_H / 2}
                dy="3.5"
                fontSize="9.5"
                fontWeight={task.depth === 0 ? 700 : 400}
                fill={colors.textSecondary}
              >
                {truncate(label, maxLabelChars)}
              </text>
              {task.is_milestone ? (
                <rect
                  x={barX + dayWidth / 2 - 4}
                  y={y + ROW_H / 2 - 4}
                  width="8"
                  height="8"
                  rx="1.5"
                  fill={barColor}
                  transform={`rotate(45 ${barX + dayWidth / 2} ${y + ROW_H / 2})`}
                >
                  <title>
                    {label}: {formatDate(task.start_date)}
                  </title>
                </rect>
              ) : (
                <>
                  <defs>
                    <clipPath id={`gantt-l2-clip-${task.id}`}>
                      <rect x={barX} y={y + 3} width={Math.max(xScale(end) - barX, dayWidth * 0.6, 4)} height={ROW_H - 10} rx="3" />
                    </clipPath>
                  </defs>
                  <rect
                    x={barX}
                    y={y + 3}
                    width={Math.max(xScale(end) - barX, dayWidth * 0.6, 4)}
                    height={ROW_H - 10}
                    rx="3"
                    fill={barColor}
                  >
                    <title>
                      {label}: {formatDate(task.start_date)}
                      {task.end_date ? ` – ${formatDate(task.end_date)}` : ''} · {Math.round(progress)}%
                    </title>
                  </rect>
                  {progressColor && (
                    <rect
                      x={barX}
                      y={y + 3}
                      width={Math.max(xScale(end) - barX, dayWidth * 0.6, 4) * (progress / 100)}
                      height={ROW_H - 10}
                      fill={progressColor}
                      clipPath={`url(#gantt-l2-clip-${task.id})`}
                    />
                  )}
                </>
              )}
            </g>
          )
        })}
        <line x1={PAD_LEFT} y1={height - PAD_BOTTOM + 4} x2={WIDTH - PAD_RIGHT} y2={height - PAD_BOTTOM + 4} stroke={colors.grid} strokeWidth="1" />
        <text x={PAD_LEFT} y={height - 4} fontSize="9" fill={colors.textMuted}>
          {formatDate(new Date(minTime).toISOString().slice(0, 10))}
        </text>
        <text x={WIDTH - PAD_RIGHT} y={height - 4} fontSize="9" fill={colors.textMuted} textAnchor="end">
          {formatDate(new Date(maxTime).toISOString().slice(0, 10))}
        </text>
      </svg>
      {hiddenCount > 0 && <p style={{ marginTop: '4px', fontSize: '10px', color: colors.textMuted }}>{moreLabel(hiddenCount)}</p>}
    </div>
  )
}

function LegendSwatch({ color, label, diamond }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
      <span
        style={{
          display: 'inline-block',
          width: '10px',
          height: '10px',
          borderRadius: diamond ? 0 : '2px',
          transform: diamond ? 'rotate(45deg) scale(0.8)' : 'none',
          backgroundColor: color,
        }}
      />
      {label}
    </span>
  )
}
