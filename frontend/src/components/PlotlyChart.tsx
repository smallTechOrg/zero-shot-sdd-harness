'use client'

import { useEffect, useRef } from 'react'

interface PlotlyFigure {
  data: Plotly.Data[]
  layout: Partial<Plotly.Layout>
}

interface PlotlyChartProps {
  chartJson: string
}

export default function PlotlyChart({ chartJson }: PlotlyChartProps) {
  const divRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!divRef.current) return

    let cancelled = false

    import('plotly.js-dist-min').then((Plotly) => {
      if (cancelled || !divRef.current) return
      try {
        const figure: PlotlyFigure = JSON.parse(chartJson)
        const layout: Partial<Plotly.Layout> = {
          ...figure.layout,
          autosize: true,
          margin: { l: 50, r: 20, t: 40, b: 50 },
        }
        Plotly.newPlot(divRef.current, figure.data, layout, { responsive: true })
      } catch {
        if (divRef.current) {
          divRef.current.textContent = 'Chart could not be rendered.'
        }
      }
    })

    return () => {
      cancelled = true
      if (divRef.current) {
        import('plotly.js-dist-min').then((Plotly) => {
          if (divRef.current) {
            try {
              Plotly.purge(divRef.current)
            } catch {
              // ignore purge errors
            }
          }
        })
      }
    }
  }, [chartJson])

  return <div ref={divRef} className="w-full" style={{ height: 400 }} />
}
