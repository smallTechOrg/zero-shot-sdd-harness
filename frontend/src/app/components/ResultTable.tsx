import type { ColumnRows } from '../lib/api'

function cell(v: unknown): string {
  if (v === null || v === undefined) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

export default function ResultTable({ result }: { result: ColumnRows }) {
  if (!result || !result.columns || result.columns.length === 0) return null
  const rows = result.rows ?? []
  return (
    <div className="mt-3 max-h-80 overflow-auto rounded-lg border border-gray-200">
      <table className="min-w-full border-collapse text-sm">
        <thead className="sticky top-0 bg-gray-50">
          <tr>
            {result.columns.map((c, i) => (
              <th
                key={i}
                className="whitespace-nowrap border-b border-gray-200 px-3 py-2 text-left font-semibold text-gray-700"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={result.columns.length}
                className="px-3 py-4 text-center text-gray-400"
              >
                No rows returned.
              </td>
            </tr>
          ) : (
            rows.map((row, ri) => (
              <tr key={ri} className="even:bg-gray-50/50">
                {result.columns.map((_, ci) => (
                  <td
                    key={ci}
                    className="whitespace-nowrap border-b border-gray-100 px-3 py-2 text-gray-800"
                  >
                    {cell((row as unknown[])[ci])}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
