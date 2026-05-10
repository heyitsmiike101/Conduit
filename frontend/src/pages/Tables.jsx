/**
 * Tables page — list and create InfoTables.
 * Individual table rows are managed in TableDetail.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { listTables, createTable, deleteTable } from '../api/tables'
import { useAccount } from '../context/AccountContext'
import { useToast } from '../hooks/useToast'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import ToastContainer from '../components/ToastContainer'

function CreateTableModal({ onClose }) {
  const { selectedAccountId } = useAccount()
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState('')
  const [schemaStr, setSchemaStr] = useState('{\n  "columns": ["id", "name", "value"]\n}')

  const mutation = useMutation({
    mutationFn: createTable,
    onSuccess: () => {
      qc.invalidateQueries(['tables'])
      toast.success('Table created')
      onClose()
    },
    onError: e => toast.error(e.message),
  })

  const handleSubmit = e => {
    e.preventDefault()
    try {
      JSON.parse(schemaStr) // validate before sending
    } catch {
      toast.error('Schema must be valid JSON')
      return
    }
    mutation.mutate({
      scope: selectedAccountId ? 'account' : 'global',
      account_id: selectedAccountId || undefined,
      name,
      schema_json: schemaStr,
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-white mb-4">New Table</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Name *</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} required placeholder="customer-list" />
          </div>
          <div>
            <label className="label">Schema (JSON)</label>
            <textarea
              className="input font-mono h-28 resize-none"
              value={schemaStr}
              onChange={e => setSchemaStr(e.target.value)}
            />
            <p className="text-xs text-gray-600 mt-1">
              Flexible — define any structure. Rows store arbitrary JSON.
            </p>
          </div>
          {mutation.isError && <p className="text-sm text-red-400">{mutation.error.message}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create Table'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function Tables() {
  const { selectedAccountId } = useAccount()
  const toast = useToast()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: tables = [], isLoading } = useQuery({
    queryKey: ['tables', selectedAccountId],
    queryFn: () => listTables({ account_id: selectedAccountId }),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTable,
    onSuccess: () => {
      qc.invalidateQueries(['tables'])
      toast.success('Table deleted')
      setDeleteTarget(null)
    },
    onError: e => toast.error(e.message),
  })

  if (isLoading) return <div className="text-sm text-gray-500 p-4">Loading…</div>

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toast.toasts} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Tables</h1>
          <p className="text-sm text-gray-500 mt-1">Structured data shared between scripts</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>+ New Table</button>
      </div>

      {tables.length === 0 ? (
        <EmptyState
          icon="⊞"
          title="No tables yet"
          description="InfoTables let scripts share structured data with each other and with the platform UI."
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>Create Table</button>}
        />
      ) : (
        <div className="card divide-y divide-gray-800">
          {tables.map(table => (
            <div key={table.id} className="px-4 py-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <Link to={`/tables/${table.id}`} className="font-medium text-gray-100 hover:text-brand-300">
                  {table.name}
                </Link>
                <div className="text-xs text-gray-600 mt-0.5">
                  {table.scope} · Created {format(new Date(table.created_at), 'MMM d, yyyy')}
                </div>
              </div>
              <Link to={`/tables/${table.id}`} className="btn-secondary text-xs">View Rows</Link>
              <button
                className="btn-ghost text-xs text-red-400 hover:text-red-300"
                onClick={() => setDeleteTarget(table)}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {showCreate && <CreateTableModal onClose={() => setShowCreate(false)} />}

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete table "${deleteTarget?.name}"?`}
        description="All rows will be permanently deleted. Scripts that write to this table will fail."
        confirmLabel="Delete Table"
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
