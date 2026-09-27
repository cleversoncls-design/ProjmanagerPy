import { api } from './client'

// Apontamento de horas (Timesheet) — ver app/routers/timesheets.py.
export function listTimesheets(params) {
  return api.get('/timesheets', params)
}

export function createTimesheet(payload) {
  return api.post('/timesheets', payload)
}

export function updateTimesheetStatus(timesheetId, status) {
  return api.patch(`/timesheets/${timesheetId}/status`, { status })
}
