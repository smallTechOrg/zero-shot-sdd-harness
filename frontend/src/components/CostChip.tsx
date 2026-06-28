import type { Cost } from '@/lib/api'

export default function CostChip({ cost }: { cost: Cost | null }) {
  if (!cost) return null
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border border-gray-200 bg-gray-50 px-3 py-1 text-xs text-gray-600"
      data-testid="cost-chip"
      title="Token usage and estimated cost for this question"
    >
      <span className="font-medium text-gray-700">Cost</span>
      <span>{(cost.tokens_in / 1000).toFixed(1)}k in</span>
      <span className="text-gray-300">/</span>
      <span>{(cost.tokens_out / 1000).toFixed(1)}k out</span>
      <span className="text-gray-300">·</span>
      <span className="font-medium text-gray-700">≈ ${cost.estimated_usd.toFixed(4)}</span>
    </span>
  )
}
