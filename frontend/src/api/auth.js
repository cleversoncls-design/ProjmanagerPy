import { api } from './client'

export function login(email, password) {
  return api.postForm('/auth/login', { username: email, password })
}

export function getCurrentUser() {
  return api.get('/users/me')
}

/** Troca da própria senha (qualquer perfil). Devolve um token novo — o
 * backend encerra as outras sessões (token_version), então a sessão atual
 * precisa guardar este token pra continuar logada. */
export function changePassword(currentPassword, newPassword) {
  return api.post('/auth/change-password', { current_password: currentPassword, new_password: newPassword })
}
