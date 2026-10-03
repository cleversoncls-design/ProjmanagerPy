import { api } from './client'

// Status Report por período (pedido do usuário: "pode implementar os 2
// modelos e colocar na opção de relatorios", depois dos mockups "Interno"/
// "Cliente" validados no canvas de design). Ver app/routers/status_reports.py
// — uma única linha por "fechamento", lida com campos financeiros/burndown/
// next_steps_internal ocultados (null/[]) pelo próprio backend quando quem
// pede é PM do cliente (EXTERNAL_ROLES), nunca um valor "zerado" fajuto.

export function listStatusReports(projectId) {
  return api.get(`/projects/${projectId}/status-reports`)
}

export function getStatusReport(projectId, reportId) {
  return api.get(`/projects/${projectId}/status-reports/${reportId}`)
}

export function createStatusReport(projectId, data) {
  return api.post(`/projects/${projectId}/status-reports`, data)
}

// Pedido do usuário: "ter opção de modificar"/"ter opção de excluir".
export function updateStatusReport(projectId, reportId, data) {
  return api.patch(`/projects/${projectId}/status-reports/${reportId}`, data)
}

export function deleteStatusReport(projectId, reportId) {
  return api.del(`/projects/${projectId}/status-reports/${reportId}`)
}

// Pedido do usuário: "os indicadores [...] venham calculados pelo sistema
// [...] mas que o gerente possa modificar" — sugestão pra pré-preencher o
// formulário de criação; nunca grava nada.
export function getSuggestedRag(projectId) {
  return api.get(`/projects/${projectId}/status-reports/suggested-rag`)
}
