import type { ResultTable } from "@/lib/api";

export default function ResultTableView({ table }: { table: ResultTable }) {
  if (!table.columns.length) return null;
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-slate-200" data-testid="result-table">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-100 text-slate-600">
          <tr>
            {table.columns.map((c) => (
              <th key={c} className="px-3 py-2 text-left font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.slice(0, 100).map((row, i) => (
            <tr key={i} className="border-t border-slate-100">
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-1.5 text-slate-800">
                  {cell === null ? "—" : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
