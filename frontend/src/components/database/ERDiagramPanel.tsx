'use client'

import { StubPill, StubNote } from '@/components/StubBanner'

/**
 * Schema / ER-diagram panel — Phase-1 labelled stub.
 *
 * A bordered placeholder box. The real SVG ER diagram (renderERDiagram /
 * _erFkLinks with crow's-foot FK edges, pan / zoom / fit) arrives in Phase 4.
 * This deliberately does NOT render any SVG diagram.
 */
export function ERDiagramPanel() {
  return (
    <section
      aria-labelledby="schema-heading"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="schema-heading" className="text-sm font-semibold text-gray-800">
          Schema
        </h2>
        <StubPill phase={4} />
      </div>

      {/* Controls placeholder — Fit / + / − (disabled) */}
      <div className="mb-3 flex gap-2">
        {['Fit', '+', '−'].map(label => (
          <button
            key={label}
            type="button"
            disabled
            aria-disabled="true"
            aria-label={
              label === '+'
                ? 'Zoom in (coming in Phase 4)'
                : label === '−'
                  ? 'Zoom out (coming in Phase 4)'
                  : 'Fit diagram (coming in Phase 4)'
            }
            title="Coming in Phase 4"
            className="cursor-not-allowed rounded-md border border-gray-200 bg-gray-50 px-3 py-1 text-xs font-medium text-gray-400"
          >
            {label}
          </button>
        ))}
      </div>

      <div className="flex min-h-[18rem] flex-col items-center justify-center rounded-md border-2 border-dashed border-gray-200 bg-gray-50 px-4 py-12 text-center">
        <span aria-hidden="true" className="mb-2 text-3xl text-gray-300">
          ⬚
        </span>
        <p className="text-sm font-medium text-gray-500">
          ER diagram — coming in Phase 4
        </p>
        <StubNote>
          The interactive schema diagram (table cards, inferred foreign-key
          edges, pan / zoom / fit) is not yet built.
        </StubNote>
      </div>
    </section>
  )
}
