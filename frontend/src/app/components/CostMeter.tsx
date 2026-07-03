'use client'

function fmtTokens(n: number): string {
  return n.toLocaleString('en-US')
}

function fmtUsd(n: number | null): string {
  if (n == null) return '—'
  if (n === 0) return '$0.00'
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(2)}`
}

// Real per-question and running-session token/cost meter. All dollar figures are
// clearly labelled as estimates.
export default function CostMeter({
  lastTokens,
  lastCost,
  totalTokens,
  totalCost,
  count,
}: {
  lastTokens: number | null
  lastCost: number | null
  totalTokens: number
  totalCost: number
  count: number
}) {
  return (
    <div
      data-testid="cost-meter"
      className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm"
    >
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Cost meter
      </h3>

      {count === 0 ? (
        <p className="text-sm text-gray-400">No questions yet.</p>
      ) : (
        <div className="space-y-2 text-sm">
          <div className="flex items-baseline justify-between gap-2">
            <span className="text-gray-500">Last question</span>
            <span className="font-mono text-gray-900">
              {lastTokens != null ? fmtTokens(lastTokens) : '—'} tok · {fmtUsd(lastCost)}
            </span>
          </div>
          <div
            data-testid="cost-session-total"
            className="flex items-baseline justify-between gap-2 border-t border-gray-100 pt-2"
          >
            <span className="font-medium text-gray-700">Session total</span>
            <span className="font-mono font-semibold text-gray-900">
              {fmtTokens(totalTokens)} tok · {fmtUsd(totalCost)}
            </span>
          </div>
        </div>
      )}

      <p className="mt-2 text-[11px] leading-snug text-gray-400">
        Dollar figures are estimates — actual billing may vary.
      </p>
    </div>
  )
}
