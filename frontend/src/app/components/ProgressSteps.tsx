'use client'

import type { ProgressEvent } from '../lib/types'

// Live step-by-step progress for a running question, driven by the SSE stream.
// Renders each received step, lighting up the current one with a spinner and
// marking completed steps with a check (or a retry glyph for "Retrying…").
export default function ProgressSteps({
  events,
  done,
}: {
  events: ProgressEvent[]
  done: boolean
}) {
  // The terminal frame ("done") is not a visible step.
  const steps = events.filter(e => e.step !== 'done')
  // Show an initial "Planning…" placeholder so the panel is never empty while
  // the first SSE frame is still in flight.
  const display: ProgressEvent[] = steps.length > 0 ? steps : [{ step: 'Planning…' }]

  return (
    <div
      data-testid="progress-steps"
      className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-gray-500">
        Working on it
      </p>
      <ol className="space-y-2.5">
        {display.map((e, i) => {
          const isLast = i === display.length - 1
          const active = isLast && !done
          const isRetry = /retry/i.test(e.step)
          return (
            <li
              key={i}
              data-testid="progress-step"
              className={`flex items-center gap-2.5 text-sm ${
                active ? 'text-gray-900' : 'text-gray-600'
              }`}
            >
              {active ? (
                <span
                  className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600"
                  aria-label="in progress"
                />
              ) : (
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white ${
                    isRetry ? 'bg-amber-500' : 'bg-green-600'
                  }`}
                  aria-hidden
                >
                  {isRetry ? '↻' : '✓'}
                </span>
              )}
              <span className={`font-medium ${isRetry ? 'text-amber-700' : ''}`}>{e.step}</span>
              {e.detail && <span className="truncate text-gray-400">— {e.detail}</span>}
            </li>
          )
        })}
      </ol>
    </div>
  )
}
