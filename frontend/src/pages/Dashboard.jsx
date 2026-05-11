/**
 * Dashboard — platform health at a glance.
 * All live data refreshes every 3 s. Metric sparklines follow the server's
 * collection cadence (default 30 s) so they never show stale data.
 */

import React, { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { format, isToday, subHours } from 'date-fns'
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
  const w = 300, h = height, pad = 3
  const values = data.map(d => d.value)
  const dataMax = max ?? Math.max(...values)
  const range = (dataMax - (min ?? 0)) || 1
  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2)
    const y = h - pad - ((v - (min ?? 0)) / range) * (h - pad * 2)
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

// ─── Metric chart card (sparkline + current value) ───────────────────────────

function MetricCard({ label, data, unit, color, fmt, min = 0, max = 1, warn, crit }) {
  const latest = data?.length ? data[data.length - 1].value : null
  const isWarn = warn != null && latest != null && latest >= warn
  const isCrit = crit  != null && latest != null && latest >= crit
  const col  = isCrit ? '#f87171' : isWarn ? '#facc15' : color
  const text = isCrit ? 'text-red-400' : isWarn ? 'text-yellow-400' : 'text-brand-400'
  return (
    <div className="card p-4">
      <div className="flex items-baseline justify-between mb-1">
        <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
        <span className={`text-xl font-bold font-mono leading-none ${text}`}>
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

function StatCard({ label, value, sub, color = 'text-white', pulse = false, warn = false, crit = false, icon }) {
  const c = crit ? 'text-red-400' : warn ? 'text-yellow-400' : color
  return (
    <div className="card p-4 flex items-start gap-3">
      {icon && <div className="text-xl leading-none mt-0.5 shrink-0">{icon}</div>}
      <div className="flex-1 min-w-0">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">{label}</div>
        <div className={`text-2xl font-bold font-mono flex items-center gap-2 ${c}`}>
          {pulse && (
            <span className="relative flex h-2.5 w-2.5 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500" />
            </span>
          )}
          {value ?? '—'}
        </div>
        {sub && <div className="text-xs text-gray-600 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

// ─── Mini performance stat ────────────────────────────────────────────────────

function PerfStat({ label, value, sub, color = 'text-gray-200' }) {
  return (
    <div className="flex flex-col">
      <span className="text-[10px] text-gray-600 uppercase tracking-wide">{label}</span>
      <span className={`text-lg font-bold font-mono ${color}`}>{value ?? '—'}</span>
      {sub && <span className="text-[10px] text-gray-700">{sub}</span>}
    </div>
  )
}

// ─── Script Activity row with error link ──────────────────────────────────────

function ScriptActivityRow({ s, scriptId }) {
  const [expanded, setExpanded] = useState(false)
  const pct = s.total ? Math.round((s.ok / s.total) * 100) : 0
  const barColor = pct >= 80 ? '#34d399' : pct >= 50 ? '#facc15' : '#f87171'

  return (
    <div>
      <div className="flex items-center gap-3 px-4 py-3 hover:bg-gray-800/30 transition-colors">
        <Link to={`/scripts/${s.id}`} className="flex-1 min-w-0 group">
          <div className="text-sm text-gray-200 truncate group-hover:text-brand-400 transition-colors">{s.name}</div>
          <div className="flex items-center gap-2 mt-0.5">
            <div className="h-1 w-20 rounded-full bg-gray-800 overflow-hidden">
              <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: barColor }} />
            </div>
            <span className="text-xs text-gray-600">{pct}% ok</span>
          </div>
        </Link>
        <div className="text-right shrink-0">
          <div className="text-sm font-mono text-gray-300">{s.total} run{s.total !== 1 ? 's' : ''}</div>
          {s.avgDur != null && <div className="text-xs text-gray-600">{s.avgDur.toFixed(2)}s avg</div>}
        </div>
        {s.fail > 0 && (
          <button
            onClick={() => setExpanded(e => !e)}
            className="text-xs text-red-400 hover:text-red-300 font-mono shrink-0 flex items-center gap-1 hover:bg-red-900/20 rounded px-1.5 py-0.5 transition-colors"
            title="Show failed executions"
          >
            ✗ {s.fail} {expanded ? '▲' : '▼'}
          </button>
        )}
      </div>

      {/* Expanded failed executions */}
      {expanded && s.failedExecs?.length > 0 && (
        <div className="border-t border-gray-800 bg-gray-900/60">
          {s.failedExecs.map(exec => (
            <Link
              key={exec.id}
              to={`/scripts/${s.id}`}
              state={{ execId: exec.id }}
              className="flex items-center gap-3 px-6 py-2 hover:bg-gray-800/40 transition-colors"
              onClick={() => setExpanded(false)}
            >
              <StatusBadge status={exec.status} />
              <span className="text-xs text-gray-500">{format(new Date(exec.started_at), 'MMM d HH:mm:ss')}</span>
              {exec.duration_seconds != null && (
                <span className="text-xs font-mono text-gray-600">{exec.duration_seconds.toFixed(2)}s</span>
              )}
              {exec.return_code != null && (
                <span className="text-xs font-mono text-red-500">rc={exec.return_code}</span>
              )}
              <span className="text-xs text-brand-500 ml-auto">View log →</span>
            </Link>
          ))}
        </div>
      )}
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

  const running = health?.active_executions ?? 0
  const queued  = health?.queue_depth ?? 0
  const warn    = health?.settings?.warn_threshold ?? 0.75
  const crit    = health?.settings?.critical_threshold ?? 0.90

  // ── Execution stats ──────────────────────────────────────────────────────
  const completed = useMemo(
    () => recentExecs.filter(e => ['success', 'failed', 'error', 'timeout'].includes(e.status)),
    [recentExecs]
  )
  const succeeded  = completed.filter(e => e.status === 'success')
  const failed     = completed.filter(e => ['failed', 'error', 'timeout'].includes(e.status))
  const successPct = completed.length ? Math.round((succeeded.length / completed.length) * 100) : null
  const todayExecs = useMemo(() => recentExecs.filter(e => isToday(new Date(e.started_at))), [recentExecs])

  const timed = completed.filter(e => e.duration_seconds != null)
  const avgDuration  = timed.length ? timed.reduce((s, e) => s + e.duration_seconds, 0) / timed.length : null
  const maxDuration  = timed.length ? Math.max(...timed.map(e => e.duration_seconds)) : null
  const minDuration  = timed.length ? Math.min(...timed.map(e => e.duration_seconds)) : null

  // Failed in the last hour (from the fetched executions)
  const oneHourAgo   = useMemo(() => subHours(new Date(), 1), [])
  const failedLastHr = useMemo(
    () => failed.filter(e => new Date(e.started_at) >= oneHourAgo).length,
    [failed, oneHourAgo]
  )

  // Longest running CURRENT execution
  const longestRunning = useMemo(() => {
    const active = recentExecs.filter(e => e.status === 'running' && e.started_at)
    if (!active.length) return null
    const oldest = active.reduce((a, b) => new Date(a.started_at) < new Date(b.started_at) ? a : b)
    const secs = Math.round((Date.now() - new Date(oldest.started_at)) / 1000)
    return { name: scriptMap[oldest.script_id] ?? '…', secs }
  }, [recentExecs, scriptMap])

  // ── Disk / memory from health ────────────────────────────────────────────
  const diskFreeGb  = health?.disk_free_gb
  const diskTotalGb = health?.disk_total_gb
  const diskPct     = health?.disk_percent
  const memUsedGb   = health?.memory_used_gb
  const memTotalGb  = health?.memory_total_gb
  const memPct      = health?.memory_percent

  const diskFreeWarn = diskTotalGb != null && diskFreeGb != null && diskFreeGb < diskTotalGb * 0.20
  const diskFreeCrit = diskTotalGb != null && diskFreeGb != null && diskFreeGb < diskTotalGb * 0.10

  // ── Script activity ──────────────────────────────────────────────────────
  const topScripts = useMemo(() => {
    const map = {}
    recentExecs.forEach(e => {
      if (!map[e.script_id]) map[e.script_id] = { total: 0, ok: 0, fail: 0, durations: [], failedExecs: [] }
      map[e.script_id].total++
      if (e.status === 'success') map[e.script_id].ok++
      if (['failed', 'error', 'timeout'].includes(e.status)) {
        map[e.script_id].fail++
        map[e.script_id].failedExecs.push(e)
      }
      if (e.duration_seconds != null) map[e.script_id].durations.push(e.duration_seconds)
    })
    return Object.entries(map)
      .sort((a, b) => b[1].total - a[1].total)
      .slice(0, 8)
      .map(([id, s]) => ({
        id,
        name: scriptMap[id] ?? id.slice(0, 8),
        ...s,
        avgDur: s.durations.length ? s.durations.reduce((a, b) => a + b, 0) / s.durations.length : null,
        failedExecs: s.failedExecs.slice(0, 5),
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

      {/* ── Row 1: live stat cards ─────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard
          icon="⚡"
          label="Running now"
          value={running}
          sub={longestRunning ? `${longestRunning.name} — ${longestRunning.secs}s` : 'Nothing running'}
          color={running > 0 ? 'text-emerald-400' : 'text-gray-400'}
          pulse={running > 0}
        />
        <StatCard
          icon="⏳"
          label="Queued"
          value={queued}
          sub={`Max ${health?.settings?.max_concurrent_scripts ?? '…'} concurrent`}
          warn={queued > 5}
          crit={queued >= 10}
        />
        <StatCard
          icon="📜"
          label="Scripts enabled"
          value={enabledScripts}
          sub={`${cronJobs.length} scheduled · ${scripts.length} total`}
        />
        <StatCard
          icon="🏃"
          label="Today's runs"
          value={todayExecs.length}
          sub={successPct != null ? `${successPct}% success (last ${completed.length})` : 'No completed runs'}
          warn={successPct != null && successPct < 80}
          crit={successPct != null && successPct < 50}
        />
        <StatCard
          icon="💾"
          label="Free disk"
          value={diskFreeGb != null ? `${diskFreeGb.toFixed(1)} GB` : '—'}
          sub={diskTotalGb != null ? `of ${diskTotalGb.toFixed(1)} GB total (${100 - Math.round(diskPct ?? 0)}% free)` : ''}
          warn={diskFreeWarn && !diskFreeCrit}
          crit={diskFreeCrit}
        />
      </div>

      {/* ── Row 2: sparklines (CPU + Memory only) ─────────────────────────── */}
      <div>
        <h2 className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-3">System Health — Last 24 h</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <MetricCard
            label="CPU" data={metrics.cpu_percent}
            unit="%" color="#22d3ee" fmt={v => (v * 100).toFixed(1)} min={0} max={1}
            warn={warn} crit={crit}
          />
          <MetricCard
            label="Memory" data={metrics.memory_percent}
            unit="%" color="#a78bfa" fmt={v => (v * 100).toFixed(1)} min={0} max={1}
            warn={warn} crit={crit}
          />
        </div>
      </div>

      {/* ── Row 3: performance snapshot ───────────────────────────────────── */}
      <div className="card p-4">
        <div className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-4">
          Execution Performance — last {recentExecs.length} runs
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-6 divide-x divide-gray-800">
          <PerfStat
            label="Avg runtime"
            value={avgDuration != null ? `${avgDuration.toFixed(2)}s` : null}
          />
          <div className="pl-6">
            <PerfStat
              label="Longest run"
              value={maxDuration != null ? `${maxDuration.toFixed(2)}s` : null}
              sub={maxDuration != null ? timed.find(e => e.duration_seconds === maxDuration) && scriptMap[timed.find(e => e.duration_seconds === maxDuration)?.script_id] : null}
              color={maxDuration > 60 ? 'text-yellow-400' : 'text-gray-200'}
            />
          </div>
          <div className="pl-6">
            <PerfStat
              label="Shortest run"
              value={minDuration != null ? `${minDuration.toFixed(2)}s` : null}
            />
          </div>
          <div className="pl-6">
            <PerfStat
              label="Failed (1 h)"
              value={failedLastHr}
              color={failedLastHr > 0 ? 'text-red-400' : 'text-emerald-400'}
              sub={failedLastHr > 0 ? 'click ✗ in activity →' : 'All clear'}
            />
          </div>
          <div className="pl-6">
            <PerfStat
              label="Memory used"
              value={memUsedGb != null ? `${memUsedGb.toFixed(1)} GB` : null}
              sub={memTotalGb != null ? `of ${memTotalGb.toFixed(1)} GB (${memPct ?? '?'}%)` : null}
              color={memPct != null && memPct > crit * 100 ? 'text-red-400' : memPct != null && memPct > warn * 100 ? 'text-yellow-400' : 'text-gray-200'}
            />
          </div>
          <div className="pl-6">
            <PerfStat
              label="CPU cores"
              value={health?.cpu_count ?? null}
              sub="logical cores"
            />
          </div>
        </div>
      </div>

      {/* ── Row 4: script activity + recent executions ─────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Script activity */}
        <div className="card">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="text-sm font-medium text-gray-200">Script Activity</h2>
            <p className="text-xs text-gray-600 mt-0.5">
              By run count · click ✗ to expand errors · click name to go to script
            </p>
          </div>
          {topScripts.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-600">No executions yet</div>
          ) : (
            <div className="divide-y divide-gray-800">
              {topScripts.map(s => (
                <ScriptActivityRow key={s.id} s={s} />
              ))}
            </div>
          )}
        </div>

        {/* Recent executions */}
        <div className="card">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-medium text-gray-200">Recent Executions</h2>
              <p className="text-xs text-gray-600 mt-0.5">Click to open script · see log inline</p>
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
                    <div className="text-sm text-gray-300 truncate">
                      {scriptMap[exec.script_id] ?? exec.script_id.slice(0, 8)}
                    </div>
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
