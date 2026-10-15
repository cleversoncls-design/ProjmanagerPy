import { api, API_BASE_URL, ApiError, getToken } from './client'
import { getStoredLanguage } from '../i18n/translations'

// Consumo já apropriado no sistema anterior — ver
// app/routers/legacy_consumption.py. Só perfis de gestão têm acesso.

export function listLegacyConsumption(projectId) {
  return api.get(`/projects/${projectId}/legacy-consumption`)
}

export function createLegacyConsumption(projectId, payload) {
  return api.post(`/projects/${projectId}/legacy-consumption`, payload)
}

export function updateLegacyConsumption(projectId, entryId, payload) {
  return api.patch(`/projects/${projectId}/legacy-consumption/${entryId}`, payload)
}

export function deleteLegacyConsumption(projectId, entryId) {
  return api.del(`/projects/${projectId}/legacy-consumption/${entryId}`)
}

function authHeaders() {
  const token = getToken()
  const headers = { 'X-App-Language': getStoredLanguage() }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

/** Envia a planilha .xlsx (multipart) — não passa por `api.post` porque o
 * corpo não é JSON. Tudo-ou-nada: em caso de erro nas linhas a API devolve
 * 422 com a lista "linha N: ..." em `detail`, que vira a mensagem do ApiError. */
export async function importLegacyConsumption(file) {
  const body = new FormData()
  body.append('file', file)
  let response
  try {
    response = await fetch(`${API_BASE_URL}/legacy-consumption/import`, { method: 'POST', headers: authHeaders(), body })
  } catch {
    throw new ApiError(`Não foi possível conectar à API em ${API_BASE_URL}.`, 0)
  }
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    data = text
  }
  if (!response.ok) {
    const detail = data && typeof data === 'object' ? data.detail : data
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
      : detail || `Erro ${response.status} ao importar a planilha.`
    throw new ApiError(message, response.status)
  }
  return data
}

/** Baixa a planilha-modelo (.xlsx) da importação. */
export async function downloadLegacyTemplate(filenameFallback = 'modelo_consumo_anterior.xlsx') {
  const response = await fetch(`${API_BASE_URL}/legacy-consumption/template.xlsx`, { headers: authHeaders() })
  if (!response.ok) {
    throw new ApiError(`Erro ${response.status} ao baixar o modelo.`, response.status)
  }
  const blob = await response.blob()
  const disposition = response.headers.get('Content-Disposition') || ''
  const match = disposition.match(/filename="?([^"]+)"?/)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = match ? match[1] : filenameFallback
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
