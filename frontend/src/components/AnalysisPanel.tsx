'use client'

import { useState } from 'react'
import { runAnalysis, UploadResult, AnalysisResult } from '@/lib/api'

interface AnalysisOption {
  value: string
  label: string
  disabled: boolean
  stub?: string
}

const ANALYSIS_OPTIONS: AnalysisOption[] = [
  { value: 'summary_stats', label: 'Summary Statistics', disabled: false },
  {
    value: 'trend_over_time',
    label: 'Trend Over Time',
    disabled: true,
    stub: 'Coming in Phase 2',
  },
  {
    value: 'top_bottom_n',
    label: 'Top / Bottom N',
    disabled: true,
    stub: 'Coming in Phase 2',
  },
  {
    value: 'correlation',
    label: 'Correlation',
    disabled: true,
    stub: 'Coming in Phase 2',
  },
  {
    value: 'nl_query',
    label: 'Ask a Question',
    disabled: true,
    stub: 'Coming in Phase 3',
  },
]

interface AnalysisPanelProps {
  activeUpload: UploadResult
  onAnalysisResult: (result: AnalysisResult) => void
  onRunningChange?: (isRunning: boolean) => void
}

export default function AnalysisPanel({ activeUpload, onAnalysisResult, onRunningChange }: AnalysisPanelProps) {
  const [analysisType, setAnalysisType] = useState('summary_stats')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function setRunningWithCallback(value: boolean) {
    setRunning(value)
    onRunningChange?.(value)
  }

  async function handleRunAnalysis() {
    setRunningWithCallback(true)
    setError(null)
    try {
      const result = await runAnalysis(activeUpload.upload_id, analysisType, {})
      onAnalysisResult(result)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Analysis failed. Please try again.'
      setError(message)
    } finally {
      setRunningWithCallback(false)
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6">
      <h2 className="text-lg font-semibold text-gray-800 mb-4">Run Analysis</h2>

      <div className="mb-1">
        <p className="text-sm text-gray-500 mb-1">
          File:{' '}
          <span className="font-medium text-gray-700">{activeUpload.filename}</span>
          <span className="text-gray-400 ml-2">
            ({activeUpload.row_count.toLocaleString()} rows, {activeUpload.col_count} cols)
          </span>
        </p>
      </div>

      <div className="mt-4">
        <label htmlFor="analysis-type" className="block text-sm font-medium text-gray-700 mb-2">
          Analysis Type
        </label>
        <select
          id="analysis-type"
          value={analysisType}
          onChange={(e) => setAnalysisType(e.target.value)}
          disabled={running}
          className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 bg-white"
        >
          {ANALYSIS_OPTIONS.map((opt) => (
            <option
              key={opt.value}
              value={opt.value}
              disabled={opt.disabled}
              className={opt.disabled ? 'text-gray-400 italic' : 'text-gray-900'}
            >
              {opt.disabled
                ? `${opt.label} — ${opt.stub}`
                : opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Stub notice for disabled options */}
      {analysisType !== 'summary_stats' && (
        <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          This analysis type is not yet available. Select &quot;Summary Statistics&quot; to run an analysis now.
        </div>
      )}

      {error && (
        <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-5">
        <button
          onClick={handleRunAnalysis}
          disabled={running || analysisType !== 'summary_stats'}
          className="rounded-lg bg-blue-600 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {running ? (
            <span className="flex items-center gap-2">
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
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
              Running…
            </span>
          ) : (
            'Run Analysis'
          )}
        </button>
      </div>

      {/* Stub legend */}
      <div className="mt-6 pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-400 italic">
          Options marked &quot;Coming in Phase 2 / 3&quot; are non-functional stubs — they will be enabled in future phases.
        </p>
      </div>
    </div>
  )
}
