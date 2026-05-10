/**
 * Variables page — unified list of config variables and API keys.
 *
 * Config variables:  value visible immediately, editable inline
 * API keys:          write-only — value is set once and never shown again
 *
 * Both types are encrypted at rest and injected into scripts at runtime.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listVariables, createVariable, updateVariable, deleteVariable } from '../api/variables'
import { useAccount } from '../context/AccountContext'
import { useToast } from '../hooks/useToast'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import ToastContainer from '../components/ToastContainer'
import { format } from 'date-fns'

// ─── Create modal ─────────────────────────────────────────────────────────────

function CreateVariableModal({ type, onClose }) {
  const { selectedAccountId } = useAccount()
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const isApiKey = type === 'api_key'

  const mutation = useMutation({
    mutationFn: createVariable,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['variables'] })
      toast.success(`${isApiKey ? 'API key' : 'Variable'} created`)
      onClose()
    },
    onError: e => toast.error(e.message),
  })

  const handleSubmit = e => {
    e.preventDefault()
    mutation.mutate({
      scope: selectedAccountId ? 'account' : 'global',
      account_id: selectedAccountId || undefined,
      name,
      value,
      is_secret: isApiKey,     // only API keys are secret; config vars are plain
      variable_type: type,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-white mb-1">
          {isApiKey ? 'New API Key' : 'New Config Variable'}
        </h2>
        <p className="text-xs text-gray-500 mb-4">
          {isApiKey
            ? 'API keys are write-only — the value cannot be viewed after saving.'
            : 'Config variables are visible and editable after creation.'}
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Name *</label>
            <input
              className="input font-mono"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              placeholder={isApiKey ? 'STRIPE_API_KEY' : 'BASE_URL'}
              autoFocus
            />
          </div>
          <div>
            <label className="label">Value *</label>
            <input
              className="input font-mono"
              type={isApiKey ? 'password' : 'text'}
              value={value}
              onChange={e => setValue(e.target.value)}
              required
              placeholder="Enter value"
            />
          </div>
          {mutation.isError && <p className="text-sm text-red-400">{mutation.error.message}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Saving…' : `Create ${isApiKey ? 'API Key' : 'Variable'}`}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Inline edit form (config variables only) ─────────────────────────────────

function InlineEditForm({ variable, onDone }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState(variable.name)
  const [value, setValue] = useState(variable.value === '***' ? '' : variable.value)

  const mutation = useMutation({
    mutationFn: (body) => updateVariable(variable.id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['variables'] })
      toast.success('Variable updated')
      onDone()
    },
    onError: e => toast.error(e.message),
  })

  const handleSubmit = e => {
    e.preventDefault()
    const body = { name }
    if (value !== variable.value) body.value = value
    mutation.mutate(body)
  }

  return (
    <form onSubmit={handleSubmit} className="px-4 py-3 bg-gray-900/80 border-t border-gray-800 flex items-center gap-2 flex-wrap">
      <input
        className="input font-mono text-sm py-1 w-44"
        value={name}
        onChange={e => setName(e.target.value)}
        placeholder="Name"
        required
      />
      <input
        className="input font-mono text-sm py-1 flex-1 min-w-32"
        value={value}
        onChange={e => setValue(e.target.value)}
        placeholder="Value"
      />
      <button type="submit" className="btn-primary text-xs" disabled={mutation.isPending}>Save</button>
      <button type="button" className="btn-ghost text-xs" onClick={onDone}>Cancel</button>
    </form>
  )
}

// ─── Variable row ─────────────────────────────────────────────────────────────

function VariableRow({ variable, onDelete }) {
  const [editing, setEditing] = useState(false)
  const isApiKey = variable.variable_type === 'api_key'

  return (
    <div>
      <div className="px-4 py-3 flex items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-sm font-mono text-gray-200">{variable.name}</code>
            {isApiKey && (
              <span className="text-xs px-1.5 py-0.5 bg-purple-900/50 text-purple-400 rounded border border-purple-800">api_key</span>
            )}
            <span className="text-xs text-gray-700">{variable.scope}</span>
          </div>

          <div className="mt-0.5">
            {isApiKey ? (
              <span className="text-xs text-gray-600">
                Added {format(new Date(variable.created_at), 'MMM d, yyyy')} · value hidden
              </span>
            ) : (
              <code className="text-xs font-mono text-gray-400 truncate block max-w-sm">{variable.value}</code>
            )}
          </div>
        </div>

        <div className="flex gap-2 shrink-0">
          {!isApiKey && (
            <button
              className={`btn-ghost text-xs ${editing ? 'text-brand-400' : ''}`}
              onClick={() => setEditing(e => !e)}
            >
              {editing ? 'Cancel' : 'Edit'}
            </button>
          )}
          <button
            className="btn-ghost text-xs text-red-400 hover:text-red-300"
            onClick={() => onDelete(variable)}
          >✕</button>
        </div>
      </div>

      {editing && (
        <InlineEditForm variable={variable} onDone={() => setEditing(false)} />
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Variables() {
  const { selectedAccountId } = useAccount()
  const toast = useToast()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(null)  // null | 'config' | 'api_key'
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: variables = [], isLoading } = useQuery({
    queryKey: ['variables', selectedAccountId],
    queryFn: () => listVariables({ account_id: selectedAccountId }),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteVariable,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['variables'] })
      toast.success('Deleted')
      setDeleteTarget(null)
    },
    onError: e => toast.error(e.message),
  })

  if (isLoading) return <div className="text-sm text-gray-500 p-4">Loading…</div>

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toast.toasts} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Variables</h1>
          <p className="text-sm text-gray-500 mt-1">
            Config variables are visible and editable. API keys are write-only.
            Both are encrypted at rest and injected into scripts at run time.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => setShowCreate('config')}>+ Config Variable</button>
          <button className="btn-primary"   onClick={() => setShowCreate('api_key')}>+ API Key</button>
        </div>
      </div>

      {variables.length === 0 ? (
        <EmptyState
          icon="⚙"
          title="No variables yet"
          description="Add config variables for settings like URLs and feature flags, or API keys for service credentials."
          action={
            <div className="flex gap-2 justify-center">
              <button className="btn-secondary" onClick={() => setShowCreate('config')}>Add Variable</button>
              <button className="btn-primary"   onClick={() => setShowCreate('api_key')}>Add API Key</button>
            </div>
          }
        />
      ) : (
        <div className="card divide-y divide-gray-800">
          {variables.map(v => (
            <VariableRow key={v.id} variable={v} onDelete={setDeleteTarget} />
          ))}
        </div>
      )}

      {showCreate && (
        <CreateVariableModal type={showCreate} onClose={() => setShowCreate(null)} />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete "${deleteTarget?.name}"?`}
        description="Scripts that depend on this will receive an empty value on the next run."
        confirmLabel="Delete"
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
