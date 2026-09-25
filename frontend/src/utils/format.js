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

export function daysBetween(startValue, endValue) {
  const start = parseApiDate(startValue)
  const end = parseApiDate(endValue)
  if (!start || !end) return null
  return Math.round((end.getTime() - start.getTime()) / 86_400_000)
}
