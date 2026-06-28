'use client'

import type { SummaryTable as SummaryTableData } from '../lib/api'

function fmtCell(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'number') return v.toLocaleString('en-US')
  return String(v)
}

export function SummaryTable({ table }: { table: SummaryTableData | null }) {
  if (!table || table.columns.length === 0) return null
  return (
    <div data-testid="summary-table" className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-gray-200 bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            {table.columns.map((c) => (
              <th key={c} className="px-3 py-2 font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, ri) => (
            <tr key={ri} className="border-b border-gray-100 last:border-0">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-gray-700">
                  {fmtCell(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
