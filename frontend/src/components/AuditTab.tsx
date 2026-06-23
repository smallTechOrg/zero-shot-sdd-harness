'use client'

import { useState, useEffect, useCallback } from 'react'
import { getAudit } from '../lib/api'
import type { AuditEntry } from '../types'

interface Props {
  sessionId: string
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function truncate(str: string | null | undefined, max: number): string {
  if (!str) return '—'
  if (str.length <= max) return str
  return str.slice(0, max) + '…'
}

export default function AuditTab({ sessionId }: Props) {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchAudit = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAudit(sessionId)
      setEntries(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load audit log')
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchAudit()
  }, [fetchAudit])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 shrink-0">
        <h2 className="text-sm font-semibold text-gray-700">Audit Log</h2>
        <button
          onClick={fetchAudit}
          disabled={loading}
          className="text-xs font-medium text-blue-600 hover:text-blue-800 border border-blue-200 rounded px-2 py-1 disabled:opacity-50"
        >
          {loading ? 'Loading…' : 'Reload'}
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading && (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3 text-gray-400">
              <div className="w-7 h-7 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin" />
              <p className="text-sm">Loading audit log…</p>
            </div>
          </div>
        )}

        {!loading && error && (
          <div className="m-4 rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && entries.length === 0 && (
          <div className="flex items-center justify-center h-full text-gray-400 text-sm">
            No audit entries yet. Run a query to see results here.
          </div>
        )}

        {!loading && !error && entries.length > 0 && (
          <table className="min-w-full text-xs">
            <thead className="bg-gray-50 border-b border-gray-200 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-gray-600 whitespace-nowrap">
                  Timestamp
                </th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600 whitespace-nowrap">
                  Dataset
                </th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">Question</th>
                <th className="px-3 py-2 text-right font-semibold text-gray-600 whitespace-nowrap">
                  Rows
                </th>
                <th className="px-3 py-2 text-right font-semibold text-gray-600 whitespace-nowrap">
                  Duration
                </th>
                <th className="px-3 py-2 text-left font-semibold text-gray-600">Error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {entries.map((entry, i) => (
                <tr key={entry.id} className={i % 2 === 1 ? 'bg-gray-50' : 'bg-white'}>
                  <td className="px-3 py-2 text-gray-600 whitespace-nowrap">
                    {formatDate(entry.created_at)}
                  </td>
                  <td className="px-3 py-2 text-gray-700 font-mono whitespace-nowrap max-w-[140px]">
                    <span title={entry.dataset_table}>{truncate(entry.dataset_table, 20)}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-700 max-w-[220px]">
                    <span title={entry.question}>{truncate(entry.question, 60)}</span>
                  </td>
                  <td className="px-3 py-2 text-gray-600 text-right font-mono">
                    {entry.row_count ?? '—'}
                  </td>
                  <td className="px-3 py-2 text-gray-600 text-right font-mono whitespace-nowrap">
                    {entry.duration_ms != null ? `${entry.duration_ms} ms` : '—'}
                  </td>
                  <td className="px-3 py-2 max-w-[180px]">
                    {entry.error ? (
                      <span
                        className="text-red-600"
                        title={entry.error}
                      >
                        {truncate(entry.error, 40)}
                      </span>
                    ) : (
                      <span className="text-green-600">OK</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
