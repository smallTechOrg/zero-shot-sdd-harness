'use client'

import { useEffect, useRef } from 'react'

interface PlotlyChartProps {
  chartJson: string
}

export default function PlotlyChart({ chartJson }: PlotlyChartProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current) return
    let cancelled = false

    import('plotly.js-dist-min').then((Plotly) => {
      if (cancelled || !ref.current) return
      try {
        const fig = JSON.parse(chartJson)
        Plotly.react(ref.current!, fig.data || [], fig.layout || {}, { responsive: true })
      } catch {
        // invalid JSON — render nothing
      }
    })

    return () => {
      cancelled = true
    }
  }, [chartJson])

  return <div ref={ref} style={{ width: '100%', minHeight: '400px' }} />
}
