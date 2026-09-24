import { api } from './client'

export function getDashboard() {
  return api.get('/dashboard')
}

export function getPortfolio(params) {
  return api.get('/reports/portfolio', params)
}

export function getProjectReport(projectId) {
  return api.get(`/projects/${projectId}/report`)
}

export function getGantt(projectId) {
  return api.get(`/projects/${projectId}/gantt`)
}

export function getSchedule(projectId) {
  return api.get(`/projects/${projectId}/schedule`)
}

export function getEvm(projectId) {
  return api.get(`/projects/${projectId}/report.evm`)
}

export function getStatistics(projectId) {
  return api.get(`/projects/${projectId}/statistics`)
}
