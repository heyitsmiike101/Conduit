/**
 * Tools — create and manage supporting Python modules that can be imported
 * by any script running on the platform.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { format } from 'date-fns'
import { listTools, createScript, deleteScript, updateScript } from '../api/scripts'
import { listPackages, installPackage, uninstallPackage } from '../api/packages'
import { useToast } from '../hooks/useToast'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import ToastContainer from '../components/ToastContainer'

// ─── Create modal ─────────────────────────────────────────────────────────────

function CreateToolModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  const qc = useQueryClient()
  const mutation = useMutation({
    mutationFn: createScript,
    onSuccess: (tool) => {
      qc.invalidateQueries(['scripts'])
      onCreated(tool)
    },
  })

  // Derive the Python import name in real-time as the user types
  const pythonName = name
    ? name.replace(/[^a-zA-Z0-9]+/g, '_').replace(/^_+|_+$/g, '').toLowerCase().replace(/^\d/, s => 'tool_' + s) || 'tool'
    : ''

  const handleSubmit = (e) => {
    e.preventDefault()
    mutation.mutate({
      scope: 'global',
      name,
      description: description || undefined,
      script_type: 'tool',
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-white mb-1">New Supporting Tool</h2>
        <p className="text-sm text-gray-500 mb-4">
          A shared Python module any script can import. Tools are always global.
        </p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="label">Name *</label>
            <input
              className="input"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              placeholder="e.g. Runn API Helper"
            />
            {pythonName && (
              <p className="text-xs text-gray-500 mt-1">
                Import as: <code className="font-mono text-brand-400">import {pythonName}</code>
              </p>
            )}
          </div>
          <div>
            <label className="label">Description</label>
            <input
              className="input"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="What does this tool provide?"
            />
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-400">{mutation.error.message}</p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create Tool'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Packages panel ───────────────────────────────────────────────────────────

function PackagesPanel({ toast }) {
  const [installInput, setInstallInput] = useState('')
  const [installOutput, setInstallOutput] = useState(null)
  const [filter, setFilter] = useState('')
  const [uninstallTarget, setUninstallTarget] = useState(null)

  const { data: packages = [], isLoading, refetch } = useQuery({
    queryKey: ['packages'],
    queryFn: listPackages,
  })

  const installMutation = useMutation({
    mutationFn: installPackage,
    onSuccess: (data) => {
      setInstallOutput(data)
      if (data.success) {
        setInstallInput('')
        refetch()
        toast.success('Package installed')
      } else {
        toast.error('Install failed — see output below')
      }
    },
    onError: (e) => toast.error(e.message),
  })

  const uninstallMutation = useMutation({
    mutationFn: uninstallPackage,
    onSuccess: (data) => {
      setUninstallTarget(null)
      if (data.success) {
        refetch()
        toast.success('Package uninstalled')
      } else {
        toast.error('Uninstall failed')
      }
    },
    onError: (e) => { setUninstallTarget(null); toast.error(e.message) },
  })

  const filtered = packages.filter(p =>
    p.name.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div className="space-y-4">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-white">Python Packages</h2>
          <p className="text-sm text-gray-500 mt-1">
            {isLoading ? 'Loading…' : `${packages.length} package${packages.length !== 1 ? 's' : ''} installed in this environment`}
          </p>
        </div>
      </div>

      {/* Install form */}
      <div className="card p-4 space-y-3">
        <label className="label">Install Package</label>
        <div className="flex gap-2">
          <input
            className="input flex-1"
            value={installInput}
            onChange={e => { setInstallInput(e.target.value); setInstallOutput(null) }}
            placeholder="e.g. requests  or  pandas==2.1.0  or  httpx>=0.27"
            onKeyDown={e => {
              if (e.key === 'Enter' && installInput.trim()) {
                installMutation.mutate({ package: installInput.trim() })
              }
            }}
          />
          <button
            className="btn-primary shrink-0"
            disabled={!installInput.trim() || installMutation.isPending}
            onClick={() => installMutation.mutate({ package: installInput.trim() })}
          >
            {installMutation.isPending ? 'Installing…' : 'Install'}
          </button>
        </div>
        {installOutput && (
          <pre className={`rounded p-3 text-xs font-mono whitespace-pre-wrap max-h-48 overflow-y-auto ${
            installOutput.success ? 'bg-gray-950 text-green-400' : 'bg-gray-950 text-red-400'
          }`}>
            {installOutput.output || (installOutput.success ? 'Done.' : 'Unknown error.')}
          </pre>
        )}
      </div>

      {/* Package list */}
      {!isLoading && packages.length > 0 && (
        <div className="card">
          <div className="px-4 pt-3 pb-2">
            <input
              className="input text-sm"
              placeholder="Filter packages…"
              value={filter}
              onChange={e => setFilter(e.target.value)}
            />
          </div>
          <div className="divide-y divide-gray-800 max-h-96 overflow-y-auto">
            {filtered.length === 0 ? (
              <p className="px-4 py-3 text-sm text-gray-600">No packages match "{filter}"</p>
            ) : (
              filtered.map(pkg => (
                <div key={pkg.name} className="px-4 py-2.5 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-mono text-gray-200">{pkg.name}</span>
                    <span className="ml-2 text-xs text-gray-600">{pkg.version}</span>
                  </div>
                  <button
                    className="btn-ghost text-xs text-red-400 hover:text-red-300 shrink-0"
                    onClick={() => setUninstallTarget(pkg)}
                  >
                    Uninstall
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <ConfirmDialog
        open={!!uninstallTarget}
        title={`Uninstall "${uninstallTarget?.name}"?`}
        description={`This removes ${uninstallTarget?.name} ${uninstallTarget?.version} from the environment. Scripts that import it will break.`}
        confirmLabel="Uninstall"
        onConfirm={() => uninstallMutation.mutate(uninstallTarget.name)}
        onCancel={() => setUninstallTarget(null)}
      />
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Tools() {
  const toast = useToast()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: tools = [], isLoading } = useQuery({
    queryKey: ['scripts', 'tools'],
    queryFn: listTools,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteScript,
    onSuccess: () => {
      qc.invalidateQueries(['scripts'])
      toast.success('Tool deleted')
      setDeleteTarget(null)
    },
    onError: (e) => toast.error(e.message),
  })

  const toggleMutation = useMutation({
    mutationFn: ({ id, enabled }) => updateScript(id, { enabled }),
    onSuccess: () => qc.invalidateQueries(['scripts']),
    onError: (e) => toast.error(e.message),
  })

  if (isLoading) {
    return <div className="text-sm text-gray-500 p-4">Loading tools…</div>
  }

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toast.toasts} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Supporting Tools</h1>
          <p className="text-sm text-gray-500 mt-1">
            {tools.length} tool{tools.length !== 1 ? 's' : ''} · Importable by all scripts
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>
          + New Tool
        </button>
      </div>

      {/* How it works banner */}
      <div className="card px-4 py-3 bg-gray-900/60 border-brand-900/50 flex items-start gap-3">
        <span className="text-brand-400 text-lg mt-0.5">⚡</span>
        <div className="text-sm text-gray-400 space-y-1">
          <p>
            Tools are shared Python modules available to every script at run time.
            Create a tool, add your helper code in the editor, then import it from any script:
          </p>
          <code className="block font-mono text-xs text-brand-300 mt-1">
            import my_tool_name<br />
            from my_tool_name import my_function
          </code>
        </div>
      </div>

      {tools.length === 0 ? (
        <EmptyState
          icon="⚡"
          title="No tools yet"
          description="Create a supporting tool to share utility code across all your scripts."
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>Create Tool</button>}
        />
      ) : (
        <div className="card divide-y divide-gray-800">
          {tools.map(tool => (
            <div key={tool.id} className="px-4 py-4 flex items-center gap-4">
              {/* Enabled toggle */}
              <button
                title={tool.enabled ? 'Disable (will stop being available to scripts)' : 'Enable'}
                onClick={() => toggleMutation.mutate({ id: tool.id, enabled: !tool.enabled })}
                className={`w-2 h-8 rounded-full transition-colors shrink-0 ${tool.enabled ? 'bg-brand-500' : 'bg-gray-700'}`}
              />

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <Link to={`/tools/${tool.id}`} className="font-medium text-gray-100 hover:text-brand-300">
                    {tool.name}
                  </Link>
                  {!tool.enabled && (
                    <span className="text-xs px-1.5 py-0.5 rounded border border-gray-700 bg-gray-800 text-gray-500">
                      disabled
                    </span>
                  )}
                </div>
                {tool.description && (
                  <p className="text-xs text-gray-500 truncate mt-0.5">{tool.description}</p>
                )}
                <p className="text-xs text-gray-700 font-mono mt-0.5">
                  import <span className="text-brand-500">{tool.python_name}</span>
                </p>
              </div>

              <div className="text-xs text-gray-600 text-right shrink-0">
                <div>Updated</div>
                <div>{format(new Date(tool.updated_at), 'MMM d, yyyy HH:mm')}</div>
              </div>

              {/* Actions */}
              <div className="flex gap-2 shrink-0">
                <Link to={`/tools/${tool.id}`} className="btn-secondary text-xs">Edit</Link>
                <button
                  className="btn-ghost text-xs text-red-400 hover:text-red-300"
                  onClick={() => setDeleteTarget(tool)}
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <CreateToolModal
          onClose={() => setShowCreate(false)}
          onCreated={(t) => { setShowCreate(false); toast.success(`Tool '${t.name}' created`) }}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete "${deleteTarget?.name}"?`}
        description="This removes the tool and its files from disk. Scripts that import it will break. This cannot be undone."
        confirmLabel="Delete Tool"
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Divider */}
      <hr className="border-gray-800" />

      <PackagesPanel toast={toast} />
    </div>
  )
}
