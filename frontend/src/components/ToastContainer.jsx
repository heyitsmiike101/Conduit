import React from 'react'
import clsx from 'clsx'

export default function ToastContainer({ toasts }) {
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none">
      {toasts.map(t => (
        <div
          key={t.id}
          className={clsx(
            'px-4 py-3 rounded-lg shadow-lg text-sm font-medium max-w-sm transition-all',
            t.type === 'success' && 'bg-emerald-700 text-white',
            t.type === 'error'   && 'bg-red-700 text-white',
            t.type === 'info'    && 'bg-gray-700 text-gray-100',
          )}
        >
          {t.message}
        </div>
      ))}
    </div>
  )
}
