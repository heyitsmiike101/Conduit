/**
 * TableDetail — spreadsheet-style row editor with keyboard navigation.
 *
 * - Click a cell to edit it inline
 * - Tab / Shift+Tab moves to the next / previous cell
 * - Enter commits; Escape cancels
 * - Columns derived from schema + all row keys
 */

import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { format } from 'date-fns'
import { getTable, listRows, insertRow, updateRow, deleteRow, patchTable } from '../api/tables'
import { useToast } from '../hooks/useToast'
import ToastContainer from '../components/ToastContainer'
import ConfirmDialog from '../components/ConfirmDialog'

// ─── Helpers ──────────────────────────────────────────────────────────────────

function parseRow(rowDataJson) {
  try { return JSON.parse(rowDataJson) } catch { return {} }
}

function parseSchemaColumns(schemaJson) {
  try {
    const s = JSON.parse(schemaJson)
    if (Array.isArray(s.columns) && s.columns.length > 0) return s.columns
  } catch {}
  return []
}

function deriveColumns(schemaJson, rows) {
  const schemaCols = parseSchemaColumns(schemaJson)
  const all = new Set(schemaCols)
  rows.forEach(row => Object.keys(parseRow(row.row_data_json)).forEach(k => all.add(k)))
  const extras = [...all].filter(k => !schemaCols.includes(k))
  return [...schemaCols, ...extras]
}

function coerce(str) {
  const t = str.trim()
  if (t === '') return t
  if (t === 'true') return true
  if (t === 'false') return false
  const n = Number(t)
  return isNaN(n) ? str : n
}

// ─── Editable cell ────────────────────────────────────────────────────────────

function EditableCell({ value, isEditing, onStartEdit, onCommit, onCancel, onTab }) {
  const [draft, setDraft] = useState('')
  const inputRef = useRef(null)
  const didCommit = useRef(false)

  // Sync draft and focus when editing starts
  useEffect(() => {
    if (isEditing) {
      didCommit.current = false
      setDraft(value === null || value === undefined ? '' : String(value))
      // Defer focus so the DOM has updated
      requestAnimationFrame(() => {
        if (inputRef.current) {
          inputRef.current.focus()
          inputRef.current.select()
        }
      })
    }
  }, [isEditing, value])

  const commit = useCallback(() => {
    if (didCommit.current) return
    didCommit.current = true
    onCommit(coerce(draft))
  }, [draft, onCommit])

  if (!isEditing) {
    return (
      <td
        className="px-3 py-2 text-sm text-gray-300 cursor-pointer hover:bg-gray-800/60 whitespace-nowrap max-w-[200px]"
        onClick={onStartEdit}
        title="Click to edit"
      >
        <span className="block truncate">
          {value === null || value === undefined
            ? <span className="text-gray-700">—</span>
            : String(value)}
        </span>
      </td>
    )
  }

  return (
    <td className="px-1 py-0.5">
      <input
        ref={inputRef}
        className="input text-sm py-1 w-full min-w-[100px]"
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onBlur={() => { commit(); onCancel() }}
        onKeyDown={e => {
          if (e.key === 'Enter')  { e.preventDefault(); commit(); onCancel() }
          if (e.key === 'Escape') { onCancel() }
          if (e.key === 'Tab')    { e.preventDefault(); commit(); onTab(e.shiftKey) }
        }}
      />
    </td>
  )
}

// ─── New row form ─────────────────────────────────────────────────────────────

function NewRowForm({ columns, onSave, onCancel }) {
  const [values, setValues] = useState(() => Object.fromEntries(columns.map(c => [c, ''])))
  const inputRefs = useRef([])

  const handleSave = () => {
    const data = {}
    columns.forEach(c => { data[c] = coerce(values[c]) })
    onSave(data)
  }

  return (
    <tr className="bg-brand-900/10 border-b border-gray-700">
      {columns.map((col, i) => (
        <td key={col} className="px-1 py-1">
          <input
            ref={el => { inputRefs.current[i] = el }}
            className="input text-sm py-1 w-full min-w-[80px]"
            placeholder={col}
            value={values[col]}
            autoFocus={i === 0}
            onChange={e => setValues(v => ({ ...v, [col]: e.target.value }))}
            onKeyDown={e => {
              if (e.key === 'Enter') handleSave()
              if (e.key === 'Escape') onCancel()
              if (e.key === 'Tab') {
                e.preventDefault()
                const next = e.shiftKey ? i - 1 : i + 1
                if (next >= 0 && next < columns.length) inputRefs.current[next]?.focus()
              }
            }}
          />
        </td>
      ))}
      <td className="px-3 py-1 whitespace-nowrap">
        <div className="flex gap-2">
          <button className="btn-primary text-xs" onClick={handleSave}>Add</button>
          <button className="btn-ghost text-xs" onClick={onCancel}>✕</button>
        </div>
      </td>
    </tr>
  )
}

// ─── Add column form ──────────────────────────────────────────────────────────

function AddColumnForm({ existingColumns, onSave, onCancel }) {
  const [name, setName] = useState('')
  const error = existingColumns.includes(name.trim()) ? 'Already exists' : ''

  return (
    <div className="flex items-center gap-2 px-4 py-3 border-t border-gray-800 bg-gray-900/60">
      <input
        className="input text-sm py-1 w-44 font-mono"
        placeholder="column_name"
        value={name}
        autoFocus
        onChange={e => setName(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' && !error && name.trim()) onSave(name.trim())
          if (e.key === 'Escape') onCancel()
        }}
      />
      {error && <span className="text-xs text-red-400">{error}</span>}
      <button
        className="btn-primary text-xs"
        disabled={!name.trim() || !!error}
        onClick={() => onSave(name.trim())}
      >
        Add Column
      </button>
      <button className="btn-ghost text-xs" onClick={onCancel}>Cancel</button>
    </div>
  )
}

// ─── Main table ───────────────────────────────────────────────────────────────

function DataTable({ columns, rows, onCellUpdate, onInsert, onDelete, onAddColumn }) {
  const [showNew, setShowNew] = useState(false)
  const [showAddCol, setShowAddCol] = useState(false)
  // editingCell: { rowId, colIdx } | null
  const [editingCell, setEditingCell] = useState(null)

  const startEdit = useCallback((rowId, colIdx) => {
    setEditingCell({ rowId, colIdx })
  }, [])

  const cancelEdit = useCallback(() => {
    setEditingCell(null)
  }, [])

  const handleTab = useCallback((rowId, colIdx, shiftKey) => {
    const numCols = columns.length
    const rowIdx = rows.findIndex(r => r.id === rowId)

    let nextColIdx = colIdx + (shiftKey ? -1 : 1)
    let nextRowIdx = rowIdx

    if (nextColIdx < 0) {
      nextRowIdx = rowIdx - 1
      nextColIdx = numCols - 1
    } else if (nextColIdx >= numCols) {
      nextRowIdx = rowIdx + 1
      nextColIdx = 0
    }

    if (nextRowIdx >= 0 && nextRowIdx < rows.length) {
      setEditingCell({ rowId: rows[nextRowIdx].id, colIdx: nextColIdx })
    } else {
      setEditingCell(null)
    }
  }, [columns.length, rows])

  return (
    <div className="card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900">
              {columns.map(col => (
                <th
                  key={col}
                  className="px-3 py-2 text-xs font-medium text-gray-500 uppercase tracking-wider whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
              <th className="px-3 py-2 w-28">
                <div className="flex gap-1">
                  <button className="btn-primary text-xs" onClick={() => { setShowNew(true); setEditingCell(null) }}>
                    + Row
                  </button>
                  <button className="btn-ghost text-xs" onClick={() => setShowAddCol(true)}>
                    + Col
                  </button>
                </div>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {showNew && (
              <NewRowForm
                columns={columns}
                onSave={data => { onInsert(data); setShowNew(false) }}
                onCancel={() => setShowNew(false)}
              />
            )}
            {rows.length === 0 && !showNew ? (
              <tr>
                <td colSpan={columns.length + 1} className="px-4 py-8 text-center text-sm text-gray-600">
                  No rows yet — click + Row to add one
                </td>
              </tr>
            ) : (
              rows.map(row => {
                const data = parseRow(row.row_data_json)
                return (
                  <tr
                    key={row.id}
                    className="hover:bg-gray-800/20 group"
                    onClick={() => { if (!editingCell) setEditingCell(null) }}
                  >
                    {columns.map((col, colIdx) => (
                      <EditableCell
                        key={col}
                        value={data[col]}
                        isEditing={editingCell?.rowId === row.id && editingCell?.colIdx === colIdx}
                        onStartEdit={() => startEdit(row.id, colIdx)}
                        onCancel={cancelEdit}
                        onCommit={val => {
                          const updated = { ...data, [col]: val }
                          onCellUpdate(row.id, updated)
                        }}
                        onTab={shiftKey => handleTab(row.id, colIdx, shiftKey)}
                      />
                    ))}
                    <td className="px-3 py-2">
                      <button
                        className="btn-ghost text-xs text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                        onClick={e => { e.stopPropagation(); onDelete(row) }}
                        title="Delete row"
                      >✕</button>
                    </td>
                  </tr>
                )
              })
            )}
          </tbody>
        </table>
      </div>

      {showAddCol && (
        <AddColumnForm
          existingColumns={columns}
          onSave={name => { onAddColumn(name); setShowAddCol(false) }}
          onCancel={() => setShowAddCol(false)}
        />
      )}

      <div className="px-4 py-2 border-t border-gray-800 text-xs text-gray-700">
        {rows.length} row{rows.length !== 1 ? 's' : ''} · {columns.length} col{columns.length !== 1 ? 's' : ''} · click to edit · Tab / Shift+Tab to move · Enter to confirm · Esc to cancel
      </div>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function TableDetail() {
  const { id } = useParams()
  const toast = useToast()
  const qc = useQueryClient()
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data: table } = useQuery({
    queryKey: ['tables', id],
    queryFn: () => getTable(id),
  })

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['table-rows', id],
    queryFn: () => listRows(id),
  })

  const columns = useMemo(
    () => deriveColumns(table?.schema_json ?? '{}', rows),
    [table?.schema_json, rows]
  )

  const insertMutation = useMutation({
    mutationFn: (data) => insertRow(id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['table-rows', id] }); toast.success('Row added') },
    onError: e => toast.error(e.message),
  })

  const updateMutation = useMutation({
    mutationFn: ({ rowId, data }) => updateRow(id, rowId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['table-rows', id] }),
    onError: e => toast.error(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (rowId) => deleteRow(id, rowId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['table-rows', id] })
      toast.success('Row deleted')
      setDeleteTarget(null)
    },
    onError: e => toast.error(e.message),
  })

  const addColumnMutation = useMutation({
    mutationFn: (colName) => {
      const currentCols = parseSchemaColumns(table?.schema_json ?? '{}')
      const newSchema = JSON.stringify({ columns: [...currentCols, colName] })
      return patchTable(id, { schema_json: newSchema })
    },
    onSuccess: (_, colName) => {
      qc.invalidateQueries({ queryKey: ['tables', id] })
      toast.success(`Column "${colName}" added`)
    },
    onError: e => toast.error(e.message),
  })

  return (
    <div className="space-y-4">
      <ToastContainer toasts={toast.toasts} />

      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-1">
            <Link to="/tables" className="hover:text-gray-300">Tables</Link>
            <span>/</span>
            <span className="text-gray-300">{table?.name ?? id}</span>
          </div>
          <h1 className="text-xl font-semibold text-white">{table?.name}</h1>
          <p className="text-xs text-gray-600 font-mono mt-0.5">{id}</p>
        </div>
      </div>

      {/* Column summary */}
      {columns.length > 0 && (
        <div className="card p-3 flex items-center gap-4 flex-wrap">
          <div>
            <div className="text-xs text-gray-600 mb-1">Columns</div>
            <div className="flex flex-wrap gap-1">
              {columns.map(c => (
                <span key={c} className="text-xs font-mono px-1.5 py-0.5 bg-gray-800 rounded text-gray-300">{c}</span>
              ))}
            </div>
          </div>
          {table?.scope && (
            <div className="ml-auto text-xs text-gray-600">{table.scope}</div>
          )}
        </div>
      )}

      {/* Script access hint */}
      <div className="text-xs text-gray-600 bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 font-mono">
        <span className="text-gray-500">from conduit import get_table  </span>
        <span className="text-gray-600">·  </span>
        tbl = get_table(<span className="text-brand-400">"{id}"</span>)
        <span className="text-gray-600">  ·  </span>
        tbl.get_rows()
        <span className="text-gray-600">  ·  </span>
        tbl.insert_row({'{'}<span className="text-amber-400">…</span>{'}'})
        <span className="text-gray-600">  ·  </span>
        tbl.delete_row(<span className="text-amber-400">row_id</span>)
      </div>

      {isLoading ? (
        <div className="text-sm text-gray-500 p-4">Loading rows…</div>
      ) : (
        <DataTable
          columns={columns}
          rows={rows}
          onCellUpdate={(rowId, data) => updateMutation.mutate({ rowId, data })}
          onInsert={(data) => insertMutation.mutate(data)}
          onDelete={setDeleteTarget}
          onAddColumn={(name) => addColumnMutation.mutate(name)}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        title="Delete row?"
        description="This row will be permanently removed."
        confirmLabel="Delete"
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  )
}
