'use client'

import { useEffect, useRef, useState } from 'react'

// vega-embed must NOT be imported at module top-level: it touches browser globals
// and breaks the Next.js static-export (SSR) build. It is imported dynamically
// inside useEffect so it only ever runs in the browser.

export default function ChartView({ spec }: { spec: Record<string, unknown> | null }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!spec || !containerRef.current) return
    let disposed = false
    let view: { finalize: () => void } | null = null

    ;(async () => {
      try {
        const embed = (await import('vega-embed')).default
        if (disposed || !containerRef.current) return
        const result = await embed(containerRef.current, spec as never, {
          actions: false,
          renderer: 'svg',
        })
        view = result.view
      } catch (e) {
        if (!disposed) setError(e instanceof Error ? e.message : 'Could not render chart')
      }
    })()

    return () => {
      disposed = true
      try {
        view?.finalize()
      } catch {
        /* noop */
      }
    }
  }, [spec])

  if (!spec) return null

  if (error) {
    return (
      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        Chart could not be rendered: {error}
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      data-testid="chart-view"
      className="w-full overflow-x-auto rounded-lg border border-gray-200 bg-white p-3"
    />
  )
}
