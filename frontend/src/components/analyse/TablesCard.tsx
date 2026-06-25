'use client'

import { StubPill, StubNote } from '@/components/StubBanner'

/**
 * Datasets / "Tables" card — Phase-1 labelled stub.
 *
 * Renders the filter tabs (All | Uploaded | Derived | This session) as static,
 * non-functional chips and an empty list. No /datasets call; becomes real in
 * Phase 2 (list + delete).
 */
const FILTERS = ['All', 'Uploaded', 'Derived', 'This session'] as const

export function TablesCard() {
  return (
    <section
      aria-labelledby="tables-heading"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="tables-heading" className="text-sm font-semibold text-gray-800">
          Tables
        </h2>
        <StubPill phase={2} />
      </div>

      <div
        role="group"
        aria-label="Dataset filters (placeholder)"
        className="mb-3 flex flex-wrap gap-2"
      >
        {FILTERS.map((f, i) => (
          <button
            key={f}
            type="button"
            disabled
            aria-disabled="true"
            aria-pressed={i === 0}
            title="Coming in Phase 2"
            className={`cursor-not-allowed rounded-full border px-3 py-1 text-xs font-medium ${
              i === 0
                ? 'border-gray-300 bg-gray-100 text-gray-500'
                : 'border-gray-200 bg-white text-gray-400'
            }`}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="rounded-md border border-dashed border-gray-200 px-3 py-8 text-center text-xs text-gray-400">
        No datasets yet.
        <StubNote>
          Uploaded and derived tables — with row × column counts, clean, and
          delete actions — will appear here in Phase 2.
        </StubNote>
      </div>
    </section>
  )
}
