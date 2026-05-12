import { api } from './client'

export const listPackages     = ()       => api.get('/packages')
export const installPackage   = (body)   => api.post('/packages/install', body)
export const uninstallPackage = (name)   => api.delete(`/packages/${encodeURIComponent(name)}`)
