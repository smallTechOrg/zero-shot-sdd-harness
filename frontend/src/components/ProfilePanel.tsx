'use client'

import { useState } from 'react'
import type { Dataset } from '@/lib/api'

interface Props {
  dataset: Dataset
}

export default function ProfilePanel({ dataset }: Props) {
  const [open, setOpen] = useState(true)
  const { profile } = dataset

  return (
    <section
      data-testid="profile-panel"
      className="rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <button
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div>
          <h2 className="text-sm font-semibold text-slate-800">
            {dataset.name}
            <span className="ml-2 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
              profiled
            </span>
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            {dataset.row_count.toLocaleString()} rows · {dataset.col_count} columns
          </p>
        </div>
        <span className="text-slate-400">{open ? '▾' : '▸'}</span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-5 py-4">
          {profile.quality_flags?.length > 0 && (
            <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
              <p className="text-xs font-semibold text-amber-800">Data-quality flags</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-amber-700">
                {profile.quality_flags.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500">
                  <th className="py-2 pr-3 font-medium">Column</th>
                  <th className="py-2 pr-3 font-medium">Type</th>
                  <th className="py-2 pr-3 font-medium">Unique</th>
                  <th className="py-2 pr-3 font-medium">Nulls</th>
                  <th className="py-2 font-medium">Range</th>
                </tr>
              </thead>
              <tbody>
                {profile.columns.map(col => {
                  const range = profile.ranges?.[col.name]
                  return (
                    <tr key={col.name} className="border-b border-slate-50">
                      <td className="py-2 pr-3 font-medium text-slate-800">{col.name}</td>
                      <td className="py-2 pr-3">
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-600">
                          {col.dtype}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-slate-600">{col.n_unique?.toLocaleString()}</td>
                      <td className="py-2 pr-3 text-slate-600">
                        {col.n_null > 0 ? (
                          <span className="text-amber-600">{col.n_null.toLocaleString()}</span>
                        ) : (
                          '0'
                        )}
                      </td>
                      <td className="py-2 text-slate-500">
                        {range ? `${fmt(range.min)} – ${fmt(range.max)}` : '—'}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  )
}

function fmt(v: number): string {
  if (typeof v !== 'number' || Number.isNaN(v)) return String(v)
  return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 2 })
}
