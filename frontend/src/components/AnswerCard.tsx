'use client'

import { StubBadge } from './StubBadge'

export interface AnalysisResult {
  run_id: string
  answer: string
  chart_base64: string | null
  chart_type: string | null
  executed_code: string | null
  node_trace: Array<{ node: string; duration_ms: number }>
  tokens_in: number | null
  tokens_out: number | null
  cost_usd: number | null
  latency_ms: number | null
}

interface AnswerCardProps {
  question: string
  result: AnalysisResult | null
  loading: boolean
  error: string | null
}

export function AnswerCard({ question, result, loading, error }: AnswerCardProps) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      {/* Question header */}
      <div className="px-4 py-3 bg-gray-50 border-b border-gray-200">
        <p className="text-sm font-medium text-gray-700">{question}</p>
      </div>

      {/* Loading state */}
      {loading && (
        <div className="px-4 py-6 flex items-center gap-3 text-gray-400">
          <svg
            className="animate-spin h-4 w-4 text-indigo-500"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="text-sm">Thinking&hellip;</span>
        </div>
      )}

      {/* Error state */}
      {!loading && error && (
        <div className="px-4 py-4 bg-amber-50 border-l-4 border-amber-400">
          <p className="text-sm font-medium text-amber-800 mb-1">Request failed</p>
          <p className="text-sm text-amber-700">{error}</p>
        </div>
      )}

      {/* Answer content */}
      {!loading && !error && result && (
        <div className="divide-y divide-gray-100">
          {/* Answer text */}
          <div className="px-4 py-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">Answer</p>
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{result.answer}</p>
          </div>

          {/* Chart stub — Phase 2 */}
          <div className="px-4 py-4 bg-gray-50">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Charts</p>
              <StubBadge label="Phase 2" />
            </div>
            <div className="rounded-lg border border-dashed border-gray-200 bg-white px-4 py-6 flex items-center justify-center">
              <p className="text-sm italic text-gray-400">Charts — coming in Phase 2</p>
            </div>
          </div>

          {/* Executed code stub — Phase 2 */}
          <div className="px-4 py-4 bg-gray-50">
            <div className="flex items-center gap-2 mb-2">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">Executed code</p>
              <StubBadge label="Phase 2" />
            </div>
            <div className="rounded-lg border border-dashed border-gray-200 bg-white px-4 py-6 flex items-center justify-center">
              <p className="text-sm italic text-gray-400">Executed code — coming in Phase 2</p>
            </div>
          </div>

          {/* Latency/cost metadata */}
          {(result.latency_ms != null || result.cost_usd != null) && (
            <div className="px-4 py-3 bg-gray-50 flex items-center gap-4 text-xs text-gray-400">
              {result.latency_ms != null && (
                <span>{(result.latency_ms / 1000).toFixed(2)}s</span>
              )}
              {result.tokens_in != null && result.tokens_out != null && (
                <span>{result.tokens_in + result.tokens_out} tokens</span>
              )}
              {result.cost_usd != null && (
                <span>${result.cost_usd.toFixed(5)}</span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
