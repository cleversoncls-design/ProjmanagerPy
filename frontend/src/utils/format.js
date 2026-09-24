const currencyFormatter = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
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

/** Datas da API vêm como "YYYY-MM-DD" (sem hora) — parse forçando UTC para
 * não perder um dia por causa do fuso do navegador. */
export function parseApiDate(value) {
  if (!value) return null
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day))
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

export function daysBetween(startValue, endValue) {
  const start = parseApiDate(startValue)
  const end = parseApiDate(endValue)
  if (!start || !end) return null
  return Math.round((end.getTime() - start.getTime()) / 86_400_000)
}
