'use client'

import { useState } from 'react'
import { AnalysisResult } from '@/lib/api'
import dynamic from 'next/dynamic'

const PlotlyChart = dynamic(() => import('@/components/PlotlyChart'), { ssr: false })

const ROWS_PER_PAGE = 20

interface ResultsPanelProps {
  result: AnalysisResult | null
  isLoading?: boolean
  onRetry: () => void
}

export default function ResultsPanel({ result, isLoading, onRetry }: ResultsPanelProps) {
  const [page, setPage] = useState(0)

  // Loading skeleton — shown while analysis is running
  if (isLoading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6 space-y-3">
        <div className="animate-pulse bg-gray-200 rounded h-4 w-full" />
        <div className="animate-pulse bg-gray-200 rounded h-4 w-full" />
        <div className="animate-pulse bg-gray-200 rounded h-4 w-full" />
      </div>
    )
  }

  if (!result) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6 text-center">
        <p className="text-sm text-gray-400">No results yet — run an analysis to see results here.</p>
      </div>
    )
  }

  if (result.status === 'failed') {
    const errorMsg = result.error_message ?? result.error ?? 'An unknown error occurred.'
    return (
      <div className="rounded-xl border border-red-200 bg-red-50 shadow-sm p-6">
        <h2 className="text-lg font-semibold text-red-800 mb-2">Analysis Failed</h2>
        <p className="text-sm text-red-700 mb-4">{errorMsg}</p>
        <button
          onClick={onRetry}
          className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 transition-colors"
        >
          Try Again
        </button>
      </div>
    )
  }

  const table = result.table ?? []
  const totalPages = Math.ceil(table.length / ROWS_PER_PAGE)
  const pageRows = table.slice(page * ROWS_PER_PAGE, (page + 1) * ROWS_PER_PAGE)
  const tableKeys = table.length > 0 ? Object.keys(table[0]) : []

  return (
    <div className="space-y-6">
      {/* Summary card */}
      {result.summary && (
        <div className="rounded-xl border border-gray-200 bg-gray-50 shadow-sm p-5">
          <h2 className="text-base font-semibold text-gray-800 mb-2">Summary</h2>
          <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
            {result.summary}
          </p>
        </div>
      )}

      {/* Plotly chart */}
      {result.chart_json && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-4 overflow-hidden">
          <h2 className="text-base font-semibold text-gray-800 mb-3">Chart</h2>
          <PlotlyChart chartJson={result.chart_json} />
        </div>
      )}

      {/* Data table */}
      {table.length > 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-base font-semibold text-gray-800">Data Table</h2>
            <span className="text-xs text-gray-400">
              {table.length} row{table.length !== 1 ? 's' : ''}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {tableKeys.map((key) => (
                    <th
                      key={key}
                      className="px-4 py-2.5 font-medium text-gray-600 whitespace-nowrap"
                    >
                      {key}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {pageRows.map((row, i) => (
                  <tr key={i} className="hover:bg-gray-50 transition-colors">
                    {tableKeys.map((key) => {
                      const val = row[key]
                      const display =
                        typeof val === 'number'
                          ? Number.isInteger(val)
                            ? val.toLocaleString()
                            : val.toFixed(4)
                          : String(val ?? '')
                      return (
                        <td key={key} className="px-4 py-2.5 text-gray-700 whitespace-nowrap">
                          {display}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="px-5 py-3 border-t border-gray-200 flex items-center justify-between">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="rounded px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-300 hover:bg-gray-50 disabled:opacity-40 transition-colors"
              >
                Previous
              </button>
              <span className="text-xs text-gray-500">
                Page {page + 1} of {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page === totalPages - 1}
                className="rounded px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-300 hover:bg-gray-50 disabled:opacity-40 transition-colors"
              >
                Next
              </button>
            </div>
          )}
        </div>
      )}

      {/* Pending state */}
      {result.status === 'pending' && !result.summary && !result.chart_json && table.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-6 text-center">
          <p className="text-sm text-gray-400">Analysis is pending…</p>
        </div>
      )}
    </div>
  )
}
