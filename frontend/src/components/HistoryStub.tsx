// Labelled NON-FUNCTIONAL stub (Phase 3/5). Static placeholder, no API call.

export default function HistoryStub() {
  return (
    <section
      aria-label="History (coming soon)"
      className="rounded-lg border border-dashed border-gray-300 bg-gray-50/60 p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          History
        </h2>
        <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500">
          Coming soon
        </span>
      </div>
      <ul className="space-y-2" aria-hidden="true">
        {[0, 1].map((i) => (
          <li key={i} className="space-y-1">
            <span className="block h-3 w-3/4 rounded bg-gray-200" />
            <span className="block h-2 w-1/2 rounded bg-gray-200" />
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] leading-snug text-gray-400">
        Every question you ask will be saved here as a re-openable audit trail.
      </p>
    </section>
  )
}
