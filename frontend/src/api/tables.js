import { api } from './client'

export const listTables   = (params = {}) => {
  const qs = params.account_id ? `?account_id=${params.account_id}` : ''
  return api.get(`/tables${qs}`)
}
export const getTable     = (id)          => api.get(`/tables/${id}`)
export const createTable  = (body)        => api.post('/tables', body)
export const patchTable   = (id, body)    => api.patch(`/tables/${id}`, body)
export const deleteTable  = (id)          => api.delete(`/tables/${id}`)

export const renameColumn = (id, old_name, new_name) => api.post(`/tables/${id}/rename-column`, { old_name, new_name })

export const listRows     = (tableId)               => api.get(`/tables/${tableId}/rows`)
export const insertRow    = (tableId, row_data)      => api.post(`/tables/${tableId}/rows`, { row_data })
export const updateRow    = (tableId, rowId, row_data) => api.patch(`/tables/${tableId}/rows/${rowId}`, { row_data })
export const deleteRow    = (tableId, rowId)         => api.delete(`/tables/${tableId}/rows/${rowId}`)
