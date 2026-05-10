import { api } from './client'

export const getSettings   = ()     => api.get('/settings')
export const patchSettings = (body) => api.patch('/settings', body)
