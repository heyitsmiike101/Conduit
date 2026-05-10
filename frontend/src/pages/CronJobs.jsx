/**
 * CronJobs — create, edit inline, pause, resume, and delete scheduled jobs.
 * Includes a cron expression builder and notation reference.
 */

import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { listCronJobs, createCronJob, updateCronJob, deleteCronJob, pauseCronJob, resumeCronJob } from '../api/cronJobs'
import { listScripts } from '../api/scripts'
import { useToast } from '../hooks/useToast'
import EmptyState from '../components/EmptyState'
import ConfirmDialog from '../components/ConfirmDialog'
import ToastContainer from '../components/ToastContainer'

// ─── Cron builder ─────────────────────────────────────────────────────────────

const MINUTE_OPTS  = [['*','Every minute'],['0','On the hour'],['*/5','Every 5 min'],['*/10','Every 10 min'],['*/15','Every 15 min'],['*/30','Every 30 min']]
const HOUR_OPTS    = [['*','Every hour'],['0','Midnight (0)'],['6','6 AM'],['8','8 AM'],['9','9 AM'],['12','Noon'],['17','5 PM'],['20','8 PM']]
const DOM_OPTS     = [['*','Every day'],['1','1st'],['15','15th'],['L','Last day']]
const MONTH_OPTS   = [['*','Every month'],['1','Jan'],['2','Feb'],['3','Mar'],['4','Apr'],['5','May'],['6','Jun'],['7','Jul'],['8','Aug'],['9','Sep'],['10','Oct'],['11','Nov'],['12','Dec']]
const DOW_OPTS     = [['*','Every day'],['1-5','Mon–Fri'],['1','Mon'],['2','Tue'],['3','Wed'],['4','Thu'],['5','Fri'],['6','Sat'],['0','Sun']]

function CronBuilder({ value, onChange }) {
  const parts = value.split(' ')
  const [min, hour, dom, mon, dow] = parts.length === 5 ? parts : ['*','*','*','*','*']

  const set = (index, val) => {
    const p = [min, hour, dom, mon, dow]
    p[index] = val
    onChange(p.join(' '))
  }

  const Select = ({ label, options, index, current }) => (
    <div className="flex-1 min-w-0">
      <div className="text-xs text-gray-600 mb-1">{label}</div>
      <select
        className="input text-xs"
        value={options.some(([v]) => v === current) ? current : '__custom__'}
        onChange={e => set(index, e.target.value === '__custom__' ? current : e.target.value)}
      >
        {options.map(([v, l]) => <option key={v} value={v}>{l} ({v})</option>)}
        {!options.some(([v]) => v === current) && (
          <option value="__custom__">Custom ({current})</option>
        )}
      </select>
    </div>
  )

  return (
    <div className="space-y-3">
      <div className="flex gap-2 flex-wrap">
        <Select label="Minute"       options={MINUTE_OPTS}  index={0} current={min}  />
        <Select label="Hour"         options={HOUR_OPTS}    index={1} current={hour} />
        <Select label="Day of Month" options={DOM_OPTS}     index={2} current={dom}  />
        <Select label="Month"        options={MONTH_OPTS}   index={3} current={mon}  />
        <Select label="Day of Week"  options={DOW_OPTS}     index={4} current={dow}  />
      </div>
      <div className="flex items-center gap-2">
        <div className="text-xs text-gray-600">Expression:</div>
        <input
          className="input font-mono text-xs flex-1"
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder="* * * * *"
        />
      </div>
    </div>
  )
}

// ─── Cron reference ───────────────────────────────────────────────────────────

const EXAMPLES = [
  ['* * * * *',       'Every minute'],
  ['*/5 * * * *',     'Every 5 minutes'],
  ['0 * * * *',       'Every hour'],
  ['0 0 * * *',       'Daily at midnight UTC'],
  ['0 9 * * *',       'Daily at 9 AM UTC'],
  ['0 9 * * 1-5',     'Weekdays at 9 AM UTC'],
  ['0 9 * * 1',       'Every Monday at 9 AM'],
  ['0 */6 * * *',     'Every 6 hours'],
  ['0 0 1 * *',       'First day of every month'],
  ['30 8 * * 1-5',    'Weekdays at 8:30 AM'],
]

function CronReference({ onSelect }) {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button
        type="button"
        className="text-xs text-gray-500 hover:text-gray-300 underline underline-offset-2"
        onClick={() => setOpen(o => !o)}
      >
        {open ? 'Hide reference' : 'Show cron reference'}
      </button>
      {open && (
        <div className="mt-3 bg-gray-950 border border-gray-800 rounded-lg overflow-hidden">
          <div className="px-3 py-2 border-b border-gray-800 text-xs font-medium text-gray-500">
            Format: <code className="font-mono text-gray-400">minute  hour  day-of-month  month  day-of-week</code>
          </div>
          <table className="w-full text-xs">
            <tbody>
              {EXAMPLES.map(([expr, desc]) => (
                <tr
                  key={expr}
                  className="border-b border-gray-800/50 last:border-0 hover:bg-gray-800/40 cursor-pointer"
                  onClick={() => { onSelect(expr); setOpen(false) }}
                >
                  <td className="px-3 py-2 font-mono text-brand-400 whitespace-nowrap">{expr}</td>
                  <td className="px-3 py-2 text-gray-400">{desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-3 py-2 border-t border-gray-800 text-xs text-gray-700">
            Wildcards: <code className="font-mono">*</code> = any · <code className="font-mono">*/n</code> = every n · <code className="font-mono">n-m</code> = range · <code className="font-mono">n,m</code> = list
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Inline edit panel ────────────────────────────────────────────────────────

function InlineEditPanel({ job, onSave, onCancel }) {
  const [name, setName] = useState(job.name ?? '')
  const [description, setDescription] = useState(job.description ?? '')
  const [expr, setExpr] = useState(job.cron_expression)

  return (
    <div className="px-4 pb-4 pt-2 border-t border-gray-800 bg-gray-900/60 space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label text-xs">Name</label>
          <input className="input text-xs" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Daily sync" />
        </div>
        <div>
          <label className="label text-xs">Description</label>
          <input className="input text-xs" value={description} onChange={e => setDescription(e.target.value)} placeholder="What does this schedule do?" />
        </div>
      </div>
      <CronBuilder value={expr} onChange={setExpr} />
      <CronReference onSelect={setExpr} />
      <div className="flex gap-2 justify-end pt-1">
        <button className="btn-secondary text-xs" onClick={onCancel}>Cancel</button>
        <button
          className="btn-primary text-xs"
          disabled={!expr}
          onClick={() => onSave({ expr, name: name || undefined, description: description || undefined })}
        >
          Save Schedule
        </button>
      </div>
    </div>
  )
}

// ─── Create modal ─────────────────────────────────────────────────────────────

function CreateCronModal({ onClose }) {
  const qc = useQueryClient()
  const toast = useToast()
  const [scriptId, setScriptId] = useState('')
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [expr, setExpr] = useState('0 9 * * 1-5')

  const { data: scripts = [] } = useQuery({ queryKey: ['scripts'], queryFn: listScripts })
  // Only show regular scripts (not tools) for scheduling
  const runnableScripts = scripts.filter(s => s.script_type !== 'tool')

  const mutation = useMutation({
    mutationFn: createCronJob,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cron-jobs'] })
      toast.success('Schedule created')
      onClose()
    },
    onError: e => toast.error(e.message),
  })

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="relative bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-lg mx-4">
        <h2 className="text-lg font-semibold text-white mb-4">Schedule a Script</h2>

        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Name</label>
              <input className="input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Daily sync" />
            </div>
            <div>
              <label className="label">Script *</label>
              <select className="input" value={scriptId} onChange={e => setScriptId(e.target.value)} required>
                <option value="">Select a script…</option>
                {runnableScripts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="label">Description</label>
            <input className="input" value={description} onChange={e => setDescription(e.target.value)} placeholder="What does this schedule do?" />
          </div>

          <div>
            <label className="label">Schedule *</label>
            <CronBuilder value={expr} onChange={setExpr} />
          </div>

          <CronReference onSelect={setExpr} />

          {mutation.isError && <p className="text-sm text-red-400">{mutation.error.message}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button
              className="btn-primary"
              disabled={!scriptId || !expr || mutation.isPending}
              onClick={() => mutation.mutate({
                script_id: scriptId,
                cron_expression: expr,
                name: name || undefined,
                description: description || undefined,
              })}
            >
              {mutation.isPending ? 'Scheduling…' : 'Schedule'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CronJobs() {
  const toast = useToast()
  const qc = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editingJobId, setEditingJobId] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: jobs = [], isLoading } = useQuery({
    queryKey: ['cron-jobs'],
    queryFn: listCronJobs,
    refetchInterval: 30_000,
  })

  const { data: scripts = [] } = useQuery({ queryKey: ['scripts'], queryFn: listScripts })
  const scriptMap = Object.fromEntries(scripts.map(s => [s.id, s.name]))

  const deleteMutation = useMutation({
    mutationFn: deleteCronJob,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cron-jobs'] }); toast.success('Schedule removed'); setDeleteTarget(null) },
    onError: e => toast.error(e.message),
  })

  const pauseMutation = useMutation({
    mutationFn: pauseCronJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron-jobs'] }),
    onError: e => toast.error(e.message),
  })

  const resumeMutation = useMutation({
    mutationFn: resumeCronJob,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cron-jobs'] }),
    onError: e => toast.error(e.message),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, expr, name, description }) => updateCronJob(id, {
      cron_expression: expr,
      ...(name !== undefined ? { name } : {}),
      ...(description !== undefined ? { description } : {}),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cron-jobs'] })
      toast.success('Schedule updated')
      setEditingJobId(null)
    },
    onError: e => toast.error(e.message),
  })

  if (isLoading) return <div className="text-sm text-gray-500 p-4">Loading…</div>

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toast.toasts} />

      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Cron Jobs</h1>
          <p className="text-sm text-gray-500 mt-1">{jobs.length} scheduled job{jobs.length !== 1 ? 's' : ''}</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreate(true)}>+ Schedule Script</button>
      </div>

      {jobs.length === 0 ? (
        <EmptyState
          icon="⏱"
          title="No schedules yet"
          description="Schedule a script to run automatically on a cron expression."
          action={<button className="btn-primary" onClick={() => setShowCreate(true)}>Schedule Script</button>}
        />
      ) : (
        <div className="card divide-y divide-gray-800">
          {jobs.map(job => (
            <div key={job.id}>
              {/* Job row */}
              <div className="px-4 py-4 flex items-center gap-4">
                {/* Pause/resume toggle */}
                <button
                  title={job.enabled ? 'Pause' : 'Resume'}
                  onClick={() => job.enabled ? pauseMutation.mutate(job.id) : resumeMutation.mutate(job.id)}
                  className={`w-2 h-8 rounded-full transition-colors shrink-0 ${job.enabled ? 'bg-brand-500' : 'bg-gray-700'}`}
                />

                <div className="flex-1 min-w-0">
                  <div className="font-medium text-gray-100">
                    {job.name || scriptMap[job.script_id] || job.script_id}
                  </div>
                  {job.description && (
                    <p className="text-xs text-gray-500 truncate mt-0.5">{job.description}</p>
                  )}
                  <div className="text-xs text-gray-600 mt-0.5 flex items-center gap-2 flex-wrap">
                    <span className="text-gray-500">{scriptMap[job.script_id] ?? 'Unknown script'}</span>
                    <span>·</span>
                    <code className="font-mono text-gray-400">{job.cron_expression}</code>
                    {job.human_readable && <span className="text-gray-600">{job.human_readable}</span>}
                  </div>
                </div>

                <div className="text-right text-xs text-gray-600 shrink-0">
                  {job.next_run ? (
                    <>
                      <div className="text-gray-500">Next run</div>
                      <div>{format(new Date(job.next_run), 'MMM d, yyyy HH:mm')}</div>
                    </>
                  ) : (
                    <span className="text-yellow-600">Paused</span>
                  )}
                  {job.last_run && (
                    <div className="mt-0.5 text-gray-700">Last: {format(new Date(job.last_run), 'MMM d HH:mm')}</div>
                  )}
                </div>

                <button
                  className={`btn-ghost text-xs shrink-0 ${editingJobId === job.id ? 'text-brand-400' : ''}`}
                  onClick={() => setEditingJobId(editingJobId === job.id ? null : job.id)}
                >
                  {editingJobId === job.id ? 'Cancel' : 'Edit'}
                </button>

                <button
                  className="btn-ghost text-xs text-red-400 hover:text-red-300 shrink-0"
                  onClick={() => setDeleteTarget(job)}
                >✕</button>
              </div>

              {/* Inline editor */}
              {editingJobId === job.id && (
                <InlineEditPanel
                  job={job}
                  onSave={({ expr, name, description }) => updateMutation.mutate({ id: job.id, expr, name, description })}
                  onCancel={() => setEditingJobId(null)}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {showCreate && <CreateCronModal onClose={() => setShowCreate(false)} />}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Remove schedule?"
        description="The script will no longer run on this schedule. Existing executions are not affected."
        confirmLabel="Remove"
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
