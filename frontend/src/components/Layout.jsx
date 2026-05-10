/**
 * Main application layout — sidebar nav + top bar + content area.
 */

import React from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getNotificationCount } from '../api/notifications'
import { listAccounts } from '../api/accounts'
import { useAccount } from '../context/AccountContext'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/',             label: 'Dashboard',    icon: '◈' },
  { to: '/scripts',      label: 'Scripts',       icon: '⌥' },
  { to: '/tools',        label: 'Tools',         icon: '⚡' },
  { to: '/executions',   label: 'Executions',    icon: '▶' },
  { to: '/cron-jobs',    label: 'Cron Jobs',     icon: '⏱' },
  { to: '/variables',    label: 'Variables',     icon: '⚿' },
  { to: '/tables',       label: 'Tables',        icon: '⊞' },
  { to: '/notifications',label: 'Notifications', icon: '◉' },
  { to: '/settings',     label: 'Settings',      icon: '⚙' },
  { to: '/docs',         label: 'Docs',          icon: '◎' },
]

export default function Layout() {
  const { selectedAccountId, setSelectedAccountId } = useAccount()

  const { data: notifCount } = useQuery({
    queryKey: ['notifications', 'count'],
    queryFn: getNotificationCount,
    refetchInterval: 30_000,
  })

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
  })

  const unread = notifCount?.count ?? 0

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Sidebar ─────────────────────────────────────────────── */}
      <aside className="w-52 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        {/* Brand */}
        <div className="px-4 py-5 border-b border-gray-800">
          <div className="flex items-center gap-2">
            <span className="text-brand-400 text-xl font-bold">⊕</span>
            <span className="font-semibold text-white tracking-wide">Conduit</span>
          </div>
        </div>

        {/* Account selector */}
        <div className="px-3 py-3 border-b border-gray-800">
          <label className="label text-xs">Account</label>
          <select
            className="input text-xs py-1"
            value={selectedAccountId ?? ''}
            onChange={e => setSelectedAccountId(e.target.value || null)}
          >
            <option value="">Global</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-2 overflow-y-auto">
          {NAV_ITEMS.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-2.5 text-sm transition-colors',
                  isActive
                    ? 'bg-brand-900/40 text-brand-300 font-medium'
                    : 'text-gray-400 hover:text-gray-100 hover:bg-gray-800',
                )
              }
            >
              <span className="text-base">{icon}</span>
              <span>{label}</span>
              {label === 'Notifications' && unread > 0 && (
                <span className="ml-auto bg-red-600 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                  {unread > 99 ? '99+' : unread}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-800 text-xs text-gray-600">
          v0.1.0
        </div>
      </aside>

      {/* ── Main area ──────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="h-12 flex-shrink-0 bg-gray-900 border-b border-gray-800 flex items-center px-6">
          <div className="text-sm text-gray-400">
            {selectedAccountId
              ? `Account: ${accounts.find(a => a.id === selectedAccountId)?.name ?? selectedAccountId}`
              : 'Global scope'}
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
