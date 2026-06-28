'use client'

// The transparency surface: renders the live SSE feed — plan first, then each
// step ("writing code", "running code"), retries WITH their error message,
// ending in the terminal (final/error/connection). Each item animates in.

export type FeedItem =
  | { kind: 'plan'; id: string; plan: string }
  | { kind: 'step'; id: string; phase: 'generate_code' | 'execute_code'; attempt: number; message: string }
  | { kind: 'retry'; id: string; attempt: number; error: string }
  | { kind: 'final'; id: string }
  | { kind: 'error'; id: string; error: string }
  | { kind: 'connection'; id: string; message: string }

interface StepStreamProps {
  items: FeedItem[]
  streaming: boolean
}

export default function StepStream({ items, streaming }: StepStreamProps) {
  if (items.length === 0 && !streaming) {
    return null
  }

  return (
    <section
      aria-label="Live run progress"
      aria-live="polite"
      className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
    >
      <h2 className="mb-3 text-sm font-semibold text-gray-900">Live run</h2>

      {items.length === 0 && streaming && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Dot pulse /> Connecting to the agent…
        </div>
      )}

      <ol className="space-y-2.5">
        {items.map((item) => (
          <li key={item.id} className="animate-fade-in">
            {renderItem(item)}
          </li>
        ))}
      </ol>

      {streaming && items.length > 0 && (
        <div className="mt-3 flex items-center gap-2 text-xs text-gray-400">
          <Dot pulse /> Working…
        </div>
      )}
    </section>
  )
}

function renderItem(item: FeedItem) {
  switch (item.kind) {
    case 'plan':
      return (
        <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
          <p className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-blue-700">
            <Dot color="bg-blue-500" /> Plan
          </p>
          <p className="whitespace-pre-wrap text-sm text-blue-900">{item.plan}</p>
        </div>
      )
    case 'step':
      return (
        <div className="flex items-center gap-2 text-sm text-gray-700">
          <Dot color="bg-gray-400" />
          <span className="font-medium capitalize">{item.message}</span>
          <span className="text-xs text-gray-400">
            ({item.phase === 'generate_code' ? 'writing code' : 'running code'} · attempt {item.attempt})
          </span>
        </div>
      )
    case 'retry':
      return (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <p className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-amber-700">
            <Dot color="bg-amber-500" /> Retry · attempt {item.attempt}
          </p>
          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-amber-900">
            {item.error}
          </pre>
        </div>
      )
    case 'final':
      return (
        <div className="flex items-center gap-2 text-sm font-medium text-emerald-700">
          <Dot color="bg-emerald-500" /> Done — answer ready below.
        </div>
      )
    case 'error':
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3">
          <p className="mb-1 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-red-700">
            <Dot color="bg-red-500" /> Failed
          </p>
          <pre className="overflow-x-auto whitespace-pre-wrap break-words font-mono text-xs text-red-900">
            {item.error}
          </pre>
        </div>
      )
    case 'connection':
      return (
        <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {item.message}
        </div>
      )
  }
}

function Dot({ color = 'bg-gray-400', pulse = false }: { color?: string; pulse?: boolean }) {
  return (
    <span
      className={`inline-block h-2 w-2 shrink-0 rounded-full ${color} ${pulse ? 'animate-pulse' : ''}`}
      aria-hidden="true"
    />
  )
}
