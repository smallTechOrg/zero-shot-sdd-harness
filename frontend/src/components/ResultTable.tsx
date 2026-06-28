import type { ResultTable as ResultTableData } from '@/lib/api'

export default function ResultTable({ table }: { table: ResultTableData | null }) {
  if (!table || table.columns.length === 0) return null

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200" data-testid="result-table">
      <table className="min-w-full divide-y divide-gray-200 text-sm">
        <thead className="bg-gray-50">
          <tr>
            {table.columns.map(col => (
              <th
                key={col}
                className="px-3 py-2 text-left font-semibold text-gray-700 whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {table.rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-gray-50">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-2 text-gray-700 whitespace-nowrap">
                  {cell === null || cell === undefined ? (
                    <span className="text-gray-300">—</span>
                  ) : (
                    String(cell)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.rows.length === 0 && (
        <p className="px-3 py-4 text-center text-sm text-gray-400">No rows returned.</p>
      )}
    </div>
  )
}
