export default function PlanView({ plan }: { plan: string[] }) {
  if (!plan || plan.length === 0) return null
  return (
    <details className="rounded-lg border border-gray-200 bg-white" data-testid="plan-view">
      <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
        Plan <span className="text-gray-400">({plan.length} steps)</span>
      </summary>
      <ol className="list-decimal space-y-1.5 px-8 py-3 text-sm text-gray-600">
        {plan.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>
    </details>
  )
}
