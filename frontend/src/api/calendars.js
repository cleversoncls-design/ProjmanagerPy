import { api } from './client'

export function listCalendars() {
  return api.get('/calendars')
}

export function createCalendar(payload) {
  return api.post('/calendars', payload)
}

export function listHolidays(calendarId) {
  return api.get(`/calendars/${calendarId}/holidays`)
}

export function addHoliday(calendarId, payload) {
  return api.post(`/calendars/${calendarId}/holidays`, payload)
}

export function updateHoliday(calendarId, holidayId, payload) {
  return api.patch(`/calendars/${calendarId}/holidays/${holidayId}`, payload)
}

export function deleteHoliday(calendarId, holidayId) {
  return api.del(`/calendars/${calendarId}/holidays/${holidayId}`)
}
