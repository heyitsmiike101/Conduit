import { api } from './client'

export const listScripts    = (params = {}) => {
  const parts = []
  if (params.account_id)  parts.push(`account_id=${params.account_id}`)
  if (params.script_type) parts.push(`script_type=${params.script_type}`)
  const qs = parts.length ? `?${parts.join('&')}` : ''
  return api.get(`/scripts${qs}`)
}
export const listTools      = ()             => listScripts({ script_type: 'tool' })
export const getScript      = (id)            => api.get(`/scripts/${id}`)
export const createScript   = (body)          => api.post('/scripts', body)
export const updateScript   = (id, body)      => api.patch(`/scripts/${id}`, body)
export const deleteScript   = (id)            => api.delete(`/scripts/${id}`)

// Content (read/write from disk)
export const getScriptContent  = (id)         => api.get(`/scripts/${id}/content`)
export const saveScriptContent = (id, body)   => api.put(`/scripts/${id}/content`, body)

// Version history
export const listScriptVersions  = (id)       => api.get(`/scripts/${id}/versions`)
export const getScriptVersion    = (id, vid)  => api.get(`/scripts/${id}/versions/${vid}`)
export const revertScriptVersion = (id, vid)  => api.post(`/scripts/${id}/versions/${vid}/revert`, {})

// Injected config
export const getScriptConfig      = (id)                => api.get(`/scripts/${id}/config`)
export const saveScriptVariables  = (id, body)          => api.put(`/scripts/${id}/variables`, body)

// File browser — all files in the script directory
// encodePath preserves '/' for subdirectory support with FastAPI :path matching
const encodePath = (p) => p.split('/').map(encodeURIComponent).join('/')
export const listScriptFiles      = (id)                => api.get(`/scripts/${id}/files`)
export const getScriptFile        = (id, path)          => api.get(`/scripts/${id}/files/${encodePath(path)}`)
export const saveScriptFile       = (id, path, body)    => api.put(`/scripts/${id}/files/${encodePath(path)}`, body)
export const createScriptFile     = (id, body)          => api.post(`/scripts/${id}/files`, body)
export const deleteScriptFile     = (id, path)          => api.delete(`/scripts/${id}/files/${encodePath(path)}`)

/** Upload any file type (binary-safe) via multipart form. */
export const uploadScriptFile = (id, path, file) => {
  const form = new FormData()
  form.append('path', path)
  form.append('file', file)
  return api.postForm(`/scripts/${id}/upload`, form)
}
