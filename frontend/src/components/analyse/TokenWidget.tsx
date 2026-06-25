'use client'

import { StubPill } from '@/components/StubBanner'

/**
 * Token usage widget (C18) + C29 budget bar — Phase-1 labelled stub.
 *
 * Shows the intended rows (model, last query, today, storage, budget bar) with
 * placeholder "—" values. No /stats/daily call; real figures arrive in Phase 3.
 */
export function TokenWidget() {
  const rows: { label: string; value: string }[] = [
    { label: 'Model', value: '—' },
    { label: 'Last query (In / Out)', value: '— / —' },
    { label: 'Last query cost', value: '—' },
    { label: 'Today (In / Out / Queries)', value: '— / — / —' },
    { label: 'Today cost', value: '—' },
    { label: 'Storage (datasets / rows)', value: '0 / 0' },
  ]

  return (
    <section
      aria-labelledby="tokens-heading"
      className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 id="tokens-heading" className="text-sm font-semibold text-gray-800">
          Token usage
        </h2>
        <StubPill phase={3} />
      </div>

      <dl className="space-y-1.5 text-xs">
        {rows.map(row => (
          <div key={row.label} className="flex items-center justify-between gap-3">
            <dt className="text-gray-500">{row.label}</dt>
            <dd className="font-medium tabular-nums text-gray-400">{row.value}</dd>
          </div>
        ))}
      </dl>

      <div className="mt-3">
        <div className="mb-1 flex items-center justify-between text-[11px] text-gray-500">
          <span>Token budget</span>
          <span className="text-gray-400">— of —</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={0}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Token budget (placeholder)"
          className="h-2 w-full overflow-hidden rounded-full bg-gray-100"
        >
          <div className="h-full w-0 bg-gray-300" />
        </div>
      </div>
    </section>
  )
}
