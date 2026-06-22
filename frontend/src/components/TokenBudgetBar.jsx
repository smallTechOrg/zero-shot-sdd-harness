import React from 'react'

export default function TokenBudgetBar({ tokenUsage, hardCap }) {
  if (!tokenUsage || tokenUsage.stub) return null
  const used = (tokenUsage.input_tokens || 0) + (tokenUsage.output_tokens || 0)
  const pct = Math.min(100, Math.round((used / hardCap) * 100))
  const color = pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-amber-400' : 'bg-green-500'

  return (
    <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
      <div className="flex items-center gap-2 text-xs text-gray-500">
        <span>Token budget:</span>
        <div className="flex-1 bg-gray-200 rounded-full h-1.5">
          <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
        </div>
        <span>{used.toLocaleString()} / {hardCap.toLocaleString()}</span>
      </div>
    </div>
  )
}
