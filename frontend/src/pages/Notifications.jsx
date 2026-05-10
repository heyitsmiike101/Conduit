/**
 * Notifications — full history of platform alerts with dismiss controls.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { formatDistanceToNow } from 'date-fns'
import { listNotifications, dismissNotification, dismissAllNotifications } from '../api/notifications'
import StatusBadge from '../components/StatusBadge'
import EmptyState from '../components/EmptyState'

export default function Notifications() {
  const qc = useQueryClient()
  const [showDismissed, setShowDismissed] = useState(false)

  // Always fetch ALL notifications so we can show accurate counts in both tabs
  const { data: allNotifications = [], isLoading } = useQuery({
    queryKey: ['notifications', 'all'],
    queryFn: () => listNotifications(true),   // always include dismissed for counting
    refetchInterval: 30_000,
  })

  const dismissMutation = useMutation({
    mutationFn: dismissNotification,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  const dismissAllMutation = useMutation({
    mutationFn: dismissAllNotifications,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })

  if (isLoading) return <div className="text-sm text-gray-500 p-4">Loading…</div>

  const undismissed = allNotifications.filter(n => !n.dismissed_at)
  const dismissed   = allNotifications.filter(n =>  n.dismissed_at)
  const visible     = showDismissed ? allNotifications : undismissed

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Notifications</h1>
          <p className="text-sm text-gray-500 mt-1">
            {undismissed.length} unread · {dismissed.length} dismissed
          </p>
        </div>
        <div className="flex items-center gap-3">
          {undismissed.length > 0 && (
            <button
              className="btn-secondary text-xs"
              onClick={() => dismissAllMutation.mutate()}
              disabled={dismissAllMutation.isPending}
            >
              {dismissAllMutation.isPending ? 'Dismissing…' : 'Dismiss All'}
            </button>
          )}
          <label className="flex items-center gap-2 text-sm text-gray-400 cursor-pointer">
            <input
              type="checkbox"
              checked={showDismissed}
              onChange={e => setShowDismissed(e.target.checked)}
              className="rounded"
            />
            Show dismissed
          </label>
        </div>
      </div>

      {visible.length === 0 ? (
        <EmptyState
          icon="◉"
          title="All clear"
          description={showDismissed ? 'No notifications at all.' : 'No unread notifications. Platform health is looking good.'}
        />
      ) : (
        <div className="space-y-2">
          {visible.map(notif => (
            <div
              key={notif.id}
              className={`card p-4 flex items-start gap-4 ${notif.dismissed_at ? 'opacity-50' : ''}`}
            >
              <StatusBadge status={notif.level} />

              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200">{notif.message}</p>
                <div className="text-xs text-gray-600 mt-1">
                  <span className="text-gray-500">{notif.category}</span>
                  <span className="mx-2">·</span>
                  {formatDistanceToNow(new Date(notif.created_at), { addSuffix: true })}
                  {notif.dismissed_at && (
                    <span className="ml-2 text-gray-700">
                      · dismissed {formatDistanceToNow(new Date(notif.dismissed_at), { addSuffix: true })}
                    </span>
                  )}
                </div>
              </div>

              {!notif.dismissed_at && (
                <button
                  className="btn-ghost text-xs shrink-0"
                  onClick={() => dismissMutation.mutate(notif.id)}
                  disabled={dismissMutation.isPending}
                >
                  Dismiss
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
