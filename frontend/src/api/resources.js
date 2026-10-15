import { api } from './client'

export function listResources(params) {
  return api.get('/resources', params)
}

export function createResource(payload) {
  return api.post('/resources', payload)
}

export function updateResource(resourceId, payload) {
  return api.patch(`/resources/${resourceId}`, payload)
}

/** Convite de calendário (Agenda → Google Calendar, via .ics por e-mail) do
 * PRÓPRIO usuário. 404 quando o usuário não tem recurso vinculado. */
export function getMyCalendarInvite() {
  return api.get('/resources/me/calendar-invite')
}

export function updateMyCalendarInvite(payload) {
  return api.put('/resources/me/calendar-invite', payload)
}

export function sendMyCalendarInviteTest() {
  return api.post('/resources/me/calendar-invite/test')
}
