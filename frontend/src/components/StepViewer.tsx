'use client'

import type { StepEvent } from '@/lib/api'

interface Props {
  steps: StepEvent[]
  maxSteps: number | null
  running: boolean
}

const STATUS_STYLES: Record<string, string> = {
  worked: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
  tried: 'bg-amber-50 text-amber-700 border-amber-200',
}

const NODE_LABELS: Record<string, string> = {
  plan: 'Plan',
  generate_code: 'Write code',
  execute: 'Run code',
  inspect: 'Inspect',
  refine: 'Refine',
  profile: 'Profile',
  clarify: 'Clarify',
  finalize: 'Finalize',
}

export default function StepViewer({ steps, maxSteps, running }: Props) {
  if (steps.length === 0 && !running) return null

  const last = steps[steps.length - 1]
  const total = last?.total ?? maxSteps ?? 6
  const current = last?.step_index ?? 0

  return (
    <section
      data-testid="step-viewer"
      className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-700">
          {running && (
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
          )}
          Live reasoning
        </h3>
        <span
          data-testid="step-counter"
          className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-700"
        >
          Step {current} of {total}
        </span>
      </div>

      <ol className="space-y-2">
        {steps.map((s, i) => (
          <li
            key={i}
            data-testid="step-item"
            className="rounded-lg border border-slate-200 bg-white px-3 py-2.5"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-800">
                <span className="mr-2 text-xs text-slate-400">{s.step_index}.</span>
                {NODE_LABELS[s.node] ?? s.node}
              </span>
              <span
                className={`rounded-full border px-2 py-0.5 text-[11px] font-medium ${
                  STATUS_STYLES[s.status] ?? 'border-slate-200 bg-slate-50 text-slate-600'
                }`}
              >
                {s.status}
              </span>
            </div>
            {s.detail && <p className="mt-1 text-xs text-slate-600">{s.detail}</p>}
            {s.result_summary && (
              <p className="mt-1 text-xs text-slate-500">→ {s.result_summary}</p>
            )}
            {s.code && (
              <pre className="mt-2 overflow-x-auto rounded bg-slate-900 px-3 py-2 text-[11px] leading-relaxed text-slate-100">
                <code>{s.code}</code>
              </pre>
            )}
          </li>
        ))}
        {running && (
          <li className="flex items-center gap-2 px-3 py-2 text-xs text-slate-500">
            <span className="inline-block h-1.5 w-1.5 animate-bounce rounded-full bg-slate-400" />
            thinking…
          </li>
        )}
      </ol>
    </section>
  )
}
