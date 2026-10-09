import { api } from './client'

export function listProjects(params) {
  return api.get('/projects', params)
}

export function getProject(projectId) {
  return api.get(`/projects/${projectId}`)
}

export function createProject(payload) {
  return api.post('/projects', payload)
}

export function updateProject(projectId, payload) {
  return api.patch(`/projects/${projectId}`, payload)
}

export function deleteProject(projectId) {
  return api.del(`/projects/${projectId}`)
}

// Recursos do projeto — vínculo direto recurso↔projeto, sem passar por
// tarefa (ver ProjectResource em app/models.py).
export function listProjectResources(projectId) {
  return api.get(`/projects/${projectId}/resources`)
}

export function addProjectResource(projectId, payload) {
  return api.post(`/projects/${projectId}/resources`, payload)
}

export function removeProjectResource(projectId, resourceId) {
  return api.del(`/projects/${projectId}/resources/${resourceId}`)
}

// Usuários que podem ser gerente de projeto (Administrador, Gerente de Projetos
// e Gerente de Serviços com função "Gerente de Projetos" no Recurso).
export function listEligibleManagers() {
  return api.get('/projects/eligible-managers')
}
