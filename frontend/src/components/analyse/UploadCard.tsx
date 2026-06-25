'use client'

import { StubPill, StubNote } from '@/components/StubBanner'

/**
 * Upload card (C1, C11, C13, C16, C17) — Phase-1 labelled stub.
 *
 * Renders the drag-drop zone and "Choose files" button as visibly disabled,
 * non-functional placeholders. No file input is wired and no /upload call is
 * made; uploads become real in Phase 2.
 */
export function UploadCard() {
  return (
    <section
      aria-labelledby="upload-heading"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="upload-heading" className="text-sm font-semibold text-gray-800">
          Upload data
        </h2>
        <StubPill phase={2} />
      </div>

      {/* Drag-drop zone — purely presentational; no drop handlers wired. */}
      <div
        aria-disabled="true"
        className="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-gray-200 bg-gray-50 px-4 py-10 text-center"
      >
        <span aria-hidden="true" className="text-2xl text-gray-300">
          ⬆
        </span>
        <p className="text-sm text-gray-500">
          Drag &amp; drop CSV / TSV / JSON / Excel files here
        </p>
        <button
          type="button"
          disabled
          aria-disabled="true"
          title="Coming in Phase 2"
          className="mt-1 cursor-not-allowed rounded-md border border-gray-300 bg-white px-4 py-1.5 text-xs font-medium text-gray-400"
        >
          Choose files
        </button>
      </div>

      <StubNote>
        File upload — drag-and-drop, folder notes, duplicate resolution — comes
        in Phase 2. This zone does nothing yet.
      </StubNote>
    </section>
  )
}
