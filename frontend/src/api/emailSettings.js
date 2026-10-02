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
