'use client'

// Phase-1 labelled, NON-FUNCTIONAL stubs. Each carries a visible
// "Coming soon · Phase 2" tag so nothing here reads as a bug.

function StubTag() {
  return (
    <span
      data-testid="phase2-tag"
      className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500"
    >
      Coming soon · Phase 2
    </span>
  )
}

function StubShell({
  title,
  testid,
  children,
}: {
  title: string
  testid: string
  children?: React.ReactNode
}) {
  return (
    <div
      data-testid={testid}
      aria-disabled="true"
      className="pointer-events-none select-none rounded-xl border border-dashed border-gray-300 bg-white/60 p-4 opacity-60"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">{title}</h3>
        <StubTag />
      </div>
      {children}
    </div>
  )
}

export function LibrarySidebar() {
  return (
    <StubShell title="Library / Projects" testid="stub-library">
      <ul className="space-y-1.5 text-sm text-gray-400">
        <li className="rounded bg-gray-100 px-2 py-1.5">📁 Untitled project</li>
        <li className="rounded bg-gray-100 px-2 py-1.5">＋ New dataset</li>
        <li className="rounded bg-gray-100 px-2 py-1.5">✎ Rename · annotate columns</li>
      </ul>
    </StubShell>
  )
}

export function DatasetSelector() {
  return (
    <StubShell title="Multi-dataset selector" testid="stub-dataset-selector">
      <div className="text-sm text-gray-400">
        Choose / auto-detect multiple active datasets · cross-file joins
      </div>
    </StubShell>
  )
}
