/**
 * StatusBadge — coloured pill for execution status and notification level.
 */

import React from 'react'
import clsx from 'clsx'

const STATUS_CLASS = {
  success:     'badge-success',
  running:     'badge-running',
  queued:      'badge-queued',
  failed:      'badge-failed',
  timeout:     'badge-timeout',
  interrupted: 'badge-interrupted',
  warn:        'badge-warn',
  warning:     'badge-warn',
  critical:    'badge-critical',
  info:        'badge-info',
}

export default function StatusBadge({ status }) {
  const cls = STATUS_CLASS[status?.toLowerCase()] ?? 'badge bg-gray-700 text-gray-300'
  return <span className={cls}>{status}</span>
}
