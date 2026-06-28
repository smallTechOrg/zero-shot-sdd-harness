// Labelled NON-FUNCTIONAL stub (Phase 2). Static placeholder, no API call.

export default function FollowUpsStub() {
  return (
    <section
      aria-label="Suggested follow-ups (coming soon)"
      className="rounded-lg border border-dashed border-gray-300 bg-gray-50/60 p-4"
    >
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Suggested follow-ups
        </h3>
        <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500">
          Coming soon
        </span>
      </div>
      <div className="flex flex-wrap gap-2" aria-hidden="true">
        {['Break down by month', 'Compare top categories', 'Show the trend'].map((label) => (
          <span
            key={label}
            className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-400"
          >
            {label}
          </span>
        ))}
      </div>
      <p className="mt-3 text-[11px] leading-snug text-gray-400">
        After each answer the agent will propose questions you can click to run.
      </p>
    </section>
  )
}
