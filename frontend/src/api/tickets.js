import { api, API_BASE_URL, ApiError, getToken } from './client'
import { getStoredLanguage } from '../i18n/translations'

// Tickets internos (pendentes) — ver app/routers/tickets.py.

export function listTickets(params) {
  return api.get('/tickets', params)
}

export function getTicket(ticketId) {
  return api.get(`/tickets/${ticketId}`)
}

export function createTicket(payload) {
  return api.post('/tickets', payload)
}

export function listTicketAssignees() {
  return api.get('/tickets/assignees')
}

export function assignTicket(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/assign`, payload)
}

export function changeTicketStatus(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/status`, payload)
}

export function commentTicket(ticketId, message) {
  return api.post(`/tickets/${ticketId}/comments`, { message })
}

export function changeTicketCriticality(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/criticality`, payload)
}

export function logTicketTime(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/time`, payload)
}

/** Cronômetro de atendimento (servidor): iniciar / finalizar (gera o
 * apontamento com a hora final do momento) / descartar. */
export function startTicketWork(ticketId) {
  return api.post(`/tickets/${ticketId}/work/start`, {})
}

export function finishTicketWork(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/work/finish`, payload)
}

export function cancelTicketWork(ticketId) {
  return api.post(`/tickets/${ticketId}/work/cancel`, {})
}

/** Indicadores para gerentes (abertos por criticidade/status, idade, horas por
 * projeto, carga por responsável). Só perfis de gestão. */
export function getTicketIndicators(params) {
  return api.get('/tickets-indicators', params)
}

function authHeaders() {
  const token = getToken()
  const headers = { 'X-App-Language': getStoredLanguage() }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

async function parseBody(response) {
  const text = await response.text()
  try {
    return text ? JSON.parse(text) : null
  } catch {
    return text
  }
}

/** Anexa arquivos (multipart) ao ticket. Sem `interactionId`, o envio vira uma
 * nova interação (comentário, com `message` opcional); com `interactionId`,
 * anexa a uma interação do próprio usuário (ex.: a abertura do ticket).
 * Devolve o ticket atualizado. */
export async function uploadTicketAttachments(ticketId, files, { message, interactionId } = {}) {
  const body = new FormData()
  files.forEach((file) => body.append('files', file))
  if (message) body.append('message', message)
  if (interactionId) body.append('interaction_id', interactionId)
  let response
  try {
    response = await fetch(`${API_BASE_URL}/tickets/${ticketId}/attachments`, { method: 'POST', headers: authHeaders(), body })
  } catch {
    throw new ApiError(`Não foi possível conectar à API em ${API_BASE_URL}.`, 0)
  }
  const data = await parseBody(response)
  if (!response.ok) {
    if (response.status === 413) throw new ApiError('Os arquivos enviados são grandes demais (máximo 10 MB por arquivo).', 413)
    const detail = data && typeof data === 'object' ? data.detail : data
    const message_ = Array.isArray(detail)
      ? detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
      : detail || `Erro ${response.status} ao enviar os anexos.`
    throw new ApiError(message_, response.status)
  }
  return data
}

/** Baixa um anexo (a rota exige o token, então não dá para usar um <a href>). */
export async function downloadTicketAttachment(ticketId, attachment) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/tickets/${ticketId}/attachments/${attachment.id}`, { headers: authHeaders() })
  } catch {
    throw new ApiError(`Não foi possível conectar à API em ${API_BASE_URL}.`, 0)
  }
  if (!response.ok) {
    const data = await parseBody(response)
    throw new ApiError((data && data.detail) || `Erro ${response.status} ao baixar o anexo.`, response.status)
  }
  const blob = await response.blob()
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = attachment.filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
