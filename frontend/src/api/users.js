import { api } from './client'

export function listUsers(params) {
  return api.get('/users', params)
}

export function createUser(payload) {
  return api.post('/users', payload)
}

export function updateUser(userId, payload) {
  return api.patch(`/users/${userId}`, payload)
}

export function resetPassword(userId, payload) {
  return api.post(`/users/${userId}/reset-password`, payload)
}

/** Autoatendimento de idioma — qualquer usuário logado troca o próprio
 * idioma (PATCH /users/me), sem precisar de permissão de ADMIN. */
export function updateMyLanguage(language) {
  return api.patch('/users/me', { language })
}
