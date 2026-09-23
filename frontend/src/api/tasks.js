import { api } from './client'

export function listTasks(projectId) {
  return api.get(`/projects/${projectId}/tasks`)
}

export function createTask(projectId, payload) {
  return api.post(`/projects/${projectId}/tasks`, payload)
}

export function updateTask(taskId, payload) {
  return api.patch(`/tasks/${taskId}`, payload)
}
