import { api } from './client'

export function listUsers(params) {
  return api.get('/users', params)
}

export function createUser(payload) {
  return api.post('/users', payload)
}
