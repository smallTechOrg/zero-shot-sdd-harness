'use client'

import dynamic from 'next/dynamic'

const PlotlyChart = dynamic(() => import('./PlotlyChart'), { ssr: false })

interface AnalysisResultProps {
  answer: string | null
  chartJson: string | null
  error: string | null
  onReset?: () => void
}

export default function AnalysisResult({ answer, chartJson, error, onReset }: AnalysisResultProps) {
  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Analysis failed</p>
          <p className="mt-1 text-sm text-red-600">{error}</p>
          {onReset && (
            <button
              onClick={onReset}
              className="mt-3 rounded-md bg-red-100 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-200"
            >
              Try again
            </button>
          )}
        </div>
      )}

      {answer && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-gray-800 whitespace-pre-wrap leading-relaxed">
          {answer}
        </div>
      )}

      {chartJson && (
        <div className="rounded-lg border border-gray-200 bg-white p-2 shadow-sm">
          <PlotlyChart chartJson={chartJson} />
        </div>
      )}
    </div>
  )
}
