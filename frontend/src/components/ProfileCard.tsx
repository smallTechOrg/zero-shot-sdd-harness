'use client'

import type { Dataset } from '../lib/api'

function fmtNum(n: number): string {
  return n.toLocaleString('en-US')
}

function rangeText(col: { min?: number | string | null; max?: number | string | null }): string | null {
  if (col.min === undefined && col.max === undefined) return null
  if (col.min === null && col.max === null) return null
  if (col.min === undefined || col.min === null) return null
  const min = typeof col.min === 'number' ? col.min.toLocaleString('en-US') : String(col.min)
  const max = typeof col.max === 'number' ? col.max.toLocaleString('en-US') : String(col.max)
  return `${min} – ${max}`
}

export function ProfileCard({ dataset }: { dataset: Dataset }) {
  const profile = dataset.profile
  return (
    <section data-testid="profile-card" className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold text-gray-900">
          Profile · <span className="font-normal text-gray-500">{dataset.name}</span>
        </h2>
        <span className="rounded-md bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
          {fmtNum(profile.row_count)} rows · {profile.columns.length} columns
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-xs uppercase tracking-wide text-gray-500">
              <th className="py-2 pr-4 font-medium">Column</th>
              <th className="py-2 pr-4 font-medium">Type</th>
              <th className="py-2 pr-4 font-medium">Nulls</th>
              <th className="py-2 pr-4 font-medium">Distinct</th>
              <th className="py-2 font-medium">Range</th>
            </tr>
          </thead>
          <tbody>
            {profile.columns.map((col) => {
              const range = rangeText(col)
              return (
                <tr key={col.name} className="border-b border-gray-100 last:border-0">
                  <td className="py-2 pr-4 font-medium text-gray-900">{col.name}</td>
                  <td className="py-2 pr-4">
                    <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-xs text-gray-600">
                      {col.type}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-gray-600">{col.nulls ?? '—'}</td>
                  <td className="py-2 pr-4 text-gray-600">{col.distinct ?? '—'}</td>
                  <td className="py-2 text-gray-600">{range ?? '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
