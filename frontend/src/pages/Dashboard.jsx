/**
 * Dashboard — system health at a glance with 24-hour sparkline charts.
 */

import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { format, formatDistanceToNow } from 'date-fns'
import { getHealth } from '../api/health'
import { listExecutions } from '../api/executions'
import { getMetrics } from '../api/metrics'
import { listScripts } from '../api/scripts'
import StatusBadge from '../components/StatusBadge'

// ─── Sparkline ────────────────────────────────────────────────────────────────

function Sparkline({ data, color = '#22d3ee', height = 48, min = 0, max = 1 }) {
  if (!data || data.length < 2) {
    return <div style={{ height }} className="flex items-center justify-center text-gray-700 text-xs">No data</div>
  }

  const w = 300
  const h = height
  const pad = 3

  const values = data.map(d => d.value)
  const dataMin = min ?? Math.min(...values)
  const dataMax = max ?? Math.max(...values)
  const range = dataMax - dataMin || 1

  const points = values.map((v, i) => {
    const x = pad + (i / (values.length - 1)) * (w - pad * 2)
    const y = h - pad - ((v - dataMin) / range) * (h - pad * 2)
    return `${x},${y}`
  })

  const areaPoints = [
    `${pad},${h - pad}`,
    ...points,
    `${w - pad},${h - pad}`,
  ]

  const gradId = `grad-${color.replace('#', '')}`

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none"
      className="w-full"
      style={{ height, display: 'block' }}
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0.03" />
        </linearGradient>
      </defs>
      <polygon
        points={areaPoints.join(' ')}
        fill={`url(#${gradId})`}
      />
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {/* Last value dot */}
      {points.length > 0 && (() => {
        const [cx, cy] = points[points.length - 1].split(',')
        return <circle cx={cx} cy={cy} r="3" fill={color} vectorEffect="non-scaling-stroke" />
      })()}
    </svg>
  )
}

// ─── Metric chart card ────────────────────────────────────────────────────────

function MetricChart({ label, data, unit, color, formatVal, min, max, warn, critical }) {
  const latest = data?.length > 0 ? data[data.length - 1].value : null
  const isWarn = warn != null && latest != null && latest >= warn
  const isCrit = critical != null && latest != null && latest >= critical
  const valueColor = isCrit ? 'text-red-400' : isWarn ? 'text-yellow-400' : 'text-brand-400'

  return (
    <div className="card p-3">
      <div className="flex items-baseline justify-between mb-2">
        <div className="text-xs text-gray-500">{label}</div>
        <div className={`text-lg font-bold font-mono leading-none ${valueColor}`}>
          {latest != null ? formatVal(latest) : '—'}
          <span className="text-xs font-normal text-gray-500 ml-0.5">{unit}</span>
        </div>
      </div>
      <Sparkline data={data} color={isCrit ? '#f87171' : isWarn ? '#facc15' : color} min={min} max={max} />
      <div className="flex justify-between text-xs text-gray-700 mt-1">
        <span>24h ago</span>
        <span>now</span>
      </div>
    </div>
  )
}

// ─── Simple stat card ─────────────────────────────────────────────────────────

function StatCard({ label, value, unit = '', warn = false, critical = false }) {
  const color = critical ? 'text-red-400' : warn ? 'text-yellow-400' : 'text-brand-400'
  return (
    <div className="card p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold font-mono ${color}`}>
        {value}<span className="text-base font-normal text-gray-500 ml-1">{unit}</span>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const { data: health, isError } = useQuery({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 3_000,
    refetchIntervalInBackground: true,
    staleTime: 0,
  })

  const { data: recentExecs = [] } = useQuery({
    queryKey: ['executions', 'recent'],
    queryFn: () => listExecutions({ limit: 10 }),
    refetchInterval: 3_000,
    refetchIntervalInBackground: true,
    staleTime: 0,
  })

  const { data: metrics = {} } = useQuery({
    queryKey: ['metrics', 24],
    queryFn: () => getMetrics(24),
    refetchInterval: 10_000,
    refetchIntervalInBackground: true,
    staleTime: 0,
  })

  const { data: scripts = [] } = useQuery({
    queryKey: ['scripts'],
    queryFn: listScripts,
    staleTime: 60_000,
  })
  const scriptMap = Object.fromEntries(scripts.map(s => [s.id, s.name]))

  const running = health?.active_executions ?? 0
  const queued  = health?.queue_depth ?? 0
  const warn    = health?.settings?.warn_threshold ?? 0.75
  const crit    = health?.settings?.critical_threshold ?? 0.90

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Platform health and recent activity</p>
      </div>

      {isError && (
        <div className="bg-red-900/40 border border-red-700 rounded-lg p-4 text-sm text-red-300">
          Cannot reach backend — check that the Conduit server is running on port 8000.
        </div>
      )}

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Platform status"  value={health ? 'Online' : '—'} />
        <StatCard label="Active scripts"   value={running} warn={running > 7} critical={running >= 10} />
        <StatCard label="Queue depth"      value={queued}  warn={queued > 5} />
        <StatCard label="Recent runs"      value={recentExecs.length} />
      </div>

      {/* 24h system health */}
      <div>
        <h2 className="text-sm font-medium text-gray-400 mb-3">System Health — Last 24 Hours</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
          <MetricChart
            label="CPU Usage"
            data={metrics.cpu_percent}
            unit="%"
            color="#22d3ee"
            formatVal={v => (v * 100).toFixed(1)}
            min={0} max={1}
            warn={warn} critical={crit}
          />
          <MetricChart
            label="Memory Usage"
            data={metrics.memory_percent}
            unit="%"
            color="#a78bfa"
            formatVal={v => (v * 100).toFixed(1)}
            min={0} max={1}
            warn={warn} critical={crit}
          />
          <MetricChart
            label="Disk Used"
            data={metrics.disk_used_gb ?? metrics.disk_percent}
            unit={metrics.disk_used_gb ? 'GB' : '%'}
            color="#34d399"
            formatVal={v => metrics.disk_used_gb ? v.toFixed(1) : (v * 100).toFixed(1)}
            min={0}
          />
          <MetricChart
            label="Network In"
            data={metrics.network_recv_mb ?? metrics.network_sent_mb}
            unit="MB"
            color="#fb923c"
            formatVal={v => v.toFixed(2)}
            min={0}
          />
        </div>
      </div>

      {/* Recent executions */}
      <div className="card">
        <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-200">Recent Executions</h2>
          <Link to="/executions" className="text-xs text-brand-400 hover:underline">View all →</Link>
        </div>
        {recentExecs.length === 0 ? (
          <div className="p-8 text-center text-sm text-gray-600">No executions yet</div>
        ) : (
          <div className="divide-y divide-gray-800">
            {recentExecs.map(exec => (
              <div key={exec.id} className="px-4 py-3 flex items-center gap-4 text-sm">
                <StatusBadge status={exec.status} />
                <div className="flex-1 min-w-0">
                  <div className="text-gray-300 text-sm truncate">
                    {scriptMap[exec.script_id] ?? exec.script_id}
                  </div>
                </div>
                {exec.duration_seconds != null && (
                  <span className="text-gray-600 text-xs">{exec.duration_seconds.toFixed(2)}s</span>
                )}
                <span className="text-gray-600 text-xs">
                  {format(new Date(exec.started_at), 'MMM d HH:mm')}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
