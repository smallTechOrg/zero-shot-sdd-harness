'use client'

import type { RunStatus, RunSummary } from '../lib/types'

function relTime(iso: string): string {
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return ''
  const s = Math.max(0, Math.round((Date.now() - t) / 1000))
  if (s < 60) return 'just now'
  const m = Math.round(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.round(m / 60)
  if (h < 24) return `${h}h ago`
  return `${Math.round(h / 24)}d ago`
}

function fmtUsd(n: number | null): string {
  if (n == null) return ''
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(2)}`
}

function StatusDot({ status }: { status: RunStatus }) {
  const failed = status === 'failed'
  return (
    <span
      className={`h-2 w-2 shrink-0 rounded-full ${failed ? 'bg-red-500' : 'bg-green-500'}`}
      title={failed ? 'failed' : 'completed'}
      aria-label={failed ? 'failed' : 'completed'}
    />
  )
}

// Real, revisitable history of past questions. Clicking an item opens its saved
// answer; the detail view offers a re-run.
export default function HistoryPanel({
  items,
  onOpen,
}: {
  items: RunSummary[]
  onOpen: (item: RunSummary) => void
}) {
  return (
    <div
      data-testid="history-panel"
      className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">History</h3>

      {items.length === 0 ? (
        <p className="text-sm text-gray-400">Past questions appear here.</p>
      ) : (
        <ul className="space-y-1">
          {items.map(item => (
            <li key={item.run_id}>
              <button
                type="button"
                data-testid="history-item"
                onClick={() => onOpen(item)}
                className="w-full rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-gray-50"
              >
                <div className="flex items-center gap-2">
                  <StatusDot status={item.status} />
                  <span className="truncate text-sm font-medium text-gray-800">
                    {item.question}
                  </span>
                </div>
                <div className="mt-0.5 flex items-center gap-2 pl-4 text-[11px] text-gray-400">
                  <span>{relTime(item.created_at)}</span>
                  {item.cost_estimate_usd != null && (
                    <span>· {fmtUsd(item.cost_estimate_usd)} est.</span>
                  )}
                </div>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
