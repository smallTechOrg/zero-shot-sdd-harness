'use client'

import type { AskResult } from '../lib/api'
import { Chart } from './Chart'
import { ShowItsWork } from './ShowItsWork'
import { SummaryTable } from './SummaryTable'

export function AnswerPanel({ result }: { result: AskResult }) {
  const failed = result.status === 'failed'

  return (
    <div data-testid="answer-panel" className="space-y-4">
      {failed ? (
        // FAILURE is an error (red + distinct), NOT a greyed stub. Show-its-work
        // stays available below so the user sees what was tried.
        <section
          data-testid="answer-failed"
          role="alert"
          className="rounded-xl border border-red-300 bg-red-50 p-5 shadow-sm"
        >
          <h2 className="text-sm font-semibold text-red-800">Couldn’t answer that one</h2>
          <p className="mt-2 text-sm text-red-700">
            {result.error_message ?? 'The agent could not complete this question.'}
          </p>
          <p className="mt-2 text-xs text-red-600">
            Expand “Show its work” below to see what was tried.
          </p>
        </section>
      ) : (
        <section data-testid="answer-success" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-900">Answer</h2>
          <p className="mt-2 text-base leading-relaxed text-gray-800">{result.answer}</p>

          {result.key_numbers && result.key_numbers.length > 0 && (
            <div data-testid="key-numbers" className="mt-4 flex flex-wrap gap-3">
              {result.key_numbers.map((kn, i) => (
                <div key={i} className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-2">
                  <div className="text-xs font-medium uppercase tracking-wide text-blue-600">{kn.label}</div>
                  <div className="text-lg font-bold text-blue-900">{String(kn.value)}</div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-5 space-y-4">
            <Chart chart={result.chart} />
            <SummaryTable table={result.table} />
          </div>
        </section>
      )}

      <ShowItsWork result={result} />
    </div>
  )
}
