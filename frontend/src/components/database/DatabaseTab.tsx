'use client'

import { StubPill, StubNote } from '@/components/StubBanner'
import { ERDiagramPanel } from '@/components/database/ERDiagramPanel'
import { TableDescriptionPanel } from '@/components/database/TableDescriptionPanel'

/**
 * Database tab — Phase-1 labelled stub shell.
 *
 * Header (session name + uploaded/derived counts + Clear database) plus a
 * two-panel layout: ER-diagram placeholder + table-description placeholder.
 * Every control is a clearly-labelled, non-functional placeholder.
 */
export function DatabaseTab() {
  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold text-gray-800">Database</h2>
            <StubPill phase={4} />
          </div>
          <p className="mt-0.5 text-xs text-gray-500">
            No session · 0 uploaded / 0 derived
          </p>
        </div>
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="Coming in Phase 4"
          className="cursor-not-allowed rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-300"
        >
          Clear database
        </button>
      </div>

      <StubNote>
        The Database tab — interactive ER diagram and per-dataset description —
        becomes real in Phase 4. Nothing below is wired yet.
      </StubNote>

      {/* Two-panel layout */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.4fr_1fr]">
        <ERDiagramPanel />
        <TableDescriptionPanel />
      </div>
    </div>
  )
}
