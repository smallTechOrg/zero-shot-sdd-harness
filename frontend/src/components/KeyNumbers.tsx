import type { KeyNumber } from '@/lib/api'

export default function KeyNumbers({ items }: { items: KeyNumber[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3" data-testid="key-numbers">
      {items.map((kn, i) => (
        <div
          key={`${kn.label}-${i}`}
          className="rounded-lg border border-gray-200 bg-gray-50 p-3"
        >
          <div className="text-xs font-medium uppercase tracking-wide text-gray-500">
            {kn.label}
          </div>
          <div className="mt-1 text-lg font-semibold text-gray-900">{String(kn.value)}</div>
        </div>
      ))}
    </div>
  )
}
