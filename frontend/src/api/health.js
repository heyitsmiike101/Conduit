import { api } from './client'
export const getHealth = () => api.get('/health')
