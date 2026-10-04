import { formatDate, formatHoursDuration } from '../utils/format'
import { STATUS_REPORT_CHART_COLORS_SCREEN } from '../utils/labels'

const WIDTH = 600
const HEIGHT = 170
const PAD_LEFT = 42
const PAD_RIGHT = 10
const PAD_TOP = 14
const PAD_BOTTOM = 26
const PLOT_W = WIDTH - PAD_LEFT - PAD_RIGHT
const PLOT_H = HEIGHT - PAD_TOP - PAD_BOTTOM

function todayUtc() {
  return new Date(`${new Date().toISOString().slice(0, 10)}T00:00:00Z`)
}

/** Burndown do Status Report (pedido do usuário: "os indicadores da foto" —
 * o mockup validado tinha um gráfico de burndown, que os dados já
 * calculavam via services.project_burndown desde a 1ª versão da tela, só
 * nunca tinham virado desenho). Linha "Planejado" tracejada + "Real"
 * sólida, mesmo padrão (cor/traço) do burndown já existente em
 * services.project_burndown/ProjectDetailPage. SVG simples com <title> por
 * ponto como tooltip (mesma convenção de DonutChart) — sem lib de gráfico
 * nova neste projeto. `points` vazio (projeto sem datas/horas estimadas o
 * bastante pra ter uma linha de base, ou perfil externo — ver
 * app/routers/status_reports.py) mostra uma mensagem no lugar do SVG.
 *
 * `colors` default usa `var(--...)` (tema da tela); StatusReportPrintSheet
 * passa hex fixo (`STATUS_REPORT_CHART_COLORS_PRINT`) — reportado pelo
 * usuário que `var(--...)` não resolve no pipeline de impressão do
 * navegador (linha/eixos saíam sem cor). */
export default function StatusReportBurndownChart({ points, emptyMessage, legendPlanned, legendActual, todayLabel, colors = STATUS_REPORT_CHART_COLORS_SCREEN }) {
  if (!points || points.length === 0) {
    return <p style={{ color: colors.textMuted, fontSize: '12px', margin: 0 }}>{emptyMessage}</p>
  }

  const dates = points.map((pt) => new Date(`${pt.date}T00:00:00Z`))
  const maxHours = Math.max(1, ...points.map((pt) => Math.max(Number(pt.planned_remaining_hours), Number(pt.actual_remaining_hours))))
  const minTime = dates[0].getTime()
  const maxTime = dates[dates.length - 1].getTime()
  const span = Math.max(maxTime - minTime, 1)
  const xScale = (date) => PAD_LEFT + ((date.getTime() - minTime) / span) * PLOT_W
  const yScale = (hours) => PAD_TOP + PLOT_H - (Math.max(0, hours) / maxHours) * PLOT_H

  const plannedPath = points.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${xScale(dates[i]).toFixed(1)} ${yScale(Number(pt.planned_remaining_hours)).toFixed(1)}`).join(' ')
  const actualPath = points.map((pt, i) => `${i === 0 ? 'M' : 'L'} ${xScale(dates[i]).toFixed(1)} ${yScale(Number(pt.actual_remaining_hours)).toFixed(1)}`).join(' ')

  const today = todayUtc()
  const showToday = today.getTime() >= minTime && today.getTime() <= maxTime
  const todayX = showToday ? xScale(today) : null

  return (
    <div>
      <div style={{ display: 'flex', gap: '14px', marginBottom: '4px', fontSize: '10px', color: colors.textSecondary }}>
        <LegendSwatch color={colors.textMuted} dashed label={legendPlanned} />
        <LegendSwatch color={colors.series1} label={legendActual} />
      </div>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} width="100%" style={{ display: 'block', overflow: 'visible' }} preserveAspectRatio="none">
        <line x1={PAD_LEFT} y1={PAD_TOP + PLOT_H} x2={WIDTH - PAD_RIGHT} y2={PAD_TOP + PLOT_H} stroke={colors.grid} strokeWidth="1" />
        <text x={PAD_LEFT - 6} y={PAD_TOP + PLOT_H} textAnchor="end" fontSize="9" fill={colors.textMuted} dy="3">
          0h
        </text>
        <text x={PAD_LEFT - 6} y={PAD_TOP} textAnchor="end" fontSize="9" fill={colors.textMuted} dy="3">
          {Math.round(maxHours)}h
        </text>
        {showToday && (
          <>
            <line x1={todayX} y1={PAD_TOP} x2={todayX} y2={PAD_TOP + PLOT_H} stroke={colors.textMuted} strokeWidth="1" strokeDasharray="2 2" />
            <text x={todayX} y={PAD_TOP - 4} textAnchor="middle" fontSize="9" fill={colors.textMuted}>
              {todayLabel}
            </text>
          </>
        )}
        <path d={plannedPath} fill="none" stroke={colors.textMuted} strokeWidth="2" strokeDasharray="4 3" strokeLinecap="round" />
        <path d={actualPath} fill="none" stroke={colors.series1} strokeWidth="2" strokeLinecap="round" />
        {points.map((pt, i) => (
          <circle key={pt.date} cx={xScale(dates[i])} cy={yScale(Number(pt.actual_remaining_hours))} r="2.5" fill={colors.series1}>
            <title>
              {formatDate(pt.date)}: {formatHoursDuration(pt.actual_remaining_hours)}
            </title>
          </circle>
        ))}
        <text x={PAD_LEFT} y={HEIGHT - 6} textAnchor="start" fontSize="9" fill={colors.textMuted}>
          {formatDate(points[0].date)}
        </text>
        <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 6} textAnchor="end" fontSize="9" fill={colors.textMuted}>
          {formatDate(points[points.length - 1].date)}
        </text>
      </svg>
    </div>
  )
}

function LegendSwatch({ color, label, dashed }) {
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
      <span
        style={{
          display: 'inline-block',
          width: '14px',
          height: dashed ? 0 : '2px',
          borderTop: dashed ? `2px dashed ${color}` : 'none',
          backgroundColor: dashed ? 'transparent' : color,
        }}
      />
      {label}
    </span>
  )
}
