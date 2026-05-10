/**
 * ConfirmDialog — modal confirmation before destructive actions.
 *
 * Usage:
 *   const [confirm, setConfirm] = useState(null)
 *   <ConfirmDialog
 *     open={!!confirm}
 *     title="Delete script?"
 *     description="This cannot be undone."
 *     onConfirm={() => { doDelete(); setConfirm(null) }}
 *     onCancel={() => setConfirm(null)}
 *   />
 */

import React from 'react'

export default function ConfirmDialog({ open, title, description, onConfirm, onCancel, confirmLabel = 'Delete', danger = true }) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60" onClick={onCancel} />
      {/* Dialog */}
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-white mb-2">{title}</h2>
        {description && <p className="text-sm text-gray-400 mb-6">{description}</p>}
        <div className="flex justify-end gap-3">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button
            className={danger ? 'btn-danger' : 'btn-primary'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
