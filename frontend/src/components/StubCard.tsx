// A shared, clearly-labelled non-functional placeholder for features that ship
// in a later phase. Visibly inert (muted, disabled-looking) with a "Coming in a
// later phase" pill so a stub is never mistaken for a bug.

interface StubCardProps {
  title: string
  phase: string
  description?: string
  className?: string
  compact?: boolean
}

export default function StubCard({
  title,
  phase,
  description,
  className = '',
  compact = false,
}: StubCardProps) {
  return (
    <div
      aria-disabled="true"
      data-stub="true"
      className={`rounded-lg border border-dashed border-gray-300 bg-gray-50/60 ${
        compact ? 'p-3' : 'p-4'
      } text-gray-400 select-none ${className}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className={`font-medium ${compact ? 'text-xs' : 'text-sm'}`}>{title}</span>
        <span className="inline-flex shrink-0 items-center rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          {phase} · Coming soon
        </span>
      </div>
      {description && !compact && (
        <p className="mt-1.5 text-xs leading-relaxed text-gray-400">{description}</p>
      )}
    </div>
  )
}
