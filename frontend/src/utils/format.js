// Moeda tratada no sistema inteiro é dólar americano (US$), independente
// do idioma da interface — decisão do usuário, não é conversão de câmbio:
// os valores já cadastrados (custo/hora, faturamento etc.) são tratados
// como se já estivessem em USD, só muda o símbolo/formatação exibida.
const currencyFormatter = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })
const numberFormatter = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1 })
const dateFormatter = new Intl.DateTimeFormat('pt-BR', { timeZone: 'UTC' })

export function formatCurrency(value) {
  if (value === null || value === undefined) return '—'
  return currencyFormatter.format(Number(value))
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '—'
  return numberFormatter.format(Number(value))
}

export function formatPercent(value) {
  if (value === null || value === undefined) return '—'
  return `${numberFormatter.format(Number(value))}%`
}

/** Datas da API normalmente vêm como "YYYY-MM-DD" (sem hora), mas alguns
 * campos são timestamp completo (ex.: Baseline.created_at, serializado como
 * "2026-09-20T14:32:10.123456") — por isso corta pros primeiros 10
 * caracteres ANTES de separar por "-": sem isso, o "T14:32:10..." colado no
 * dia virava NaN, produzindo uma Date inválida (um objeto Date "truthy",
 * não null!) que o Intl.DateTimeFormat.format() joga uma exceção ao tentar
 * formatar — foi exatamente isso que deixava o modal de Estatísticas em
 * branco quando o projeto já tinha uma linha de base salva (ver "Linha de
 * base atual: ... salva em {formatDate(latestBaseline.created_at)}" em
 * ProjectDetailPage.jsx). O parse força UTC para não perder um dia por
 * causa do fuso do navegador. */
export function parseApiDate(value) {
  if (!value) return null
  const [year, month, day] = value.slice(0, 10).split('-').map(Number)
  const date = new Date(Date.UTC(year, month - 1, day))
  return Number.isNaN(date.getTime()) ? null : date
}

export function formatDate(value) {
  const date = parseApiDate(value)
  if (!date) return '—'
  return dateFormatter.format(date)
}

/** SPI/CPI (índices de Earned Value) — sempre 2 casas, sem separador de
 * milhar; "—" quando o backend não conseguiu calcular (denominador zero). */
export function formatIndex(value) {
  if (value === null || value === undefined) return '—'
  return Number(value).toFixed(2)
}

/** Hora da API vem como "HH:MM:SS" (serialização padrão de `datetime.time`
 * do Pydantic) — só interessa mostrar "HH:MM" (ver ResourceSchedule na
 * Agenda de consultores). */
export function formatTime(value) {
  if (!value) return '—'
  return value.slice(0, 5)
}

/** Horas decimais (ex.: 4.33, como vem de `Timesheet.hours_spent` ou
 * `ServiceOrder.total_hours`) → "HH:MM" (ex.: "04:20") — "formato de horas"
 * de verdade, usado no Apontamento de horas e na Ordem de Serviço; o
 * decimal cru confundia quem lia (4.33 parece "4h33", mas são 4h20). */
export function formatHoursDuration(value) {
  if (value === null || value === undefined || value === '') return '—'
  const totalMinutes = Math.round(Number(value) * 60)
  if (Number.isNaN(totalMinutes)) return '—'
  const sign = totalMinutes < 0 ? '-' : ''
  const abs = Math.abs(totalMinutes)
  const hours = Math.floor(abs / 60)
  const minutes = abs % 60
  return `${sign}${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

/** Minutos inteiros (ex.: `Timesheet.break_minutes`) → "HH:MM", pro campo
 * Intervalo, que usa um <input type="time"> como seletor de DURAÇÃO (não de
 * horário do dia) — mesmo widget de Hora início/Hora fim. */
export function minutesToHM(minutes) {
  const total = Math.max(0, Math.round(Number(minutes) || 0))
  const hours = Math.floor(total / 60)
  const mins = total % 60
  return `${String(hours).padStart(2, '0')}:${String(mins).padStart(2, '0')}`
}

/** "HH:MM" → minutos inteiros — inverso de `minutesToHM`, pra mandar
 * `break_minutes` pro backend (que continua em minutos, sem mudança de
 * schema/API — só o formato de entrada/exibição no frontend mudou). */
export function hmToMinutes(value) {
  if (!value) return 0
  const [h, m] = value.split(':').map(Number)
  if (!Number.isFinite(h) || !Number.isFinite(m)) return 0
  return h * 60 + m
}

export function daysBetween(startValue, endValue) {
  const start = parseApiDate(startValue)
  const end = parseApiDate(endValue)
  if (!start || !end) return null
  return Math.round((end.getTime() - start.getTime()) / 86_400_000)
}
