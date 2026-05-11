import { api } from './client'

export const listExecutions   = (params = {}) => {
  const parts = []
  if (params.script_id) parts.push(`script_id=${params.script_id}`)
  if (params.status)    parts.push(`status=${params.status}`)
  if (params.limit !== undefined) parts.push(`limit=${params.limit}`)
  if (params.started_after) parts.push(`started_after=${encodeURIComponent(params.started_after)}`)
  const qs = parts.length ? `?${parts.join('&')}` : ''
  return api.get(`/executions${qs}`)
}
export const getExecution     = (id)           => api.get(`/executions/${id}`)
export const getExecutionLogs = (id, stream)   => {
  const qs = stream ? `?stream=${stream}` : ''
  return api.get(`/executions/${id}/logs${qs}`)
}
export const triggerExecution = (script_id)    => api.post('/executions', { script_id })
export const cancelExecution  = (id)           => api.post(`/executions/${id}/cancel`)
