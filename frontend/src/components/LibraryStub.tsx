// Labelled NON-FUNCTIONAL stub (Phase 3). Renders static placeholders only —
// it makes NO API call so it can never be mistaken for a failing request.

export default function LibraryStub() {
  return (
    <section
      aria-label="Dataset Library (coming soon)"
      className="rounded-lg border border-dashed border-gray-300 bg-gray-50/60 p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Dataset Library
        </h2>
        <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500">
          Coming soon
        </span>
      </div>
      <ul className="space-y-2" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="h-6 w-6 rounded bg-gray-200" />
            <span className="h-3 flex-1 rounded bg-gray-200" />
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] leading-snug text-gray-400">
        Your uploaded datasets will live here, browsable across sessions.
      </p>
    </section>
  )
}
