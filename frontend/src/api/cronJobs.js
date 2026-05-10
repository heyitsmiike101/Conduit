import { api } from './client'

export const listCronJobs   = (params = {}) => {
  const qs = params.script_id ? `?script_id=${params.script_id}` : ''
  return api.get(`/cron-jobs${qs}`)
}
export const getCronJob     = (id)          => api.get(`/cron-jobs/${id}`)
export const createCronJob  = (body)        => api.post('/cron-jobs', body)
export const updateCronJob  = (id, body)    => api.patch(`/cron-jobs/${id}`, body)
export const deleteCronJob  = (id)          => api.delete(`/cron-jobs/${id}`)
export const pauseCronJob   = (id)          => api.post(`/cron-jobs/${id}/pause`)
export const resumeCronJob  = (id)          => api.post(`/cron-jobs/${id}/resume`)
