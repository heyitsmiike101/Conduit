import React from 'react'
import { Routes, Route } from 'react-router-dom'

import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Scripts from './pages/Scripts'
import ScriptDetail from './pages/ScriptDetail'
import Tools from './pages/Tools'
import CronJobs from './pages/CronJobs'
import Variables from './pages/Variables'
import Tables from './pages/Tables'
import TableDetail from './pages/TableDetail'
import Executions from './pages/Executions'
import Notifications from './pages/Notifications'
import Settings from './pages/Settings'
import Docs from './pages/Docs'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index          element={<Dashboard />} />
        <Route path="scripts" element={<Scripts />} />
        <Route path="scripts/:id" element={<ScriptDetail />} />
        <Route path="tools"   element={<Tools />} />
        <Route path="tools/:id" element={<ScriptDetail />} />
        <Route path="cron-jobs"  element={<CronJobs />} />
        <Route path="variables"  element={<Variables />} />
        <Route path="tables"     element={<Tables />} />
        <Route path="tables/:id" element={<TableDetail />} />
        <Route path="executions" element={<Executions />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="settings"   element={<Settings />} />
        <Route path="docs"       element={<Docs />} />
      </Route>
    </Routes>
  )
}
