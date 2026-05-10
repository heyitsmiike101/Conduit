/**
 * Simple toast notification hook.
 *
 * Usage:
 *   const toast = useToast()
 *   toast.success('Saved!')
 *   toast.error('Failed to save')
 */

import { useState, useCallback } from 'react'

let _nextId = 1

export function useToast() {
  const [toasts, setToasts] = useState([])

  const add = useCallback((message, type = 'info') => {
    const id = _nextId++
    setToasts(prev => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, 4000)
  }, [])

  return {
    toasts,
    success: msg => add(msg, 'success'),
    error:   msg => add(msg, 'error'),
    info:    msg => add(msg, 'info'),
  }
}
