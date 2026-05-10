import { api } from './client'

export const listVariables  = (params = {}) => {
  const qs = params.account_id ? `?account_id=${params.account_id}` : ''
  return api.get(`/variables${qs}`)
}
export const getVariable     = (id)           => api.get(`/variables/${id}`)
export const revealVariable  = (id)           => api.get(`/variables/${id}/value?reveal=true`)
export const createVariable  = (body)         => api.post('/variables', body)
export const updateVariable  = (id, body)     => api.patch(`/variables/${id}`, body)
export const deleteVariable  = (id)           => api.delete(`/variables/${id}`)
