/**
 * Dashboard — platform health at a glance.
 * Refreshes every 3 seconds. Metrics sparklines refresh every 30 s (server cadence).
 */

import React, { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { format, isToday } from 'date-fns'
import { getHealth } from '../api/health'
import { listExecutions } from '../api/executions'
import { getMetrics } from '../api/metrics'
import { listScripts } from '../api/scripts'
import { listCronJobs } from '../api/cronJobs'
import StatusBadge from '../components/StatusBadge'

const POLL = 3_000

// ─── Sparkline ───────────────────────────────────────────────────────────────

function Sparkline({ data, color = '#22d3ee', height = 44, min = 0, max = 1 }) {
  if (!data || data.length < 2) {
    return <div style={{ height }} className="flex items-center justify-center text-gray-800 text-[10px]">no data</div>
  }
  const w = 300
  const h = height
  const pad = 3
  const values = data.map(d => d.value)
  const dataMin = Math.min(...values)
  const dataMax = max ?? Math.max(...values)
  const range = (dataMax - (min ?? dataMin)) || 1
  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2)
    const y = h - pad - ((v - (min ?? dataMin)) / range) * (h - pad * 2)
    return `${x},${y}`
  })
  const area = [`${pad},${h - pad}`, ...points, `${w - pad},${h - pad}`]
  const gradId = `g${color.replace(/[^a-z0-9]/gi, '')}`
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="w-full" style={{ height, display: 'block' }}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon points={area.join(' ')} fill={`url(#${gradId})`} />
      <polyline points={points.join(' ')} fill="none" stroke={color} strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      {(() => {
        const [cx, cy] = points[points.length - 1].split(',')
        return <circle cx={cx} cy={cy} r="3" fill={color} vectorEffect="non-scaling-stroke" />
      })()}
    </svg>
  )
}

// ─── Metric chart card ────────────────────────────────────────────────────────

function MetricCard({ label, data, unit, color, fmt, min = 0, max = 1, warn, crit }) {
  const latest = data?.length ? data[data.length - 1].value : null
  const isWarn = warn != null && latest != null && latest >= warn
  const isCrit = crit  != null && latest != null && latest >= crit
  const col = isCrit ? '#f87171' : isWarn ? '#facc15' : color
  const textCol = isCrit ? 'text-red-400' : isWarn ? 'text-yellow-400' : 'text-brand-400'
  return (
    <div className="card p-4">
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
        <span className={`text-xl font-bold font-mono leading-none ${textCol}`}>
          {latest != null ? fmt(latest) : '—'}
          <span className="text-xs font-normal text-gray-600 ml-0.5">{unit}</span>
        </span>
      </div>
      <Sparkline data={data} color={col} min={min} max={max} />
      <div className="flex justify-between text-[10px] text-gray-700 mt-1">
        <span>24h ago</span><span>now</span>
      </div>
    </div>
  )
}

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub, color = 'text-white', pulse = false, icon }) {
  return (
    <div className="card p-4 flex items-start gap-3">
      {icon && <div className="text-2xl leading-none mt-0.5">{icon}</div>}
      <div className="flex-1 min-w-0">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
        <div className={`text-2xl font-bold font-mono flex items-center gap-2 ${color}`}>
          {pulse && value > 0 && (
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
          )}
          {value}
        </div>
        {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

// ─── Main ─────────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { data: health, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: POLL,
    refetchIntervalInBackground: true,
    staleTime: 0,
  })

  const { data: recentExecs = [] } = useQuery({
    queryKey: ['executions', 'dashboard'],
    queryFn: () => listExecutions({ limit: 50 }),
    refetchInterval: POLL,
    refetchIntervalInBackground: true,
    staleTime: 0,
  })

  const { data: metrics = {} } = useQuery({
    queryKey: ['metrics', 24],
    queryFn: () => getMetrics(24),
    refetchInterval: 30_000,
    staleTime: 0,
  })

  const { data: scripts = [] } = useQuery({
    queryKey: ['scripts'],
    queryFn: listScripts,
    refetchInterval: POLL,
    staleTime: 0,
  })

  const { data: cronJobs = [] } = useQuery({
    queryKey: ['cron-jobs'],
    queryFn: () => listCronJobs({}),
    refetchInterval: POLL,
    staleTime: 0,
  })

  const scriptMap = useMemo(() => Object.fromEntries(scripts.map(s => [s.id, s.name])), [scripts])

  const running   = health?.active_executions ?? 0
  const queued    = health?.queue_depth ?? 0
  const warn      = health?.settings?.warn_threshold ?? 0.75
  const crit      = health?.settings?.critical_threshold ?? 0.90

  // Derived execution stats
  const todayExecs = useMemo(
    () => recentExecs.filter(e => isToday(new Date(e.started_at))),
    [recentExecs]
  )
  const completed  = recentExecs.filter(e => ['success', 'failed', 'error'].includes(e.status))
  const succeeded  = completed.filter(e => e.status === 'success')
  const successPct = completed.length ? Math.round((succeeded.length / completed.length) * 100) : null
  const avgDuration = useMemo(() => {
    const timed = completed.filter(e => e.duration_seconds != null)
    if (!timed.length) return null
    return (timed.reduce((s, e) => s + e.duration_seconds, 0) / timed.length).toFixed(2)
  }, [completed])

  // Top scripts by run count
  const topScripts = useMemo(() => {
    const counts = {}
    recentExecs.forEach(e => {
      if (!counts[e.script_id]) counts[e.script_id] = { total: 0, ok: 0, fail: 0, durations: [] }
      counts[e.script_id].total++
      if (e.status === 'success') counts[e.script_id].ok++
      if (['failed', 'error'].includes(e.status)) counts[e.script_id].fail++
      if (e.duration_seconds != null) counts[e.script_id].durations.push(e.duration_seconds)
    })
    return Object.entries(counts)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 6)
      .map(([id, s]) => ({
        id,
        name: scriptMap[id] ?? id.slice(0, 8),
        ...s,
        avgDur: s.durations.length ? (s.durations.reduce((a, b) => a + b, 0) / s.durations.length) : null,
      }))
  }, [recentExecs, scriptMap])

  const enabledScripts = scripts.filter(s => s.enabled && s.script_type !== 'tool').length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Live — refreshes every 3 s</p>
        </div>
        {health && (
          <div className="flex items-center gap-2 text-xs text-emerald-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            Platform online
          </div>
        )}
      </div>

      {isError && (
        <div className="bg-red-900/40 border border-red-700 rounded-lg p-4 text-sm text-red-300">
          Cannot reach backend — check that the Conduit server is running on port 8000.
        </div>
      )}

      {/* Stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Running now"
          value={running}
          sub={queued > 0 ? `${queued} queued` : 'Queue empty'}
          color={running > 0 ? 'text-emerald-400' : 'text-gray-400'}
          pulse={running > 0}
          icon="⚡"
        />
        <StatCard
          label="Scripts enabled"
          value={enabledScripts}
          sub={`${scripts.length} total`}
          icon="📜"
        />
        <StatCard
          label="Today's runs"
          value={todayExecs.length}
          sub={successPct != null ? `${successPct}% success (last ${completed.length})` : 'No runs yet'}
          color={successPct != null && successPct < 80 ? 'text-yellow-400' : 'text-white'}
          icon="🏃"
        />
        <StatCard
          label="Avg run time"
          value={avgDuration != null ? `${avgDuration}s` : '—'}
          sub={`${cronJobs.length} scheduled job${cronJobs.length !== 1 ? 's' : ''}`}
          icon="⏱"
        />
      </div>

      {/* System health sparklines */}
      <div>
        <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">System Health — Last 24 h</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricCard label="CPU" data={metrics.cpu_percent}
            unit="%" color="#22d3ee" fmt={v => (v * 100).toFixed(1)} min={0} max={1} warn={warn} crit={crit} />
          <MetricCard label="Memory" data={metrics.memory_percent}
            unit="%" color="#a78bfa" fmt={v => (v * 100).toFixed(1)} min={0} max={1} warn={warn} crit={crit} />
          <MetricCard label="Disk" data={metrics.disk_used_gb ?? metrics.disk_percent}
            unit={metrics.disk_used_gb ? 'GB' : '%'}
            color="#34d399"
            fmt={v => metrics.disk_used_gb ? v.toFixed(1) : (v * 100).toFixed(1)}
            min={0} />
        </div>
      </div>

      {/* Activity split: top scripts + recent executions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Script activity */}
        <div className="card">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="text-sm font-medium text-gray-200">Script Activity</h2>
            <p className="text-xs text-gray-600 mt-0.5">Ranked by run count (last {recentExecs.length} executions)</p>
          </div>
          {topScripts.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-600">No executions yet</div>
          ) : (
            <div className="divide-y divide-gray-800">
              {topScripts.map(s => {
                const pct = s.total ? Math.round((s.ok / s.total) * 100) : 0
                return (
                  <Link
                    key={s.id}
                    to={`/scripts/${s.id}`}
                    className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/30 transition-colors"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-gray-200 truncate">{s.name}</div>
                      <div className="flex items-center gap-2 mt-0.5">
                        {/* Mini success bar */}
                        <div className="h-1 w-20 rounded-full bg-gray-800 overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{ width: `${pct}%`, backgroundColor: pct >= 80 ? '#34d399' : pct >= 50 ? '#facc15' : '#f87171' }}
                          />
                        </div>
                        <span className="text-xs text-gray-600">{pct}% ok</span>
                      </div>
                    </div>
                    <div className="text-right shrink-0">
                      <div className="text-sm font-mono text-gray-300">{s.total} run{s.total !== 1 ? 's' : ''}</div>
                      {s.avgDur != null && (
                        <div className="text-xs text-gray-600">{s.avgDur.toFixed(2)}s avg</div>
                      )}
                    </div>
                    {s.fail > 0 && (
                      <span className="text-xs text-red-400 font-mono shrink-0">{s.fail} ✗</span>
                    )}
                  </Link>
                )
              })}
            </div>
          )}
        </div>

        {/* Recent executions */}
        <div className="card">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium text-gray-200">Recent Executions</h2>
              <p className="text-xs text-gray-600 mt-0.5">Latest {Math.min(recentExecs.length, 15)} runs</p>
            </div>
            <Link to="/executions" className="text-xs text-brand-400 hover:underline shrink-0">View all →</Link>
          </div>
          {recentExecs.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-600">No executions yet</div>
          ) : (
            <div className="divide-y divide-gray-800 max-h-96 overflow-y-auto">
              {recentExecs.slice(0, 15).map(exec => (
                <Link
                  key={exec.id}
                  to={`/scripts/${exec.script_id}`}
                  className="flex items-center gap-3 px-4 py-2.5 hover:bg-gray-800/30 transition-colors"
                >
                  <StatusBadge status={exec.status} />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm text-gray-300 truncate">{scriptMap[exec.script_id] ?? exec.script_id.slice(0, 8)}</div>
                    <div className="text-xs text-gray-600">{format(new Date(exec.started_at), 'MMM d HH:mm:ss')}</div>
                  </div>
                  {exec.duration_seconds != null && (
                    <span className="text-xs font-mono text-gray-600 shrink-0">{exec.duration_seconds.toFixed(2)}s</span>
                  )}
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
