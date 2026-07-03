'use client'

import type { RunResult } from '../lib/types'
import ChartView from './ChartView'
import CodePanel from './CodePanel'

export default function AnswerBlock({ run }: { run: RunResult }) {
  const failed = run.status === 'failed'
  const tableRows = run.table ?? []
  const tableCols = tableRows.length > 0 ? Object.keys(tableRows[0]) : []

  return (
    <div
      data-testid="answer-block"
      className={`space-y-5 rounded-2xl border p-6 shadow-sm ${
        failed ? 'border-red-200 bg-red-50/40' : 'border-gray-200 bg-white'
      }`}
    >
      {failed ? (
        <div
          role="alert"
          data-testid="answer-error"
          className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700"
        >
          <p className="font-semibold">The analysis couldn&apos;t complete.</p>
          <p className="mt-1">{run.error ?? 'The agent failed after several attempts.'}</p>
          <p className="mt-2 text-xs text-red-500">
            Attempts: {run.attempts}. Any generated code is shown below.
          </p>
        </div>
      ) : (
        <>
          {/* Prominent plain-language answer */}
          <p
            data-testid="answer-text"
            className="text-lg font-semibold leading-snug text-gray-900"
          >
            {run.answer_text}
          </p>

          {/* Key numbers */}
          {run.key_numbers && run.key_numbers.length > 0 && (
            <div className="flex flex-wrap gap-3" data-testid="key-numbers">
              {run.key_numbers.map((kn, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-gray-200 bg-gray-50 px-4 py-3"
                >
                  <div className="text-xs uppercase tracking-wide text-gray-500">{kn.label}</div>
                  <div className="text-xl font-bold text-gray-900">{String(kn.value)}</div>
                </div>
              ))}
            </div>
          )}

          {/* Narrative */}
          {run.narrative && (
            <p className="text-sm leading-relaxed text-gray-600" data-testid="narrative">
              {run.narrative}
            </p>
          )}

          {/* Chart */}
          {run.chart && <ChartView spec={run.chart} />}

          {/* Summary table */}
          {tableRows.length > 0 && (
            <div className="overflow-x-auto rounded-lg border border-gray-200" data-testid="summary-table">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    {tableCols.map(c => (
                      <th key={c} className="whitespace-nowrap px-3 py-2 font-medium text-gray-600">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableRows.slice(0, 50).map((row, i) => (
                    <tr key={i} className="border-t border-gray-100">
                      {tableCols.map(c => (
                        <td key={c} className="whitespace-nowrap px-3 py-2 text-gray-700">
                          {row[c] === null || row[c] === undefined ? '—' : String(row[c])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Code panel — shown for both success and failure when code exists */}
      <CodePanel code={run.code} />

      {/* Phase-2 stub: follow-up suggestions */}
      <div
        data-testid="stub-followups"
        className="rounded-lg border border-dashed border-gray-300 bg-gray-50 px-4 py-3 opacity-60"
      >
        <span className="mr-2 rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Coming soon · Phase 2
        </span>
        <span className="text-xs text-gray-500">Suggested follow-up questions</span>
      </div>
    </div>
  )
}
