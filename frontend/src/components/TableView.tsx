'use client'

interface TableViewProps {
  table: Record<string, unknown>[] | null
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export default function TableView({ table }: TableViewProps) {
  const rows = table ?? []
  const columns = rows.length > 0 ? Object.keys(rows[0]) : []

  return (
    <section
      aria-label="Summary table"
      data-testid="table-view"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Summary table</h2>
      {rows.length === 0 ? (
        <div className="flex h-24 items-center justify-center text-sm text-gray-400">
          No table for this result.
        </div>
      ) : (
        <div className="max-h-96 overflow-auto rounded-lg border border-gray-100">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="sticky top-0 bg-gray-50">
              <tr>
                {columns.map((col) => (
                  <th
                    key={col}
                    scope="col"
                    className="px-3 py-2 text-left font-semibold text-gray-700"
                  >
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row, i) => (
                <tr key={i} className="even:bg-gray-50/50">
                  {columns.map((col) => (
                    <td key={col} className="px-3 py-2 text-gray-700 tabular-nums">
                      {formatCell(row[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
