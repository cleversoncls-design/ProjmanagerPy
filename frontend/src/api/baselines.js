import { api } from './client'

export function listBaselines(projectId) {
  return api.get(`/projects/${projectId}/baselines`)
}

export function createBaseline(projectId, versionName) {
  return api.post(`/projects/${projectId}/baselines`, { version_name: versionName })
}
