'use client'

import { StubPill, StubNote } from '@/components/StubBanner'

/**
 * Table description panel — Phase-1 labelled stub.
 *
 * Renders the intended sections (origin, rows × cols, keys, columns, context
 * notes, preview, actions) as empty placeholders. No /datasets/{id}/preview
 * call; becomes real in Phase 4.
 */
export function TableDescriptionPanel() {
  return (
    <section
      aria-labelledby="description-heading"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="description-heading" className="text-sm font-semibold text-gray-800">
          Table description
        </h2>
        <StubPill phase={4} />
      </div>

      <div className="rounded-md border border-dashed border-gray-200 px-3 py-8 text-center text-xs text-gray-400">
        Select a dataset to see its details.
        <StubNote>
          Origin, rows × cols, keys (PK / FK), columns, context notes, and a
          data preview will appear here in Phase 4.
        </StubNote>
      </div>

      <div className="mt-3 flex gap-2">
        {['Clean', 'Re-derive', 'Delete'].map(action => (
          <button
            key={action}
            type="button"
            disabled
            aria-disabled="true"
            title="Coming in Phase 4"
            className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs font-medium text-gray-400"
          >
            {action}
          </button>
        ))}
      </div>
    </section>
  )
}
