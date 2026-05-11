/**
 * Settings — view and edit runtime platform configuration.
 * Changes via PATCH /settings apply immediately and persist across restarts.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSettings, patchSettings } from '../api/settings'
import { listAccounts, createAccount, deleteAccount } from '../api/accounts'
import { useToast } from '../hooks/useToast'
import ToastContainer from '../components/ToastContainer'
import ConfirmDialog from '../components/ConfirmDialog'
import { format } from 'date-fns'

// ─── Section wrapper ──────────────────────────────────────────────────────────

function Section({ title, description, children }) {
  return (
    <div className="card p-5 space-y-4">
      <div>
        <h2 className="text-base font-semibold text-white">{title}</h2>
        {description && <p className="text-sm text-gray-500 mt-0.5">{description}</p>}
      </div>
      {children}
    </div>
  )
}

// ─── Select (dropdown) setting row ───────────────────────────────────────────

function SelectRow({ label, envVar, value, hint, options, onSave }) {
  const [saving, setSaving] = useState(false)

  const handleChange = useCallback(async (raw) => {
    setSaving(true)
    await onSave(raw)
    setSaving(false)
  }, [onSave])

  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-gray-800 last:border-0">
      <div className="min-w-0 flex-1">
        <div className="text-sm text-gray-200">{label}</div>
        <code className="text-xs text-gray-600 font-mono">{envVar}</code>
        {hint && <p className="text-xs text-gray-600 mt-0.5">{hint}</p>}
      </div>
      <div className="shrink-0 flex items-center gap-2">
        <select
          className="input text-sm py-1 w-36 font-mono"
          value={value ?? ''}
          onChange={e => handleChange(e.target.value)}
        >
          {options.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
        {saving && <span className="text-xs text-gray-600">Saving…</span>}
      </div>
    </div>
  )
}

// ─── Editable setting row (debounced auto-save) ───────────────────────────────

function EditableRow({ label, envVar, value, hint, type = 'number', onSave, min, max, step }) {
  const [draft, setDraft] = useState(String(value ?? ''))
  const [saving, setSaving] = useState(false)
  const timerRef = useRef(null)

  // Sync draft if external value changes (e.g. after successful save)
  useEffect(() => {
    setDraft(String(value ?? ''))
  }, [value])

  const handleChange = useCallback((raw) => {
    setDraft(raw)
    clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      const v = type === 'number' ? Number(raw) : raw
      setSaving(true)
      await onSave(v)
      setSaving(false)
    }, 800)
  }, [onSave, type])

  useEffect(() => () => clearTimeout(timerRef.current), [])

  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-gray-800 last:border-0">
      <div className="min-w-0 flex-1">
        <div className="text-sm text-gray-200">{label}</div>
        <code className="text-xs text-gray-600 font-mono">{envVar}</code>
        {hint && <p className="text-xs text-gray-600 mt-0.5">{hint}</p>}
      </div>
      <div className="shrink-0 flex items-center gap-2">
        <input
          className="input text-sm py-1 w-32 font-mono"
          type={type}
          value={draft}
          min={min} max={max} step={step}
          onChange={e => handleChange(e.target.value)}
        />
        {saving && <span className="text-xs text-gray-600">Saving…</span>}
      </div>
    </div>
  )
}

// ─── Read-only row ────────────────────────────────────────────────────────────

function ReadOnlyRow({ label, envVar, value, hint }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-gray-800 last:border-0">
      <div className="min-w-0 flex-1">
        <div className="text-sm text-gray-200">{label}</div>
        <code className="text-xs text-gray-600 font-mono">{envVar}</code>
        {hint && <p className="text-xs text-gray-600 mt-0.5">{hint}</p>}
      </div>
      <div className="shrink-0 max-w-64 overflow-x-auto">
        <code className="text-sm font-mono text-gray-400 bg-gray-800 px-2 py-0.5 rounded whitespace-nowrap block" title={String(value ?? '')}>
          {value ?? <span className="text-gray-600">—</span>}
        </code>
      </div>
    </div>
  )
}

// ─── Account management ───────────────────────────────────────────────────────

function CreateAccountModal({ onClose }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [name, setName] = useState('')

  const mutation = useMutation({
    mutationFn: createAccount,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      toast.success('Account created')
      onClose()
    },
    onError: e => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-sm mx-4">
        <h2 className="text-lg font-semibold text-white mb-4">New Account</h2>
        <form onSubmit={e => { e.preventDefault(); mutation.mutate({ name }) }} className="space-y-4">
          <div>
            <label className="label">Account Name *</label>
            <input className="input" value={name} onChange={e => setName(e.target.value)} required placeholder="Acme Corp" autoFocus />
          </div>
          {mutation.isError && <p className="text-sm text-red-400">{mutation.error.message}</p>}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" className="btn-secondary" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-primary" disabled={mutation.isPending}>
              {mutation.isPending ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Settings() {
  const toast = useToast()
  const qc = useQueryClient()
  const [showCreateAccount, setShowCreateAccount] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: s, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  })

  const { data: accounts = [], isLoading: accountsLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
  })

  const patchMutation = useMutation({
    mutationFn: patchSettings,
    onSuccess: (updated) => {
      qc.setQueryData(['settings'], updated)
      qc.invalidateQueries({ queryKey: ['health'] })
    },
    onError: e => toast.error(e.message),
  })

  const deleteAccountMutation = useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['accounts'] })
      toast.success('Account deleted')
      setDeleteTarget(null)
    },
    onError: e => toast.error(e.message),
  })

  if (isLoading) return <div className="text-sm text-gray-500 p-4">Loading…</div>

  return (
    <div className="space-y-6">
      <ToastContainer toasts={toast.toasts} />

      <div>
        <h1 className="text-2xl font-semibold text-white">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">
          Editable settings apply immediately. Read-only settings require an environment variable change + restart.
        </p>
      </div>

      {/* Runner */}
      <Section title="Script Runner" description="Controls how many scripts can execute simultaneously.">
        <EditableRow
          label="Max Concurrent Scripts"
          envVar="MAX_CONCURRENT_SCRIPTS"
          value={s?.max_concurrent_scripts}
          hint="Scripts queued beyond this limit wait for a slot."
          type="number" min={1} max={100}
          onSave={v => patchMutation.mutateAsync({ max_concurrent_scripts: v })}
        />
      </Section>

      {/* Monitoring */}
      <Section title="Health Monitoring" description="Thresholds that trigger platform notifications.">
        <EditableRow
          label="Warn Threshold"
          envVar="WARN_THRESHOLD"
          value={s ? Math.round(s.warn_threshold * 100) : ''}
          hint="CPU / memory / disk usage % that creates a warning (e.g. 75)."
          type="number" min={0} max={99} step={1}
          onSave={v => patchMutation.mutateAsync({ warn_threshold: v / 100 })}
        />
        <EditableRow
          label="Critical Threshold"
          envVar="CRITICAL_THRESHOLD"
          value={s ? Math.round(s.critical_threshold * 100) : ''}
          hint="Usage % that creates a critical notification (e.g. 90)."
          type="number" min={0} max={100} step={1}
          onSave={v => patchMutation.mutateAsync({ critical_threshold: v / 100 })}
        />
        <EditableRow
          label="Metrics Interval"
          envVar="METRICS_INTERVAL_SECONDS"
          value={s?.metrics_interval_seconds}
          hint="How often system metrics are sampled (seconds)."
          type="number" min={5} max={300}
          onSave={v => patchMutation.mutateAsync({ metrics_interval_seconds: v })}
        />
      </Section>

      {/* Logging */}
      <Section title="Logging">
        <SelectRow
          label="Log Level"
          envVar="LOG_LEVEL"
          value={s?.log_level}
          hint="DEBUG enables verbose SQLAlchemy query logging."
          options={['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']}
          onSave={v => patchMutation.mutateAsync({ log_level: v })}
        />
      </Section>

      {/* Read-only */}
      <Section title="Read-Only" description="These require an environment variable change and server restart to update.">
        <ReadOnlyRow
          label="Database URL"
          envVar="DATABASE_URL"
          value={s?.database_url}
        />
        <ReadOnlyRow
          label="CORS Allowed Origins"
          envVar="CORS_ALLOWED_ORIGINS"
          value={s?.cors_allowed_origins?.join(', ') ?? '*'}
        />
        <ReadOnlyRow
          label="API Base"
          envVar="—"
          value={window.location.origin + '/api/v1'}
        />
      </Section>

      {/* Accounts */}
      <Section title="Accounts" description="Tenant accounts group scripts and variables by team or project.">
        <div className="flex justify-end">
          <button className="btn-primary text-sm" onClick={() => setShowCreateAccount(true)}>+ New Account</button>
        </div>
        {accountsLoading ? (
          <p className="text-sm text-gray-500">Loading…</p>
        ) : accounts.length === 0 ? (
          <p className="text-sm text-gray-600 text-center py-4">No accounts yet.</p>
        ) : (
          <div className="divide-y divide-gray-800">
            {accounts.map(acct => (
              <div key={acct.id} className="py-3 flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-200 font-medium">{acct.name}</div>
                  <code className="text-xs font-mono text-gray-600 truncate block max-w-xs">{acct.id}</code>
                  <div className="text-xs text-gray-600 mt-0.5">Created {format(new Date(acct.created_at), 'MMM d, yyyy')}</div>
                </div>
                <button className="btn-ghost text-xs text-red-400 hover:text-red-300" onClick={() => setDeleteTarget(acct)}>✕</button>
              </div>
            ))}
          </div>
        )}
      </Section>

      {showCreateAccount && <CreateAccountModal onClose={() => setShowCreateAccount(false)} />}

      <ConfirmDialog
        open={!!deleteTarget}
        title={`Delete account "${deleteTarget?.name}"?`}
        description="All scripts, variables, and tables scoped to this account will be permanently deleted."
        confirmLabel="Delete Account"
        onConfirm={() => deleteAccountMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
