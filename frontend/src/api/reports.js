import { api, API_BASE_URL, ApiError, getToken, withQuery } from './client'

export function getDashboard() {
  return api.get('/dashboard')
}

export function getPortfolio(params) {
  return api.get('/reports/portfolio', params)
}

export function getProjectReport(projectId) {
  return api.get(`/projects/${projectId}/report`)
}

export function getGantt(projectId) {
  return api.get(`/projects/${projectId}/gantt`)
}

export function getSchedule(projectId) {
  return api.get(`/projects/${projectId}/schedule`)
}

export function getEvm(projectId) {
  return api.get(`/projects/${projectId}/report.evm`)
}

export function getStatistics(projectId) {
  return api.get(`/projects/${projectId}/statistics`)
}

// Prévia da Ordem de Serviço (Fase 3 do apontamento) — ver
// app/routers/reports.py (GET /reports/service-orders).
export function getServiceOrders(params) {
  return api.get('/reports/service-orders', params)
}

/** Baixa a planilha de tarefas (.xlsx) direto do navegador — não passa
 * pelo `api.get` normal porque a resposta é binária, não JSON, e precisa
 * virar um download (link temporário) em vez de ser parseada. */
export async function downloadTasksXlsx(projectId, filenameFallback) {
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}/projects/${projectId}/tasks/export.xlsx`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    throw new ApiError(`Erro ${response.status} ao exportar as tarefas.`, response.status)
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : filenameFallback
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** Baixa a planilha de Ordens de Serviço (.xlsx) — mesmos filtros de
 * getServiceOrders (params), mas via download binário direto (mesmo
 * padrão de downloadTasksXlsx acima, não passa por api.get). */
export async function downloadServiceOrdersXlsx(params, filenameFallback) {
  const token = getToken()
  const response = await fetch(`${API_BASE_URL}${withQuery('/reports/service-orders/export.xlsx', params)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!response.ok) {
    throw new ApiError(`Erro ${response.status} ao exportar as Ordens de Serviço.`, response.status)
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : filenameFallback
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
