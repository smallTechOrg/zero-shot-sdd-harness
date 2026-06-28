'use client'

// react-plotly.js imports plotly.js which touches `window`/`document`, so it
// MUST be loaded via a dynamic import with ssr:false — otherwise the Next.js
// static-export build crashes on the browser globals.
import dynamic from 'next/dynamic'
import type { ChartSpec } from '@/lib/api'

const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => (
    <div className="flex h-72 items-center justify-center text-sm text-gray-400">Loading chart…</div>
  ),
})

interface ChartViewProps {
  chartSpec: ChartSpec | null
}

export default function ChartView({ chartSpec }: ChartViewProps) {
  const hasChart =
    chartSpec &&
    Array.isArray(chartSpec.data) &&
    chartSpec.data.length > 0

  return (
    <section
      aria-label="Chart"
      data-testid="chart-view"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Chart</h2>
      {hasChart ? (
        <div className="w-full overflow-hidden" data-testid="chart-plot">
          <Plot
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            data={chartSpec.data as any}
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            layout={{ autosize: true, margin: { t: 24, r: 16, b: 48, l: 48 }, ...(chartSpec.layout as any) }}
            config={{ responsive: true, displaylogo: false }}
            useResizeHandler
            style={{ width: '100%', height: '360px' }}
          />
        </div>
      ) : (
        <div className="flex h-40 items-center justify-center text-sm text-gray-400">
          No chart for this result.
        </div>
      )}
    </section>
  )
}
