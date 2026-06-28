// A clearly-labelled, non-functional "coming soon" stub.
// Stubs are visibly greyed + carry an explicit badge so they NEVER read as a
// bug. Errors (red) are a separate, distinct visual language.

interface StubPanelProps {
  title: string
  phase?: string
  children?: React.ReactNode
  className?: string
}

export function StubBadge({ phase }: { phase?: string }) {
  return (
    <span
      data-testid="stub-badge"
      className="inline-flex items-center gap-1 rounded-full border border-gray-300 bg-gray-100 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-gray-500"
    >
      coming soon{phase ? ` · ${phase}` : ''}
    </span>
  )
}

export function StubPanel({ title, phase, children, className = '' }: StubPanelProps) {
  return (
    <div
      data-stub="true"
      aria-disabled="true"
      className={`pointer-events-none select-none rounded-xl border border-dashed border-gray-300 bg-gray-50/70 p-4 text-gray-400 ${className}`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-400">{title}</h3>
        <StubBadge phase={phase} />
      </div>
      {children && <div className="mt-2 text-xs text-gray-400">{children}</div>}
    </div>
  )
}
