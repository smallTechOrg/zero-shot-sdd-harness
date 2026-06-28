'use client'

import { useEffect, useState } from 'react'
import { fetchRunDetail, fetchRuns, type RunDetail, type RunSummary } from '@/lib/api'
import AnswerCard from './AnswerCard'

interface Props {
  datasetId: string
  open: boolean
  onClose: () => void
  refreshKey: number
}

export default function HistoryDrawer({ datasetId, open, onClose, refreshKey }: Props) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    setLoading(true)
    setError(null)
    fetchRuns(datasetId)
      .then(r => {
        if (!cancelled) setRuns(r)
      })
      .catch(e => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load history')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open, datasetId, refreshKey])

  async function openDetail(runId: string) {
    setDetailLoading(true)
    setDetail(null)
    try {
      setDetail(await fetchRunDetail(runId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load run')
    } finally {
      setDetailLoading(false)
    }
  }

  if (!open) return null

  return (
    <div className="fixed inset-0 z-40 flex justify-end" data-testid="history-drawer">
      <div className="absolute inset-0 bg-slate-900/30" onClick={onClose} aria-hidden />
      <aside className="relative z-50 flex h-full w-full max-w-md flex-col bg-white shadow-2xl">
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-slate-800">Run history</h2>
          <button
            onClick={detail ? () => setDetail(null) : onClose}
            className="text-xs text-slate-500 hover:text-slate-800"
          >
            {detail ? '← Back' : 'Close ✕'}
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {detail ? (
            detailLoading ? (
              <p className="text-sm text-slate-400">Loading run…</p>
            ) : (
              <div className="space-y-3">
                <p className="text-sm font-medium text-slate-800">{detail.question}</p>
                <AnswerCard
                  answer={{
                    prose: detail.prose ?? '',
                    chart: detail.chart ?? null,
                    table: detail.table ?? null,
                    code: detail.code ?? '',
                  }}
                  onFollowUp={() => {}}
                />
              </div>
            )
          ) : loading ? (
            <p className="text-sm text-slate-400">Loading history…</p>
          ) : runs.length === 0 ? (
            <p className="text-sm text-slate-400">No runs yet for this dataset.</p>
          ) : (
            <ul className="space-y-2">
              {runs.map(run => (
                <li key={run.run_id}>
                  <button
                    data-testid="history-item"
                    onClick={() => openDetail(run.run_id)}
                    className="w-full rounded-lg border border-slate-200 px-3 py-2.5 text-left hover:border-indigo-300 hover:bg-slate-50"
                  >
                    <p className="text-sm font-medium text-slate-800">{run.question}</p>
                    <p className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                      <StatusBadge status={run.status} />
                      <span>{run.step_count} steps</span>
                      <span>${run.cost_usd?.toFixed(4)}</span>
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const styles =
    status === 'completed'
      ? 'bg-emerald-50 text-emerald-700'
      : status === 'failed'
        ? 'bg-red-50 text-red-700'
        : 'bg-slate-100 text-slate-600'
  return <span className={`rounded-full px-1.5 py-0.5 ${styles}`}>{status}</span>
}
