import { api } from './client'

// Apontamento de horas (Timesheet) — ver app/routers/timesheets.py.
export function listTimesheets(params) {
  return api.get('/timesheets', params)
}

export function createTimesheet(payload) {
  return api.post('/timesheets', payload)
}

// Editar/excluir só funcionam no próprio apontamento e enquanto ele não
// tiver sido Aprovado (ver _require_own_editable_entry no backend) — a
// API recusa com 422/403 fora disso; a tela só evita oferecer os botões
// nesse caso, nunca confia só na UI.
export function updateTimesheet(timesheetId, payload) {
  return api.put(`/timesheets/${timesheetId}`, payload)
}

export function deleteTimesheet(timesheetId) {
  return api.del(`/timesheets/${timesheetId}`)
}

export function updateTimesheetStatus(timesheetId, status) {
  return api.patch(`/timesheets/${timesheetId}/status`, { status })
}
