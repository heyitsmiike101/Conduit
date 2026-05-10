/**
 * Scripts page — list, create, run, and manage scripts.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { listScripts, createScript, deleteScript, updateScript } from '../api/scripts'
import { listAccounts } from '../api/accounts'
import { listExecutions, triggerExecution } from '../api/executions'
import { useAccount } from '../context/AccountContext'
import { useToast } from '../hooks/useToast'
import StatusBadge from '../components/StatusBadge'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import ToastContainer from '../components/ToastContainer'

// ─── Scope badge ──────────────────────────────────────────────────────────────

function ScopeBadge({ scope, accountName }) {
  if (scope === 'global') {
    return (
      <span className="text-xs px-1.5 py-0.5 rounded border border-gray-700 bg-gray-800 text-gray-400 shrink-0">
        global
      </span>
    )
  }
  return (
    <span className="text-xs px-1.5 py-0.5 rounded border border-amber-800 bg-amber-900/40 text-amber-300 shrink-0">
      {accountName ?? 'account'}
    </span>
  )
}

function CreateScriptModal({ onClose, onCreated }) {
  const { selectedAccountId } = useAccount()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [timeout, setTimeout_] = useState('')

  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: createScript,
    onSuccess: (script) => {
      qc.invalidateQueries(['scripts'])
      onCreated(script)
    },
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    mutation.mutate({
      scope: selectedAccountId ? 'account' : 'global',
      account_id: selectedAccountId || undefined,
      name,
      description: description || undefined,
      timeout_seconds: timeout ? parseInt(timeout) : undefined,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-white mb-4">New Script</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Name *</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} required placeholder="my-automation" />
          </div>
          <div>
            <label className="label">Description</label>
            <input className="input" value={description} onChange={e => setDescription(e.target.value)} placeholder="What does this script do?" />
          </div>
          <div>
            <label className="label">Timeout (seconds)</label>
            <input className="input" type="number" min="1" value={timeout} onChange={e => setTimeout_(e.target.value)} placeholder="No timeout" />
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-400">{mutation.error.message}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create Script'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Scripts() {
  const { selectedAccountId } = useAccount()
  const toast = useToast()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: scripts = [], isLoading } = useQuery({
    queryKey: ['scripts', selectedAccountId],
    queryFn: () => listScripts({ account_id: selectedAccountId }),
  })

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
  })
  const accountMap = Object.fromEntries(accounts.map(a => [a.id, a.name]))

  // Track which scripts have an active (running or queued) execution.
  const { data: activeExecs = [] } = useQuery({
    queryKey: ['executions', 'active'],
    queryFn: () => listExecutions({ limit: 50 }),
    refetchInterval: 3_000,
    staleTime: 0,
  })
  const activeScriptIds = new Set(
    activeExecs
      .filter(e => e.status === 'running' || e.status === 'queued')
      .map(e => e.script_id)
  )

  const deleteMutation = useMutation({
    mutationFn: deleteScript,
    onSuccess: () => {
      qc.invalidateQueries(['scripts'])
      toast.success('Script deleted')
      setDeleteTarget(null)
    },
    onError: (e) => toast.error(e.message),
  })

  const runMutation = useMutation({
    mutationFn: triggerExecution,
    onSuccess: () => toast.success('Run triggered'),
    onError: (e) => toast.error(e.message),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }) => updateScript(id, { enabled }),
    onSuccess: () => qc.invalidateQueries(['scripts']),
    onError: (e) => toast.error(e.message),
  })

  if (isLoading) {
    return <div className="text-sm text-gray-500 p-4">Loading scripts…</div>
  }

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toast.toasts} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Scripts</h1>
          <p className="text-sm text-gray-500 mt-1">{scripts.length} script{scripts.length !== 1 ? 's' : ''}</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          + New Script
        </button>
      </div>

      {scripts.length === 0 ? (
        <EmptyState
          icon="⌥"
          title="No scripts yet"
          description="Create your first script to start automating."
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>Create Script</button>}
        />
      ) : (
        <div className="card divide-y divide-gray-800">
          {scripts.map(script => (
            <div key={script.id} className="px-4 py-4 flex items-center gap-4">
              {/* Enabled toggle */}
              <button
                title={script.enabled ? 'Disable' : 'Enable'}
                onClick={() => toggleMutation.mutate({ id: script.id, enabled: !script.enabled })}
                className={`w-2 h-8 rounded-full transition-colors ${script.enabled ? 'bg-brand-500' : 'bg-gray-700'}`}
              />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link to={`/scripts/${script.id}`} className="font-medium text-gray-100 hover:text-brand-300">
                    {script.name}
                  </Link>
                  <ScopeBadge scope={script.scope} accountName={accountMap[script.account_id]} />
                </div>
                {script.description && (
                  <p className="text-xs text-gray-500 truncate mt-0.5">{script.description}</p>
                )}
              </div>

              <div className="text-xs text-gray-600 text-right">
                <div>Updated</div>
                <div>{format(new Date(script.updated_at), 'MMM d, yyyy HH:mm')}</div>
              </div>

              {/* Actions */}
              <div className="flex gap-2">
                {activeScriptIds.has(script.id) ? (
                  <span
                    title="A run is already in progress — Conduit allows only one run per script at a time."
                    className="text-xs px-2 py-1 rounded bg-brand-900/40 text-brand-300 border border-brand-800 cursor-help"
                  >
                    ● Running
                  </span>
                ) : (
                  <button
                    className="btn-secondary text-xs"
                    onClick={() => runMutation.mutate(script.id)}
                    disabled={!script.enabled || runMutation.isPending}
                  >
                    ▶ Run
                  </button>
                )}
                <Link to={`/scripts/${script.id}`} className="btn-secondary text-xs">Edit</Link>
                <button
                  className="btn-ghost text-xs text-red-400 hover:text-red-300"
                  onClick={() => setDeleteTarget(script)}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateScriptModal
          onClose={() => setShowCreate(false)}
          onCreated={(s) => { setShowCreate(false); toast.success(`Script '${s.name}' created`) }}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete "${deleteTarget?.name}"?`}
        description="This removes the script, all its executions, cron jobs, and the file on disk. This cannot be undone."
        confirmLabel="Delete Script"
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
