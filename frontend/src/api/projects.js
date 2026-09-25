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
