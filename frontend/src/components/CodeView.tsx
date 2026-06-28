'use client'

import { useState } from 'react'
import type { AnalysisStep } from '@/lib/api'

function StepResult({ result }: { result: unknown }) {
  if (result === null || result === undefined) return null
  const text = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
  return (
    <pre className="mt-1 overflow-x-auto rounded bg-gray-50 p-2 text-[11px] leading-relaxed text-gray-600">
      {text}
    </pre>
  )
}

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(code)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        } catch {
          /* clipboard unavailable */
        }
      }}
      className="rounded border border-gray-200 bg-white px-2 py-0.5 text-[11px] font-medium text-gray-500 hover:bg-gray-50"
    >
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

export default function CodeView({ steps }: { steps: AnalysisStep[] }) {
  if (!steps || steps.length === 0) return null
  return (
    <details className="rounded-lg border border-gray-200 bg-white" data-testid="code-view">
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
        Code <span className="text-gray-400">({steps.length} step{steps.length > 1 ? 's' : ''})</span>
      </summary>
      <div className="space-y-4 px-4 py-3">
        {steps.map(step => (
          <div key={step.step_index} className="text-sm">
            <div className="mb-1 flex items-center justify-between gap-2">
              <span className="text-xs font-semibold text-gray-500">
                Step {step.step_index + 1}
                <span className="ml-1.5 rounded bg-gray-100 px-1.5 py-0.5 font-mono text-[10px] uppercase text-gray-500">
                  {step.language}
                </span>
                {step.latency_ms != null && (
                  <span className="ml-1.5 text-gray-400">{step.latency_ms} ms</span>
                )}
              </span>
              <CopyButton code={step.code} />
            </div>
            <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 font-mono text-[12px] leading-relaxed text-gray-100">
              {step.code}
            </pre>
            {step.error ? (
              <p className="mt-1 rounded bg-red-50 px-2 py-1 text-[12px] text-red-700">
                {step.error}
              </p>
            ) : (
              <StepResult result={step.result} />
            )}
          </div>
        ))}
      </div>
    </details>
  )
}
