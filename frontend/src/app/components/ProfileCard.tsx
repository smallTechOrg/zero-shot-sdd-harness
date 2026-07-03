'use client'

import type { Dataset } from '../lib/types'

function fmt(n: number): string {
  return n.toLocaleString('en-US')
}

export default function ProfileCard({ dataset }: { dataset: Dataset }) {
  const { name, row_count, column_count, file_format, profile } = dataset
  const columns = profile?.columns ?? []
  const sampleRows = profile?.sample_rows ?? []
  const sampleCols = columns.map(c => c.name)

  return (
    <div
      data-testid="profile-card"
      className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-gray-900" data-testid="dataset-name">
          {name}
        </h2>
        <span className="rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide text-gray-600">
          {file_format}
        </span>
      </div>

      <div className="mt-1 text-sm text-gray-600" data-testid="dataset-stats">
        <span className="font-medium text-gray-900">{fmt(row_count)}</span> rows ·{' '}
        <span className="font-medium text-gray-900">{fmt(column_count)}</span> columns
      </div>

      {profile?.quality_flags?.length > 0 && (
        <ul className="mt-3 space-y-1" data-testid="quality-flags">
          {profile.quality_flags.map((flag, i) => (
            <li
              key={i}
              className="inline-block rounded-md bg-amber-50 px-2 py-1 text-xs text-amber-800"
            >
              ⚠ {flag}
            </li>
          ))}
        </ul>
      )}

      {/* Columns table */}
      <div className="mt-4 overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4 font-medium">Column</th>
              <th className="py-2 pr-4 font-medium">Type</th>
              <th className="py-2 pr-4 font-medium">Nulls</th>
              <th className="py-2 font-medium">Sample values</th>
            </tr>
          </thead>
          <tbody>
            {columns.map(col => {
              const pct = row_count > 0 ? (col.null_count / row_count) * 100 : 0
              return (
                <tr key={col.name} className="border-b border-gray-100 last:border-0">
                  <td className="py-2 pr-4 font-medium text-gray-900">{col.name}</td>
                  <td className="py-2 pr-4">
                    <code className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700">
                      {col.dtype}
                    </code>
                  </td>
                  <td className="py-2 pr-4 text-gray-600">
                    {col.null_count === 0 ? (
                      <span className="text-green-600">0</span>
                    ) : (
                      <span className={pct > 20 ? 'text-red-600' : 'text-amber-600'}>
                        {fmt(col.null_count)} ({pct.toFixed(pct < 1 ? 2 : 0)}%)
                      </span>
                    )}
                  </td>
                  <td className="py-2 text-gray-500">
                    {(col.sample_values ?? []).slice(0, 3).map(String).join(', ')}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Sample rows preview */}
      {sampleRows.length > 0 && (
        <div className="mt-5">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500">
            Sample rows
          </p>
          <div className="overflow-x-auto rounded-lg border border-gray-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50">
                <tr>
                  {sampleCols.map(c => (
                    <th key={c} className="whitespace-nowrap px-3 py-2 font-medium text-gray-600">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sampleRows.slice(0, 5).map((row, i) => (
                  <tr key={i} className="border-t border-gray-100">
                    {sampleCols.map(c => (
                      <td key={c} className="whitespace-nowrap px-3 py-2 text-gray-700">
                        {row[c] === null || row[c] === undefined ? '—' : String(row[c])}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
