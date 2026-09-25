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

export function moveTask(taskId, payload) {
  return api.post(`/tasks/${taskId}/move`, payload)
}

export function deleteTask(taskId) {
  return api.del(`/tasks/${taskId}`)
}

export function recalculateWbs(projectId) {
  return api.post(`/projects/${projectId}/tasks/recalculate-wbs`, {})
}

export function rescheduleTask(taskId, payload = {}) {
  return api.post(`/tasks/${taskId}/reschedule`, payload)
}

export function rescheduleProject(projectId, payload = {}) {
  return api.post(`/projects/${projectId}/reschedule`, payload)
}

export function listDependencies(taskId) {
  return api.get(`/tasks/${taskId}/dependencies`)
}

export function createDependency(payload) {
  return api.post('/task-dependencies', payload)
}

export function deleteDependency(dependencyId) {
  return api.del(`/task-dependencies/${dependencyId}`)
}

export function listAssignments(taskId) {
  return api.get(`/tasks/${taskId}/assignments`)
}

export function assignResource(taskId, payload) {
  return api.post(`/tasks/${taskId}/assignments`, payload)
}

export function removeAssignment(taskId, assignmentId) {
  return api.del(`/tasks/${taskId}/assignments/${assignmentId}`)
}
