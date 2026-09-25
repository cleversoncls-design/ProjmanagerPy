import { api, API_BASE_URL, ApiError, getToken } from './client'

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
