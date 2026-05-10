import { api } from './client'

export const getMetrics = (hours = 24) => api.get(`/metrics?hours=${hours}`)
