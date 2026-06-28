'use client'

import type { Dataset } from '../lib/api'
import { StubBadge } from './StubPanel'

export function Sidebar({ dataset }: { dataset: Dataset | null }) {
  return (
    <aside data-testid="sidebar" className="w-full shrink-0 lg:w-64">
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-900">Datasets</h2>

        {/* Current dataset is REAL */}
        <div className="mt-3">
          {dataset ? (
            <div
              data-testid="current-dataset"
              className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2"
            >
              <div className="truncate text-sm font-medium text-blue-900">{dataset.name}</div>
              <div className="text-xs text-blue-600">
                {dataset.row_count.toLocaleString('en-US')} rows · current
              </div>
            </div>
          ) : (
            <p className="text-xs text-gray-400">No dataset loaded yet.</p>
          )}
        </div>

        {/* STUB: past datasets (Phase 2) */}
        <div data-stub="true" aria-disabled="true" className="pointer-events-none mt-5 select-none">
          <div className="mb-2 flex items-center justify-between gap-2">
            <span className="text-xs font-medium text-gray-400">Past datasets</span>
            <StubBadge phase="Phase 2" />
          </div>
          <ul className="space-y-2">
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="flex items-center gap-2 rounded-lg border border-dashed border-gray-200 bg-gray-50 px-3 py-2"
              >
                <span className="h-2 w-2 rounded-full bg-gray-300" />
                <span className="h-3 flex-1 rounded bg-gray-200" />
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* STUB: compare another file (Phase 4) */}
      <div data-stub="true" aria-disabled="true" className="pointer-events-none mt-4 select-none">
        <button
          disabled
          className="flex w-full cursor-not-allowed items-center justify-center gap-2 rounded-xl border border-dashed border-gray-300 bg-gray-50 px-4 py-2.5 text-sm font-medium text-gray-400"
        >
          Compare another file
          <StubBadge phase="Phase 4" />
        </button>
      </div>

      {/* STUB: column notes (Phase 5) */}
      <div
        data-stub="true"
        aria-disabled="true"
        className="pointer-events-none mt-4 select-none rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold text-gray-400">Column notes</span>
          <StubBadge phase="Phase 5" />
        </div>
        <p className="mt-2 text-xs text-gray-400">
          Attach business rules (e.g. “revenue is in thousands”) for the agent to use.
        </p>
      </div>

      {/* STUB: daily cost (Phase 6) — per-question cost is real, shown in show-its-work */}
      <div
        data-stub="true"
        aria-disabled="true"
        title="Daily cost roll-up — coming soon"
        className="pointer-events-none mt-4 select-none rounded-xl border border-dashed border-gray-300 bg-gray-50 p-4"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-xs font-medium text-gray-400">Today’s spend</span>
          <StubBadge phase="Phase 6" />
        </div>
        <div className="mt-1 text-2xl font-bold text-gray-300" data-testid="daily-cost">
          —
        </div>
      </div>
    </aside>
  )
}
