import React from 'react'

const MAX_DISPLAY = 500

export default function ResultTable({ rows, totalRows }) {
  if (!rows || rows.length === 0) return null
  const columns = Object.keys(rows[0])
  const displayed = rows.slice(0, MAX_DISPLAY)
  const truncated = rows.length > MAX_DISPLAY

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-xs border border-gray-200 rounded">
        <thead className="bg-gray-50">
          <tr>
            {columns.map(col => (
              <th key={col} className="px-3 py-2 text-left font-medium text-gray-600 border-b border-gray-200">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayed.map((row, i) => (
            <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
              {columns.map(col => (
                <td key={col} className="px-3 py-2 text-gray-700 border-b border-gray-100">
                  {row[col] === null ? <em className="text-gray-400">null</em> : String(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {truncated && (
        <p className="text-xs text-gray-400 mt-1">Showing {MAX_DISPLAY} of {rows.length} rows</p>
      )}
    </div>
  )
}
