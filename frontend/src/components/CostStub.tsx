// Labelled NON-FUNCTIONAL stub (Phase 5). Header badges, visibly disabled.
// Renders static placeholders only — no API call, no live numbers.

const BADGES: { label: string; value: string }[] = [
  { label: 'Tokens', value: '—' },
  { label: 'Cost', value: '—' },
  { label: 'Session total', value: '—' },
  { label: 'Steps', value: '—' },
  { label: 'Timer', value: '—' },
]

export default function CostStub() {
  return (
    <div
      aria-label="Usage metrics (coming soon)"
      className="flex flex-wrap items-center gap-2"
      title="Coming soon"
    >
      {BADGES.map((b) => (
        <span
          key={b.label}
          aria-disabled="true"
          className="flex items-center gap-1 rounded-md border border-dashed border-gray-300 bg-gray-50 px-2 py-1 text-[11px] text-gray-400"
        >
          <span className="font-medium">{b.label}</span>
          <span className="tabular-nums">{b.value}</span>
        </span>
      ))}
      <span className="rounded-full bg-gray-200 px-2 py-0.5 text-[10px] font-medium text-gray-500">
        Coming soon
      </span>
    </div>
  )
}
