import { api } from './client'

export const listNotifications  = (includeDismissed = false) =>
  api.get(`/notifications${includeDismissed ? '?include_dismissed=true' : ''}`)
export const getNotificationCount = () => api.get('/notifications/count')
export const dismissNotification     = (id) => api.post(`/notifications/${id}/dismiss`, {})
export const dismissAllNotifications = ()  => api.post('/notifications/dismiss-all', {})
