'use client'

import { StubPill, StubNote } from '@/components/StubBanner'

/**
 * Sessions sidebar (C9) — Phase-1 labelled stub.
 *
 * Renders the intended layout (list of sessions, +New / Delete actions) with
 * a placeholder empty list. No data is fetched; sessions become real in Phase 3.
 */
export function SessionSidebar() {
  return (
    <section
      aria-labelledby="sessions-heading"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="sessions-heading" className="text-sm font-semibold text-gray-800">
          Sessions
        </h2>
        <StubPill phase={3} />
      </div>

      <div className="mb-3 flex gap-2">
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-400"
          title="Coming in Phase 3"
        >
          + New
        </button>
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-400"
          title="Coming in Phase 3"
        >
          Delete selected
        </button>
      </div>

      <ul role="list" className="space-y-2 text-sm text-gray-500">
        <li className="rounded-md border border-dashed border-gray-200 px-3 py-6 text-center text-xs text-gray-400">
          No sessions yet.
          <StubNote>
            Saved conversations will be listed here. Resume, rename, and bulk
            actions arrive in Phase 3.
          </StubNote>
        </li>
      </ul>
    </section>
  )
}
