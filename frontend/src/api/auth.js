import { api } from './client'

export function login(email, password) {
  return api.postForm('/auth/login', { username: email, password })
}

export function getCurrentUser() {
  return api.get('/users/me')
}
