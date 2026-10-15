import { api } from './client'

// "Grupos de Tarefas" (pedido do usuário: agrupador reutilizável de
// tarefas, aplicado depois como filhas de uma tarefa de projeto — ver
// app/routers/task_groups.py) — gerenciado numa página própria do menu
// lateral, restrita a MANAGEMENT_ROLES (mesmo critério de Calendários).

export function listTaskGroups() {
  return api.get('/task-groups')
}

export function getTaskGroup(groupId) {
  return api.get(`/task-groups/${groupId}`)
}

export function createTaskGroup(payload) {
  return api.post('/task-groups', payload)
}

export function updateTaskGroup(groupId, payload) {
  return api.put(`/task-groups/${groupId}`, payload)
}

export function deleteTaskGroup(groupId) {
  return api.del(`/task-groups/${groupId}`)
}
