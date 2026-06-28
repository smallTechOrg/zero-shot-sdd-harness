'use client'

// NON-FUNCTIONAL Phase 1 stub. Deliberately greyed out and clearly labelled
// "Coming in Phase 2" so it is never mistaken for a broken feature.
export default function LibrarySidebar() {
  const placeholders = ['sales_2025.csv', 'customers.xlsx', 'web_events.csv']

  return (
    <aside
      data-testid="library-sidebar"
      aria-disabled="true"
      className="hidden w-60 shrink-0 flex-col rounded-2xl border border-slate-200 bg-white p-4 lg:flex"
    >
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Dataset Library</h2>
        <span
          data-testid="phase2-badge"
          className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500"
        >
          Coming in Phase 2
        </span>
      </div>

      <div className="pointer-events-none select-none space-y-2 opacity-40">
        {placeholders.map(name => (
          <div
            key={name}
            className="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2"
          >
            <span className="h-2 w-2 rounded-full bg-slate-300" />
            <span className="truncate text-xs text-slate-600">{name}</span>
          </div>
        ))}
      </div>

      <p className="mt-4 text-[11px] leading-relaxed text-slate-400">
        Your uploaded datasets will persist here across sessions in Phase 2.
      </p>
    </aside>
  )
}
