import { api } from './client'

export const listAccounts  = ()           => api.get('/accounts')
export const getAccount    = (id)         => api.get(`/accounts/${id}`)
export const createAccount = (body)       => api.post('/accounts', body)
export const deleteAccount = (id)         => api.delete(`/accounts/${id}`)
