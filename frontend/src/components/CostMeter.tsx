'use client'

import type { UsageToday } from '@/lib/api'

interface Props {
  usage: UsageToday | null
}

export default function CostMeter({ usage }: Props) {
  return (
    <div
      data-testid="cost-meter"
      className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-2 shadow-sm"
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 6v12m-3-2.818.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33"
          />
        </svg>
      </div>
      <div className="leading-tight">
        <p className="text-[11px] uppercase tracking-wide text-slate-400">Today</p>
        <p className="text-sm font-semibold text-slate-800">
          {usage ? `$${usage.total_cost_usd.toFixed(4)}` : '$0.0000'}
        </p>
      </div>
      <div className="border-l border-slate-200 pl-3 leading-tight">
        <p className="text-[11px] uppercase tracking-wide text-slate-400">Tokens</p>
        <p className="text-sm font-semibold text-slate-800">
          {usage ? usage.total_tokens.toLocaleString() : '0'}
        </p>
      </div>
      <div className="border-l border-slate-200 pl-3 leading-tight">
        <p className="text-[11px] uppercase tracking-wide text-slate-400">Runs</p>
        <p className="text-sm font-semibold text-slate-800">{usage?.run_count ?? 0}</p>
      </div>
    </div>
  )
}
