import { api } from './client'

export function listResources(params) {
  return api.get('/resources', params)
}

export function createResource(payload) {
  return api.post('/resources', payload)
}

export function updateResource(resourceId, payload) {
  return api.patch(`/resources/${resourceId}`, payload)
}
