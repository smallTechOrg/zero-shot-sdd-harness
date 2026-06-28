'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import type { AnswerPayload } from '@/lib/api'

// Recharts is heavy + relies on browser layout; load it client-only.
const AnswerChart = dynamic(() => import('./AnswerChart'), {
  ssr: false,
  loading: () => (
    <div className="flex h-72 items-center justify-center text-xs text-slate-400">
      rendering chart…
    </div>
  ),
})

interface Props {
  answer: AnswerPayload
  onFollowUp: (q: string) => void
}

export default function AnswerCard({ answer, onFollowUp }: Props) {
  const [showCode, setShowCode] = useState(false)

  const isClarification = answer.status === 'needs_clarification' || !!answer.clarifying_question

  if (isClarification) {
    return (
      <section
        data-testid="answer-card"
        className="rounded-2xl border border-sky-200 bg-sky-50 p-5 shadow-sm"
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-sky-600">
          Needs clarification
        </p>
        <p className="mt-2 text-sm text-slate-800">
          {answer.clarifying_question ?? answer.prose}
        </p>
        <p className="mt-2 text-xs text-slate-500">Reply below as a new question to continue.</p>
      </section>
    )
  }

  const table = answer.table
  const hasTable = !!table && table.columns?.length > 0

  return (
    <section
      data-testid="answer-card"
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="grid gap-6 p-5 lg:grid-cols-2">
        {/* Prose + table */}
        <div className="space-y-4">
          <p
            data-testid="answer-prose"
            className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800"
          >
            {answer.prose}
          </p>

          {answer.uncertainty && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
              <span className="font-semibold">Note:</span> {answer.uncertainty}
            </div>
          )}

          {hasTable && (
            <div
              data-testid="answer-table"
              className="max-h-64 overflow-auto rounded-lg border border-slate-200"
            >
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-slate-50">
                  <tr className="border-b border-slate-200 text-slate-500">
                    {table!.columns.map(c => (
                      <th key={c} className="px-3 py-2 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table!.rows.map((row, ri) => (
                    <tr key={ri} className="border-b border-slate-50">
                      {row.map((cell, ci) => (
                        <td key={ci} className="px-3 py-1.5 text-slate-700">
                          {formatCell(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Chart */}
        <div className="flex flex-col">
          {answer.chart ? (
            <AnswerChart chart={answer.chart} />
          ) : (
            <div className="flex h-72 items-center justify-center rounded-lg border border-dashed border-slate-200 text-xs text-slate-400">
              No chart for this answer
            </div>
          )}
        </div>
      </div>

      {/* Show code */}
      {answer.code && (
        <div className="border-t border-slate-100">
          <button
            data-testid="toggle-code"
            onClick={() => setShowCode(s => !s)}
            className="flex w-full items-center justify-between px-5 py-3 text-left text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            <span>{showCode ? '▾' : '▸'} Show code (exact pandas run server-side)</span>
          </button>
          {showCode && (
            <pre
              data-testid="answer-code"
              className="overflow-x-auto bg-slate-900 px-5 py-4 text-xs leading-relaxed text-slate-100"
            >
              <code>{answer.code}</code>
            </pre>
          )}
        </div>
      )}

      {/* Cost line */}
      <div
        data-testid="answer-cost"
        className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-100 bg-slate-50/60 px-5 py-2.5 text-[11px] text-slate-500"
      >
        {answer.tokens && (
          <span>
            {(answer.tokens.prompt + answer.tokens.completion).toLocaleString()} tokens
            <span className="text-slate-400">
              {' '}
              ({answer.tokens.prompt} in / {answer.tokens.completion} out)
            </span>
          </span>
        )}
        {answer.cost_usd != null && <span>${answer.cost_usd.toFixed(4)} this question</span>}
        {answer.daily_total_usd != null && (
          <span className="ml-auto font-medium text-slate-600">
            ${answer.daily_total_usd.toFixed(4)} today
          </span>
        )}
      </div>

      {/* Suggested follow-ups */}
      {answer.follow_ups && answer.follow_ups.length > 0 && (
        <div className="flex flex-wrap gap-2 border-t border-slate-100 px-5 py-3">
          <span className="self-center text-xs text-slate-400">Try next:</span>
          {answer.follow_ups.slice(0, 3).map((q, i) => (
            <button
              key={i}
              data-testid="follow-up"
              onClick={() => onFollowUp(q)}
              className="rounded-full border border-indigo-200 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </section>
  )
}

function formatCell(cell: unknown): string {
  if (cell == null) return '—'
  if (typeof cell === 'number') {
    return Number.isInteger(cell)
      ? cell.toLocaleString()
      : cell.toLocaleString(undefined, { maximumFractionDigits: 4 })
  }
  return String(cell)
}
