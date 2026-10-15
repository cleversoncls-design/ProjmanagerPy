import { api } from './client'

// Agenda de consultores (ResourceSchedule) — ver app/routers/schedules.py.
export function listSchedules(params) {
  return api.get('/resource-schedules', params)
}

export function createSchedule(payload) {
  return api.post('/resource-schedules', payload)
}

export function updateSchedule(scheduleId, payload) {
  return api.patch(`/resource-schedules/${scheduleId}`, payload)
}

export function deleteSchedule(scheduleId) {
  return api.del(`/resource-schedules/${scheduleId}`)
}
