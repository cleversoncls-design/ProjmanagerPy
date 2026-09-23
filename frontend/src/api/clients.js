import { api } from './client'

export function listClients() {
  return api.get('/clients')
}

export function createClient(payload) {
  return api.post('/clients', payload)
}

export function getClient(clientId) {
  return api.get(`/clients/${clientId}`)
}
