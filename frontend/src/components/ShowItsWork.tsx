'use client'

import { useState } from 'react'
import type { AskResult, TraceStep } from '../lib/api'

function StepRow({ step }: { step: TraceStep }) {
  return (
    <li className="rounded-md border border-gray-100 bg-gray-50 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-2 text-sm font-medium text-gray-800">
          <span
            className={`inline-block h-2 w-2 rounded-full ${step.ok ? 'bg-green-500' : 'bg-red-500'}`}
            aria-hidden
          />
          {step.step}
          <span className={`text-xs font-normal ${step.ok ? 'text-green-700' : 'text-red-700'}`}>
            {step.ok ? 'ok' : 'failed'}
          </span>
        </span>
        {typeof step.latency_ms === 'number' && (
          <span className="text-xs text-gray-400">{step.latency_ms} ms</span>
        )}
      </div>
      {step.error && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-red-50 p-2 text-xs text-red-700">
          {step.error}
        </pre>
      )}
      {step.sql && (
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-gray-900 p-2 font-mono text-xs text-gray-100">
          {step.sql}
        </pre>
      )}
    </li>
  )
}

export function ShowItsWork({ result }: { result: AskResult }) {
  const [open, setOpen] = useState(false)

  return (
    <section data-testid="show-its-work" className="rounded-xl border border-gray-200 bg-white shadow-sm">
      <button
        type="button"
        data-testid="show-its-work-toggle"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-5 py-3 text-left text-sm font-semibold text-gray-800 hover:bg-gray-50"
      >
        <span>Show its work</span>
        <span className="flex items-center gap-3 text-xs font-normal text-gray-500">
          {typeof result.cost_usd === 'number' && (
            <span data-testid="cost-usd" className="rounded bg-gray-100 px-2 py-0.5 font-mono">
              ${result.cost_usd.toFixed(4)}
            </span>
          )}
          <svg
            className={`h-4 w-4 transition-transform ${open ? 'rotate-180' : ''}`}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 9l6 6 6-6" />
          </svg>
        </span>
      </button>

      {open && (
        <div data-testid="work-detail" className="space-y-4 border-t border-gray-100 px-5 py-4">
          {result.plan && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Plan</h4>
              <p className="text-sm text-gray-700">{result.plan}</p>
            </div>
          )}

          {result.trace && result.trace.length > 0 && (
            <div>
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Step trace</h4>
              <ul className="space-y-2">
                {result.trace.map((s, i) => (
                  <StepRow key={i} step={s} />
                ))}
              </ul>
            </div>
          )}

          {result.sql && (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">DuckDB SQL</h4>
              <pre
                data-testid="executed-sql"
                className="overflow-x-auto whitespace-pre-wrap rounded-lg bg-gray-900 p-3 font-mono text-xs text-gray-100"
              >
                {result.sql}
              </pre>
            </div>
          )}

          <div className="text-xs text-gray-400">
            Per-question cost shown above is real. The daily roll-up is a stub (coming soon).
          </div>
        </div>
      )}
    </section>
  )
}
