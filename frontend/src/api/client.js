const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

const TOKEN_KEY = 'pmpy_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

/** Erro de API com o status HTTP anexado, para as telas decidirem o que
 * mostrar (ex.: 409 de duplicidade vs. 422 de validação vs. 403 de
 * permissão) sem precisar re-parsear a mensagem. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { method = 'GET', json, form, signal } = {}) {
  const headers = {}
  let body

  if (form) {
    body = new URLSearchParams(form)
    headers['Content-Type'] = 'application/x-www-form-urlencoded'
  } else if (json !== undefined) {
    body = JSON.stringify(json)
    headers['Content-Type'] = 'application/json'
  }

  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method, headers, body, signal })
  } catch {
    throw new ApiError(
      `Não foi possível conectar à API em ${API_BASE_URL}. Verifique se ela está rodando e se VITE_API_BASE_URL aponta para o lugar certo.`,
      0,
    )
  }

  const text = await response.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !path.startsWith('/auth/login')) {
      clearToken()
    }
    const detail = data && typeof data === 'object' ? data.detail : data
    const message = Array.isArray(detail)
      ? detail.map((item) => item.msg || JSON.stringify(item)).join('; ')
      : detail || `Erro ${response.status} ao chamar ${path}`
    throw new ApiError(message, response.status)
  }

  return data
}

function withQuery(path, params) {
  if (!params) return path
  const entries = Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '')
  if (entries.length === 0) return path
  return `${path}?${new URLSearchParams(entries).toString()}`
}

export const api = {
  get: (path, params) => request(withQuery(path, params)),
  post: (path, json) => request(path, { method: 'POST', json }),
  patch: (path, json) => request(path, { method: 'PATCH', json }),
  postForm: (path, form) => request(path, { method: 'POST', form }),
}
