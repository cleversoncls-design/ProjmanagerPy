import { api } from './client'

// "Conhecimento" (pedido do usuário, "NOVAS MELHORIAS": processo de
// registro de conhecimento dos consultores) — ver app/routers/knowledge.py.
// Três grupos de funções, um por tela/acesso (ver
// KNOWLEDGE_CATALOG_ROLES/KNOWLEDGE_SELF_ASSESSMENT_ROLES/
// KNOWLEDGE_REVIEW_ROLES em utils/labels.js).

// --- Cadastro das Funcionalidades (Sistema / Módulo / Funcionalidade) ---

export function getCatalog() {
  return api.get('/knowledge/catalog')
}

export function createSystem(payload) {
  return api.post('/knowledge/systems', payload)
}

export function updateSystem(systemId, payload) {
  return api.patch(`/knowledge/systems/${systemId}`, payload)
}

export function deleteSystem(systemId) {
  return api.del(`/knowledge/systems/${systemId}`)
}

export function createModule(systemId, payload) {
  return api.post(`/knowledge/systems/${systemId}/modules`, payload)
}

export function updateModule(moduleId, payload) {
  return api.patch(`/knowledge/modules/${moduleId}`, payload)
}

export function deleteModule(moduleId) {
  return api.del(`/knowledge/modules/${moduleId}`)
}

export function createFunctionality(moduleId, payload) {
  return api.post(`/knowledge/modules/${moduleId}/functionalities`, payload)
}

export function updateFunctionality(functionalityId, payload) {
  return api.patch(`/knowledge/functionalities/${functionalityId}`, payload)
}

export function deleteFunctionality(functionalityId) {
  return api.del(`/knowledge/functionalities/${functionalityId}`)
}

// --- Registro de Funcionalidades por Consultor / Gerente (autoavaliação) ---

export function getMyCatalog() {
  return api.get('/knowledge/my-catalog')
}

export function upsertMyRating(functionalityId, payload) {
  return api.put(`/knowledge/my-ratings/${functionalityId}`, payload)
}

export function submitMyRatings() {
  return api.post('/knowledge/my-ratings/submit')
}

export function listMySubmissions() {
  return api.get('/knowledge/my-submissions')
}

// --- Revisão e Aprovação ---

export function listSubmissions(statusFilter) {
  return api.get('/knowledge/submissions', statusFilter ? { status_filter: statusFilter } : undefined)
}

export function getSubmission(submissionId) {
  return api.get(`/knowledge/submissions/${submissionId}`)
}

export function reviewSubmission(submissionId, payload) {
  return api.patch(`/knowledge/submissions/${submissionId}`, payload)
}
