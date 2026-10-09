import { api } from './client'

// Tickets internos (pendentes) — ver app/routers/tickets.py.

export function listTickets(params) {
  return api.get('/tickets', params)
}

export function getTicket(ticketId) {
  return api.get(`/tickets/${ticketId}`)
}

export function createTicket(payload) {
  return api.post('/tickets', payload)
}

export function listTicketAssignees() {
  return api.get('/tickets/assignees')
}

export function assignTicket(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/assign`, payload)
}

export function changeTicketStatus(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/status`, payload)
}

export function commentTicket(ticketId, message) {
  return api.post(`/tickets/${ticketId}/comments`, { message })
}

export function changeTicketCriticality(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/criticality`, payload)
}

export function logTicketTime(ticketId, payload) {
  return api.post(`/tickets/${ticketId}/time`, payload)
}
