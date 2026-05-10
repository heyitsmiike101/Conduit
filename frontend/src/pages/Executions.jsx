/**
 * Executions — full log of all script runs with filtering by script and status.
 */

import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { format } from 'date-fns'
import { listExecutions, getExecutionLogs } from '../api/executions'
import { listScripts } from '../api/scripts'
import StatusBadge from '../components/StatusBadge'

const STATUSES = ['', 'running', 'success', 'failed', 'queued', 'timeout', 'interrupted']

// ─── Inline log drawer ────────────────────────────────────────────────────────

function LogDrawer({ execId }) {
  const { data: logs = [], isLoading } = useQuery({
    queryKey: ['execution-logs', execId],
    queryFn: () => getExecutionLogs(execId),
    enabled: !!execId,
  })

  return (
    <div className="bg-gray-950 border-t border-gray-800 px-4 py-3 font-mono text-xs overflow-y-auto max-h-48">
      {isLoading ? (
        <span className="text-gray-700">Loading…</span>
      ) : logs.length === 0 ? (
        <span className="text-gray-700">No output recorded</span>
      ) : (
        logs.map(log => (
          <div key={log.id} className={`flex gap-3 ${
            log.stream === 'stderr' ? 'text-red-400'
            : log.stream === 'api'  ? 'text-blue-400'
            : 'text-gray-300'
          }`}>
            <span className="text-gray-700 shrink-0">{format(new Date(log.timestamp), 'HH:mm:ss')}</span>
            <span className="text-gray-600 shrink-0 w-12">[{log.stream}]</span>
            <span className="break-all">{log.content}</span>
          </div>
        ))
      )}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Executions() {
  const [filterScript, setFilterScript] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [expandedId, setExpandedId] = useState(null)
  const [limit, setLimit] = useState(100)

  const { data: scripts = [] } = useQuery({
    queryKey: ['scripts'],
    queryFn: listScripts,
  })
  const scriptMap = Object.fromEntries(scripts.map(s => [s.id, s.name]))

  const { data: executions = [], isLoading, refetch } = useQuery({
    queryKey: ['executions-log', filterScript, filterStatus, limit],
    queryFn: () => listExecutions({
      script_id: filterScript || undefined,
      status:    filterStatus || undefined,
      limit,
    }),
    refetchInterval: 5_000,
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Execution Log</h1>
          <p className="text-sm text-gray-500 mt-1">{executions.length} run{executions.length !== 1 ? 's' : ''} shown</p>
        </div>
        <button className="btn-ghost text-xs" onClick={() => refetch()}>↺ Refresh</button>
      </div>

      {/* Filters */}
      <div className="card p-3 flex flex-wrap gap-3 items-center">
        <select
          className="input text-sm flex-1 min-w-40"
          value={filterScript}
          onChange={e => setFilterScript(e.target.value)}
        >
          <option value="">All scripts</option>
          {scripts.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>

        <select
          className="input text-sm w-44"
          value={filterStatus}
          onChange={e => setFilterStatus(e.target.value)}
        >
          {STATUSES.map(s => (
            <option key={s} value={s}>{s || 'All statuses'}</option>
          ))}
        </select>

        <select
          className="input text-sm w-28"
          value={limit}
          onChange={e => setLimit(Number(e.target.value))}
        >
          {[50, 100, 250, 500].map(n => (
            <option key={n} value={n}>Last {n}</option>
          ))}
        </select>

        {(filterScript || filterStatus) && (
          <button
            className="btn-ghost text-xs"
            onClick={() => { setFilterScript(''); setFilterStatus('') }}
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="text-sm text-gray-500 p-4">Loading…</div>
      ) : executions.length === 0 ? (
        <div className="card p-8 text-center text-sm text-gray-600">No executions match the current filters.</div>
      ) : (
        <div className="card divide-y divide-gray-800">
          {executions.map(exec => (
            <div key={exec.id}>
              <button
                className={`w-full px-4 py-3 flex items-center gap-4 text-sm text-left hover:bg-gray-800/40 transition-colors ${expandedId === exec.id ? 'bg-gray-800/30' : ''}`}
                onClick={() => setExpandedId(expandedId === exec.id ? null : exec.id)}
              >
                <StatusBadge status={exec.status} />

                <div className="flex-1 min-w-0">
                  <div className="text-gray-200 font-medium truncate">
                    {scriptMap[exec.script_id] ?? exec.script_id}
                  </div>
                  <div className="text-xs text-gray-600 font-mono truncate">{exec.script_id}</div>
                </div>

                {exec.duration_seconds != null && (
                  <span className="text-gray-500 text-xs font-mono shrink-0">{exec.duration_seconds.toFixed(2)}s</span>
                )}
                {exec.return_code != null && (
                  <span className="text-gray-600 text-xs font-mono shrink-0">rc={exec.return_code}</span>
                )}

                <div className="text-xs text-gray-600 shrink-0 text-right">
                  <div>{format(new Date(exec.started_at), 'MMM d, yyyy')}</div>
                  <div>{format(new Date(exec.started_at), 'HH:mm:ss')}</div>
                </div>

                <Link
                  to={`/scripts/${exec.script_id}`}
                  className="text-brand-400 text-xs hover:underline shrink-0"
                  onClick={e => e.stopPropagation()}
                >
                  View script →
                </Link>
              </button>

              {expandedId === exec.id && <LogDrawer execId={exec.id} />}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
