import { api } from './client'

export function getEmailSettings() {
  return api.get('/email-settings')
}

export function updateEmailSettings(payload) {
  return api.put('/email-settings', payload)
}

export function sendTestEmail(toEmail) {
  return api.post('/email-settings/test-email', { to_email: toEmail })
}

// Pedido do usuário: "poderia criar um botão para abrir uma tela com o
// log dos emails enviados? [...] e que tenha a opção de limpar o log".
export function getEmailLog(limit) {
  return api.get('/email-settings/log', limit ? { limit } : undefined)
}

export function clearEmailLog() {
  return api.del('/email-settings/log')
}
