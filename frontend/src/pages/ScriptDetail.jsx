/**
 * ScriptDetail — Monaco editor with multi-file browser, version history,
 * execution log, and injected config.
 *
 * Layout:
 *   [full-width editor card: file sidebar | Monaco]
 *   [version history (script.py only)]  [injected config]
 *   [full-width execution history + log panel]
 */

import React, { useState, useRef, useCallback, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import Editor from '@monaco-editor/react'
import {
  getScript,
  getScriptContent, saveScriptContent,
  listScriptVersions, getScriptVersion, revertScriptVersion,
  getScriptConfig, saveScriptVariables,
  listScriptFiles, getScriptFile, saveScriptFile, createScriptFile, deleteScriptFile, uploadScriptFile,
} from '../api/scripts'
import { listExecutions, getExecutionLogs, triggerExecution, cancelExecution } from '../api/executions'
import { listCronJobs } from '../api/cronJobs'
import { listAccounts } from '../api/accounts'
import { useToast } from '../hooks/useToast'
import StatusBadge from '../components/StatusBadge'
import ToastContainer from '../components/ToastContainer'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function detectLanguage(filename) {
  const ext = (filename.split('.').pop() || '').toLowerCase()
  const map = {
    py: 'python', js: 'javascript', ts: 'typescript',
    jsx: 'javascript', tsx: 'typescript',
    json: 'json', md: 'markdown', txt: 'plaintext',
    yaml: 'yaml', yml: 'yaml', sh: 'shell', bash: 'shell',
    css: 'css', html: 'html', xml: 'xml', sql: 'sql',
    toml: 'ini', cfg: 'ini', ini: 'ini',
    env: 'plaintext',
  }
  return map[ext] || 'plaintext'
}

function fileIcon(path) {
  const ext = (path.split('.').pop() || '').toLowerCase()
  const map = { py: '🐍', js: '📜', ts: '📘', json: '{}', md: '📝', yaml: '⚙️', yml: '⚙️', sh: '💲', env: '🔑' }
  return map[ext] || '📄'
}

// ─── Execution log panel ──────────────────────────────────────────────────────

function ExecutionLogPanel({ execId }) {
  const { data: logs = [] } = useQuery({
    queryKey: ['execution-logs', execId],
    queryFn: () => getExecutionLogs(execId),
    enabled: !!execId,
    refetchInterval: 2_000,
  })

  if (!execId) return null

  return (
    <div className="card">
      <div className="px-4 py-2 border-b border-gray-800 text-xs text-gray-500 font-medium">
        Execution Output
      </div>
      <div className="bg-gray-950 rounded-b-lg p-4 font-mono text-xs overflow-y-auto max-h-72">
        {logs.length === 0
          ? <span className="text-gray-700">No output yet…</span>
          : logs.map(log => (
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
        }
      </div>
    </div>
  )
}

// ─── Version history panel ────────────────────────────────────────────────────

function VersionHistory({ scriptId, onRevert }) {
  const [expanded, setExpanded] = useState(false)
  const [previewId, setPreviewId] = useState(null)
  const qc = useQueryClient()
  const toast = useToast()

  const { data: versions = [] } = useQuery({
    queryKey: ['script-versions', scriptId],
    queryFn: () => listScriptVersions(scriptId),
    enabled: expanded,
  })

  const { data: preview } = useQuery({
    queryKey: ['script-version', previewId],
    queryFn: () => getScriptVersion(scriptId, previewId),
    enabled: !!previewId,
  })

  const revertMutation = useMutation({
    mutationFn: (vid) => revertScriptVersion(scriptId, vid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['script-content', scriptId] })
      qc.invalidateQueries({ queryKey: ['script-versions', scriptId] })
      toast.success('Reverted to selected version')
      onRevert()
    },
    onError: e => toast.error(e.message),
  })

  return (
    <div className="card">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800/40"
      >
        <span>Version History <span className="text-gray-600 font-normal text-xs">(script.py)</span></span>
        <span className="text-gray-600">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="border-t border-gray-800">
          {versions.length === 0 ? (
            <div className="p-4 text-xs text-gray-600 text-center">No versions yet — save script.py to create one</div>
          ) : (
            <div className="divide-y divide-gray-800 max-h-64 overflow-y-auto">
              {versions.map(v => (
                <div
                  key={v.id}
                  className={`px-4 py-2 flex items-center gap-3 cursor-pointer hover:bg-gray-800/40 ${previewId === v.id ? 'bg-gray-800/40' : ''}`}
                  onClick={() => setPreviewId(previewId === v.id ? null : v.id)}
                >
                  <span className="text-xs font-mono text-gray-500 w-8 shrink-0">v{v.version_number}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-gray-400 truncate">{v.label || 'Auto-saved'}</div>
                    <div className="text-xs text-gray-700">{format(new Date(v.created_at), 'MMM d, yyyy HH:mm')}</div>
                  </div>
                  <button
                    className="btn-ghost text-xs shrink-0"
                    onClick={e => { e.stopPropagation(); revertMutation.mutate(v.id) }}
                    disabled={revertMutation.isPending}
                  >
                    Revert
                  </button>
                </div>
              ))}
            </div>
          )}
          {preview && (
            <div className="border-t border-gray-800 p-3">
              <div className="text-xs text-gray-500 mb-2">Preview — v{preview.version_number}</div>
              <pre className="text-xs font-mono text-gray-400 bg-gray-950 p-3 rounded overflow-x-auto max-h-48 overflow-y-auto">
                {preview.code}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ─── Injected config panel ────────────────────────────────────────────────────

function InjectedConfig({ scriptId }) {
  const [expanded, setExpanded] = useState(false)
  const qc = useQueryClient()
  const toast = useToast()

  const { data: config, isLoading } = useQuery({
    queryKey: ['script-config', scriptId],
    queryFn: () => getScriptConfig(scriptId),
    enabled: expanded,
  })

  const saveMutation = useMutation({
    mutationFn: (selectedIds) => saveScriptVariables(scriptId, { selected_variable_ids: selectedIds }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['script-config', scriptId] })
      toast.success('Variable selection saved')
    },
    onError: e => toast.error(e.message),
  })

  const allVars = [...(config?.global_vars ?? []), ...(config?.account_vars ?? [])]
  const selectedCount = allVars.filter(v => v.selected).length
  const totalCount = allVars.length

  const handleToggle = (varId, isSelected) => {
    const currentSelected = allVars.filter(v => v.selected).map(v => v.id)
    let next = isSelected
      ? [...new Set([...currentSelected, varId])]
      : currentSelected.filter(id => id !== varId)
    const allIds = allVars.map(v => v.id)
    const isAll = next.length === allIds.length && allIds.every(id => next.includes(id))
    saveMutation.mutate(isAll ? null : next)
  }

  return (
    <div className="card">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full px-4 py-3 flex items-center justify-between text-sm font-medium text-gray-300 hover:bg-gray-800/40"
      >
        <span>
          Injected Config
          {totalCount > 0 && (
            <span className="text-gray-500 font-normal ml-1.5">
              ({selectedCount}/{totalCount} var{totalCount !== 1 ? 's' : ''})
            </span>
          )}
        </span>
        <span className="text-gray-600">{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="border-t border-gray-800">
          {isLoading ? (
            <div className="p-4 text-xs text-gray-600">Loading…</div>
          ) : totalCount === 0 ? (
            <div className="p-4 text-xs text-gray-600 text-center">No variables available</div>
          ) : (
            <>
              <div className="px-4 py-2 flex items-center gap-3 border-b border-gray-800">
                <span className="text-xs text-gray-600 flex-1">Check which variables to inject at run time</span>
                <button className="text-xs text-gray-500 hover:text-gray-300" onClick={() => saveMutation.mutate(null)}>All</button>
                <button className="text-xs text-gray-500 hover:text-gray-300" onClick={() => saveMutation.mutate([])}>None</button>
              </div>
              {config.global_vars.length > 0 && (
                <div className="p-3">
                  <div className="text-xs text-gray-600 uppercase tracking-wide mb-2">Global</div>
                  <div className="space-y-1.5">
                    {config.global_vars.map(v => (
                      <VarCheckRow key={v.id} variable={v} onToggle={handleToggle} />
                    ))}
                  </div>
                </div>
              )}
              {config.account_vars.length > 0 && (
                <div className="p-3 border-t border-gray-800">
                  <div className="text-xs text-gray-600 uppercase tracking-wide mb-2">Account</div>
                  <div className="space-y-1.5">
                    {config.account_vars.map(v => (
                      <VarCheckRow key={v.id} variable={v} onToggle={handleToggle} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function VarCheckRow({ variable, onToggle }) {
  return (
    <label className="flex items-center gap-3 text-xs cursor-pointer hover:bg-gray-800/30 rounded px-1 py-0.5">
      <input
        type="checkbox"
        checked={variable.selected}
        onChange={e => onToggle(variable.id, e.target.checked)}
        className="rounded border-gray-600 text-brand-500 focus:ring-brand-500"
      />
      <code className="text-gray-300 font-mono flex-1 truncate">{variable.name}</code>
      <code className="text-gray-600 font-mono truncate max-w-[8rem]">{variable.value}</code>
      {variable.variable_type === 'api_key' && (
        <span className="text-purple-500 px-1 rounded border border-purple-800 bg-purple-900/30 shrink-0">api_key</span>
      )}
    </label>
  )
}

// ─── File sidebar ─────────────────────────────────────────────────────────────

/**
 * Recursively reads a FileSystemEntry (file or directory) and yields
 * { path, file } objects for every text file found.
 *
 * Works in Chrome, Edge, Firefox, Safari 11.1+ via webkitGetAsEntry().
 */
async function* readEntryTree(entry, basePath = '') {
  if (entry.isFile) {
    const file = await new Promise((res, rej) => entry.file(res, rej))
    const path = basePath ? `${basePath}/${entry.name}` : entry.name
    yield { path, file }
  } else if (entry.isDirectory) {
    const reader = entry.createReader()
    const dirBase = basePath ? `${basePath}/${entry.name}` : entry.name
    // readEntries returns ≤100 entries per call — loop until empty
    let batch
    do {
      batch = await new Promise((res, rej) => reader.readEntries(res, rej))
      for (const child of batch) {
        yield* readEntryTree(child, dirBase)
      }
    } while (batch.length > 0)
  }
}

function FileSidebar({ files, activeFilePath, mainFileName, dirtyFiles, onSelect, onCreate, onDelete, isDragOver, uploading }) {
  // 'none' | 'file' | 'folder'
  const [newMode, setNewMode] = useState('none')
  const [newName, setNewName] = useState('')

  const closeForm = () => { setNewMode('none'); setNewName('') }

  const handleCreate = (e) => {
    e.preventDefault()
    const name = newName.trim()
    if (!name) return
    const filename = newMode === 'folder' ? `${name}/__init__.py` : name
    onCreate(filename, closeForm)
  }

  return (
    <div
      className={`flex flex-col border-r transition-colors ${isDragOver ? 'border-brand-500 bg-brand-900/20' : 'border-gray-800 bg-gray-900/60'}`}
      style={{ width: '188px', minWidth: '188px' }}
    >
      {/* Header */}
      <div className="px-3 py-2 text-xs text-gray-600 uppercase tracking-wide border-b border-gray-800 font-medium flex items-center justify-between">
        <span>Files</span>
        {uploading && <span className="text-brand-400 animate-pulse">uploading…</span>}
      </div>

      {/* File list */}
      <div className="flex-1 overflow-y-auto py-1 relative">
        {files.map(f => {
          const isActive = activeFilePath === f.path
          const isDirty = dirtyFiles.has(f.path)
          const isProtected = f.path === mainFileName
          // Show folder hierarchy: indent files in subdirectories
          const depth = f.path.split('/').length - 1
          const displayName = f.path.split('/').pop()
          const prefix = f.path.includes('/') ? f.path.split('/').slice(0, -1).join('/') + '/' : ''

          return (
            <div
              key={f.path}
              className={`group flex items-center gap-1 py-1.5 cursor-pointer text-xs transition-colors ${
                isActive ? 'bg-gray-700/70 text-gray-100' : 'text-gray-400 hover:bg-gray-800/60 hover:text-gray-200'
              }`}
              style={{ paddingLeft: `${8 + depth * 12}px`, paddingRight: '6px' }}
              onClick={() => onSelect(f.path)}
              title={f.path}
            >
              <span className="shrink-0 text-[10px] leading-none">{fileIcon(f.path)}</span>
              <span className="flex-1 truncate font-mono leading-tight text-[11px]">
                {prefix && <span className="text-gray-700">{/* indent handled by padding */}</span>}
                {displayName}
              </span>
              {isDirty && <span className="text-yellow-400 shrink-0 text-[9px]" title="Unsaved changes">●</span>}
              {!isProtected && (
                <button
                  className="shrink-0 text-gray-600 hover:text-red-400 transition-colors leading-none px-0.5 rounded"
                  title={`Delete ${f.path}`}
                  onClick={e => { e.stopPropagation(); onDelete(f.path) }}
                >
                  ×
                </button>
              )}
            </div>
          )
        })}

        {files.length === 0 && (
          <div className="px-3 py-4 text-xs text-gray-700 text-center">
            Drop files here or click + below
          </div>
        )}
      </div>

      {/* Footer: create actions */}
      <div className="border-t border-gray-800 p-2 shrink-0">
        {newMode !== 'none' ? (
          <form onSubmit={handleCreate} className="flex flex-col gap-1.5">
            <div className="text-[10px] text-gray-600 px-1">
              {newMode === 'folder'
                ? 'Folder name (creates __init__.py inside)'
                : 'Filename — use folder/file.py for subfolders'}
            </div>
            <input
              autoFocus
              className="input text-xs py-1 px-2"
              placeholder={newMode === 'folder' ? 'utils' : 'helpers.py'}
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => e.key === 'Escape' && closeForm()}
            />
            <div className="flex gap-1">
              <button type="submit" className="btn-primary text-xs py-0.5 flex-1">Create</button>
              <button type="button" className="btn-secondary text-xs py-0.5 px-2" onClick={closeForm}>✕</button>
            </div>
          </form>
        ) : (
          <div className="flex gap-1">
            <button
              className="flex-1 text-xs text-gray-600 hover:text-gray-300 py-1 transition-colors text-center rounded hover:bg-gray-800/50"
              onClick={() => setNewMode('file')}
              title="New file"
            >
              📄 File
            </button>
            <button
              className="flex-1 text-xs text-gray-600 hover:text-gray-300 py-1 transition-colors text-center rounded hover:bg-gray-800/50"
              onClick={() => setNewMode('folder')}
              title="New folder (creates __init__.py)"
            >
              📁 Folder
            </button>
          </div>
        )}
        <div className="text-[10px] text-gray-700 text-center mt-1">
          or drag & drop files/folders
        </div>
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ScriptDetail() {
  const { id } = useParams()
  const toast = useToast()
  const qc = useQueryClient()

  // Execution state
  const [selectedExecId, setSelectedExecId] = useState(null)

  // File editor state — starts with placeholder; updated once script loads
  const [activeFilePath, setActiveFilePath] = useState('script.py')
  const [mainFileName, setMainFileName] = useState('script.py')
  const [dirtyFiles, setDirtyFiles] = useState(new Set())
  const [saveLabel, setSaveLabel] = useState('')

  // Refs — stable across renders, no stale closure issues
  const editorRef = useRef(null)
  const fileCache = useRef({})       // path → latest editor content (includes unsaved)
  const loadedPathRef = useRef(null) // which path is currently shown in the editor
  const mainContentRef = useRef(null)
  const activeFileDataRef = useRef(null)
  const activeFilePathRef = useRef(activeFilePath)
  const mainFileNameRef = useRef(mainFileName)

  // Drag-and-drop state (card-level drop zone)
  const [isDragOver, setIsDragOver] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const dragCounter = useRef(0)

  // ── Queries ──

  const { data: script, isLoading } = useQuery({
    queryKey: ['scripts', id],
    queryFn: () => getScript(id),
  })

  const { data: files = [], refetch: refetchFiles } = useQuery({
    queryKey: ['script-files', id],
    queryFn: () => listScriptFiles(id),
    enabled: !!script,
    refetchInterval: 15_000,
  })

  // script.py uses the versioned /content endpoint
  const { data: mainContentData } = useQuery({
    queryKey: ['script-content', id],
    queryFn: () => getScriptContent(id),
    enabled: !!script,
  })

  // Other files use the generic /files/{path} endpoint
  const { data: activeFileData } = useQuery({
    queryKey: ['script-file-content', id, activeFilePath],
    queryFn: () => getScriptFile(id, activeFilePath),
    enabled: !!script && activeFilePath !== mainFileName,
    staleTime: Infinity,
  })

  const { data: executions = [] } = useQuery({
    queryKey: ['executions', id],
    queryFn: () => listExecutions({ script_id: id, limit: 20 }),
    refetchInterval: 5_000,
  })

  const { data: cronJobs = [] } = useQuery({
    queryKey: ['cron-jobs', id],
    queryFn: () => listCronJobs({ script_id: id }),
  })

  const { data: accounts = [] } = useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
  })
  const accountName = accounts.find(a => a.id === script?.account_id)?.name

  // Keep refs in sync
  useEffect(() => { activeFilePathRef.current = activeFilePath }, [activeFilePath])
  useEffect(() => { mainFileNameRef.current = mainFileName }, [mainFileName])

  // Derive the main file name from the script's file_path once loaded
  useEffect(() => {
    if (!script) return
    const name = script.file_path.split('/').pop() // basename of the file_path
    setMainFileName(name)
    mainFileNameRef.current = name
    setActiveFilePath(name)
    activeFilePathRef.current = name
  }, [script?.id]) // run once per script, keyed by ID

  // ── Keep data refs current ──
  useEffect(() => { mainContentRef.current = mainContentData }, [mainContentData])
  useEffect(() => { activeFileDataRef.current = activeFileData }, [activeFileData])

  // ── Core: load content into the editor ──
  // Uses refs so it never has stale closures, safe to call any time.
  const loadEditorContent = useCallback(() => {
    const editor = editorRef.current
    if (!editor) return

    const path = activeFilePathRef.current
    if (loadedPathRef.current === path && fileCache.current[path] !== undefined) return

    // 1. Use cached (possibly dirty) content if available
    if (fileCache.current[path] !== undefined) {
      editor.setValue(fileCache.current[path])
      loadedPathRef.current = path
      return
    }

    // 2. Load from fetched data
    let content
    if (path === mainFileNameRef.current) {
      content = mainContentRef.current?.content
    } else {
      const data = activeFileDataRef.current
      if (data?.path === path) content = data.content
    }

    if (content !== undefined) {
      fileCache.current[path] = content
      editor.setValue(content)
      loadedPathRef.current = path
    }
  }, []) // no deps — reads everything from refs

  // Run whenever data arrives or file switches
  useEffect(() => { loadEditorContent() }, [mainContentData, activeFileData, activeFilePath, loadEditorContent])

  // ── Mutations ──

  const runMutation = useMutation({
    mutationFn: () => triggerExecution(id),
    onSuccess: (exec) => {
      toast.success('Run triggered')
      setSelectedExecId(exec.id)
      qc.invalidateQueries({ queryKey: ['executions', id] })
    },
    onError: (e) => toast.error(e.message),
  })

  const cancelMutation = useMutation({
    mutationFn: cancelExecution,
    onSuccess: () => {
      toast.info('Cancellation requested')
      qc.invalidateQueries({ queryKey: ['executions', id] })
    },
    onError: (e) => toast.error(e.message),
  })

  // Save the main file via /content (creates a version snapshot)
  const saveMainMutation = useMutation({
    mutationFn: ({ content, label }) => saveScriptContent(id, { content, label: label || undefined }),
    onSuccess: () => {
      toast.success(`${mainFileName} saved`)
      setDirtyFiles(prev => { const s = new Set(prev); s.delete(mainFileName); return s })
      setSaveLabel('')
      qc.invalidateQueries({ queryKey: ['script-content', id] })
      qc.invalidateQueries({ queryKey: ['script-versions', id] })
    },
    onError: e => toast.error(e.message),
  })

  // Save other files via /files/{path}
  const saveFileMutation = useMutation({
    mutationFn: ({ path, content }) => saveScriptFile(id, path, { content }),
    onSuccess: (_, { path }) => {
      toast.success(`${path} saved`)
      setDirtyFiles(prev => { const s = new Set(prev); s.delete(path); return s })
      qc.invalidateQueries({ queryKey: ['script-files', id] })
    },
    onError: e => toast.error(e.message),
  })

  const createFileMutation = useMutation({
    mutationFn: ({ filename, content = '' }) => createScriptFile(id, { filename, content }),
    onSuccess: (data, { onDone, silent }) => {
      if (!silent) toast.success(`${data.path} created`)
      fileCache.current[data.path] = data.content ?? ''
      refetchFiles()
      if (!silent) {
        // Switch to the new file
        loadedPathRef.current = null
        setActiveFilePath(data.path)
      }
      if (onDone) onDone()
    },
    onError: e => toast.error(e.message),
  })

  // Upload multiple files at once (from drag-and-drop)
  // Accepts { path, file } where file is a raw browser File object (binary-safe)
  const handleUpload = useCallback(async (filesToUpload) => {
    let succeeded = 0
    let skipped = 0
    for (const { path, file } of filesToUpload) {
      try {
        await uploadScriptFile(id, path, file)
        succeeded++
      } catch {
        skipped++
      }
    }
    refetchFiles()
    if (succeeded > 0) {
      toast.success(`Uploaded ${succeeded} file${succeeded !== 1 ? 's' : ''}${skipped ? ` (${skipped} skipped)` : ''}`)
    } else if (skipped > 0) {
      toast.error(`All ${skipped} files failed to upload`)
    }
  }, [id, refetchFiles, toast])

  // ── Card-level drag-and-drop (covers sidebar + Monaco) ──
  const handleCardDragEnter = useCallback((e) => {
    e.preventDefault()
    dragCounter.current += 1
    setIsDragOver(true)
  }, [])

  const handleCardDragLeave = useCallback((e) => {
    e.preventDefault()
    dragCounter.current -= 1
    if (dragCounter.current === 0) setIsDragOver(false)
  }, [])

  const handleCardDragOver = useCallback((e) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }, [])

  const handleCardDrop = useCallback(async (e) => {
    e.preventDefault()
    dragCounter.current = 0
    setIsDragOver(false)

    const items = [...(e.dataTransfer.items || [])]
    if (items.length === 0) return

    setIsUploading(true)
    const toUpload = []

    try {
      for (const item of items) {
        const entry = item.webkitGetAsEntry?.()
        if (!entry) continue
        for await (const { path, file } of readEntryTree(entry)) {
          toUpload.push({ path, file })
        }
      }
      if (toUpload.length > 0) {
        await handleUpload(toUpload)
      } else {
        toast.error('No files found in the drop')
      }
    } finally {
      setIsUploading(false)
    }
  }, [handleUpload, toast])

  const deleteFileMutation = useMutation({
    mutationFn: (path) => deleteScriptFile(id, path),
    onSuccess: (_, path) => {
      toast.success(`${path} deleted`)
      delete fileCache.current[path]
      setDirtyFiles(prev => { const s = new Set(prev); s.delete(path); return s })
      refetchFiles()
      if (activeFilePath === path) {
        loadedPathRef.current = null
        setActiveFilePath(mainFileNameRef.current)
      }
    },
    onError: e => toast.error(e.message),
  })

  // ── Editor event handlers ──

  const handleEditorMount = useCallback((editor) => {
    editorRef.current = editor
    loadedPathRef.current = null // reset so loadEditorContent will run
    loadEditorContent()
  }, [loadEditorContent])

  const handleEditorChange = useCallback(() => {
    const path = activeFilePathRef.current
    const value = editorRef.current?.getValue()
    if (value === undefined) return
    fileCache.current[path] = value
    setDirtyFiles(prev => {
      if (prev.has(path)) return prev
      return new Set([...prev, path])
    })
  }, [])

  const handleFileSelect = useCallback((path) => {
    if (path === activeFilePathRef.current) return
    // Snapshot current editor value before switching
    if (editorRef.current) {
      fileCache.current[activeFilePathRef.current] = editorRef.current.getValue()
    }
    loadedPathRef.current = null
    setSaveLabel('')
    setActiveFilePath(path)
  }, [])

  const handleSave = useCallback(() => {
    const path = activeFilePathRef.current
    const content = editorRef.current?.getValue()
    if (content === undefined) return
    fileCache.current[path] = content
    if (path === mainFileNameRef.current) {
      saveMainMutation.mutate({ content, label: saveLabel })
    } else {
      saveFileMutation.mutate({ path, content })
    }
  }, [saveLabel, saveMainMutation, saveFileMutation])

  const handleCreate = useCallback((filename, onDone) => {
    createFileMutation.mutate({ filename, onDone })
  }, [createFileMutation])

  const handleDelete = useCallback((path) => {
    if (!window.confirm(`Delete "${path}"? This cannot be undone.`)) return
    deleteFileMutation.mutate(path)
  }, [deleteFileMutation])

  // Cmd/Ctrl+S shortcut
  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault()
        if (dirtyFiles.has(activeFilePathRef.current)) handleSave()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [dirtyFiles, handleSave])

  // ── Render ──

  if (isLoading || !script) {
    return <div className="text-sm text-gray-500 p-4">Loading…</div>
  }

  const isTool = script.script_type === 'tool'
  const hasRunning = executions.some(e => e.status === 'running')
  const isActiveFileDirty = dirtyFiles.has(activeFilePath)
  const isSaving = saveMainMutation.isPending || saveFileMutation.isPending

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toast.toasts} />

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
            <Link to={isTool ? '/tools' : '/scripts'} className="hover:text-gray-300">
              {isTool ? 'Tools' : 'Scripts'}
            </Link>
            <span>/</span>
            <span className="text-gray-300">{script.name}</span>
          </div>
          <h1 className="text-xl font-semibold text-white">{script.name}</h1>
          {script.description && <p className="text-sm text-gray-500 mt-0.5">{script.description}</p>}
        </div>
        {!isTool && (
          <div className="flex gap-2">
            {hasRunning ? (
              <button
                className="btn-danger"
                onClick={() => {
                  const running = executions.find(e => e.status === 'running')
                  if (running) cancelMutation.mutate(running.id)
                }}
              >
                ■ Cancel
              </button>
            ) : (
              <button
                className="btn-primary"
                onClick={() => runMutation.mutate()}
                disabled={!script.enabled || runMutation.isPending}
              >
                ▶ Run Now
              </button>
            )}
          </div>
        )}
      </div>

      {/* Meta */}
      <div className="card p-4 flex flex-wrap gap-8 text-sm">
        {isTool ? (
          <div>
            <div className="text-xs text-gray-600 mb-0.5">Import name</div>
            <code className="font-mono text-brand-400 text-sm">import {script.python_name}</code>
          </div>
        ) : (
          <div>
            <div className="text-xs text-gray-600 mb-0.5">Scope</div>
            {script.scope === 'global' ? (
              <span className="text-xs px-1.5 py-0.5 rounded border border-gray-700 bg-gray-800 text-gray-400">global</span>
            ) : (
              <span className="text-xs px-1.5 py-0.5 rounded border border-amber-800 bg-amber-900/40 text-amber-300">
                {accountName ?? 'account'}
              </span>
            )}
          </div>
        )}
        <div>
          <div className="text-xs text-gray-600 mb-0.5">Status</div>
          <div className={script.enabled ? 'text-emerald-400' : 'text-gray-500'}>
            {script.enabled ? 'Enabled' : 'Disabled'}
          </div>
        </div>
        {!isTool && (
          <div>
            <div className="text-xs text-gray-600 mb-0.5">Timeout</div>
            <div className="text-gray-300">{script.timeout_seconds ? `${script.timeout_seconds}s` : 'None'}</div>
          </div>
        )}
        {!isTool && cronJobs.length > 0 && (
          <div>
            <div className="text-xs text-gray-600 mb-0.5">Schedules</div>
            <div className="text-gray-300">{cronJobs.map(c => c.cron_expression).join(', ')}</div>
          </div>
        )}
        <div>
          <div className="text-xs text-gray-600 mb-0.5">Updated</div>
          <div className="text-gray-300">{format(new Date(script.updated_at), 'MMM d, yyyy HH:mm')}</div>
        </div>
      </div>

      {/* ── Full-width editor card — entire card is the drop zone ── */}
      <div
        className={`card overflow-hidden relative transition-colors ${isDragOver ? 'ring-2 ring-brand-500' : ''}`}
        onDragEnter={handleCardDragEnter}
        onDragLeave={handleCardDragLeave}
        onDragOver={handleCardDragOver}
        onDrop={handleCardDrop}
      >
        {/* Full-card drop overlay */}
        {isDragOver && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-brand-900/60 pointer-events-none">
            <div className="bg-gray-900 border-2 border-brand-500 rounded-xl px-8 py-6 text-center shadow-2xl">
              <div className="text-3xl mb-2">📂</div>
              <div className="text-sm font-medium text-brand-300">Drop files or folders to upload</div>
              <div className="text-xs text-gray-500 mt-1">Text files only · binary files skipped</div>
            </div>
          </div>
        )}
        {/* Toolbar */}
        <div className="px-4 py-2 border-b border-gray-800 flex items-center gap-2 bg-gray-900/60">
          {/* Filename + unsaved indicator */}
          <span className="text-xs font-mono text-gray-400 flex-1 truncate">
            {activeFilePath}
            {isActiveFileDirty && (
              <span className="text-yellow-400 ml-1.5" title="Unsaved changes">●</span>
            )}
          </span>

          {/* Version label — only for the main file when dirty */}
          {isActiveFileDirty && activeFilePath === mainFileName && (
            <input
              className="input text-xs py-1 w-36"
              placeholder="Version label (optional)"
              value={saveLabel}
              onChange={e => setSaveLabel(e.target.value)}
            />
          )}

          <span className="text-xs text-gray-700 hidden sm:block">Ctrl+S</span>

          {/* Save */}
          <button
            className="btn-primary text-xs shrink-0"
            onClick={handleSave}
            disabled={!isActiveFileDirty || isSaving}
          >
            {isSaving ? 'Saving…' : isActiveFileDirty ? '● Save' : 'Saved'}
          </button>

          {/* Delete — shown for all files except the main file */}
          {activeFilePath !== mainFileName && (
            <button
              className="btn-ghost text-xs text-red-400 hover:text-red-300 hover:bg-red-900/30 shrink-0"
              onClick={() => handleDelete(activeFilePath)}
              title={`Delete ${activeFilePath}`}
            >
              Delete file
            </button>
          )}
        </div>

        {/* Sidebar + Monaco */}
        <div className="flex" style={{ height: '520px' }}>
          <FileSidebar
            files={files}
            activeFilePath={activeFilePath}
            mainFileName={mainFileName}
            dirtyFiles={dirtyFiles}
            onSelect={handleFileSelect}
            onCreate={handleCreate}
            onDelete={handleDelete}
            isDragOver={isDragOver}
            uploading={isUploading}
          />
          <div className="flex-1 min-w-0">
            <Editor
              height="520px"
              language={detectLanguage(activeFilePath)}
              defaultValue=""
              theme="vs-dark"
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                lineNumbers: 'on',
                scrollBeyondLastLine: false,
                wordWrap: 'on',
                automaticLayout: true,
              }}
              onMount={handleEditorMount}
              onChange={handleEditorChange}
            />
          </div>
        </div>
      </div>

      {/* ── Secondary panels: version history + injected config ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {activeFilePath === mainFileName ? (
          <VersionHistory
            scriptId={id}
            onRevert={() => {
              delete fileCache.current[mainFileName]
              loadedPathRef.current = null
              setDirtyFiles(prev => { const s = new Set(prev); s.delete(mainFileName); return s })
            }}
          />
        ) : (
          <div className="card p-4 text-xs text-gray-600 flex items-center justify-center">
            Version history is available for {mainFileName} only
          </div>
        )}
        {!isTool && <InjectedConfig scriptId={id} />}
      </div>

      {/* ── Execution history (scripts only) ── */}
      {!isTool && (
        <>
          <div className="card">
            <div className="px-4 py-3 border-b border-gray-800 text-sm font-medium text-gray-300">
              Execution History
            </div>
            <div className="divide-y divide-gray-800 max-h-72 overflow-y-auto">
              {executions.length === 0 ? (
                <div className="p-6 text-sm text-gray-600 text-center">No runs yet</div>
              ) : executions.map(exec => (
                <button
                  key={exec.id}
                  onClick={() => setSelectedExecId(exec.id === selectedExecId ? null : exec.id)}
                  className={`w-full px-4 py-3 flex items-center gap-3 text-sm text-left hover:bg-gray-800/50 transition-colors ${selectedExecId === exec.id ? 'bg-gray-800/40' : ''}`}
                >
                  <StatusBadge status={exec.status} />
                  <div className="flex-1 min-w-0">
                    <div className="text-gray-400 text-xs">{format(new Date(exec.started_at), 'MMM d HH:mm:ss')}</div>
                  </div>
                  {exec.duration_seconds != null && (
                    <span className="text-gray-600 text-xs font-mono">{exec.duration_seconds.toFixed(2)}s</span>
                  )}
                  {exec.return_code != null && (
                    <span className="text-gray-600 text-xs font-mono">rc={exec.return_code}</span>
                  )}
                </button>
              ))}
            </div>
          </div>

          <ExecutionLogPanel execId={selectedExecId} />
        </>
      )}
    </div>
  )
}
