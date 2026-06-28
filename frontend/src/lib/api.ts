// API client + types. Codes against spec/api.md ONLY.
// The frontend is served at /app; API routes are at the root, so we hit absolute paths from origin.

export interface ProfileColumn {
  name: string
  dtype: string
  n_unique: number
  n_null: number
}

export interface DatasetProfile {
  columns: ProfileColumn[]
  ranges: Record<string, { min: number; max: number }>
  quality_flags: string[]
}

export interface Dataset {
  dataset_id: string
  name: string
  row_count: number
  col_count: number
  profile: DatasetProfile
}

export interface ChartSpec {
  // agent-picked chart; we render defensively from whatever shape arrives.
  type?: string // 'bar' | 'line' | 'area' | 'pie' | 'scatter'
  x?: string
  y?: string | string[]
  data?: Array<Record<string, unknown>>
  title?: string
}

export interface TableSpec {
  columns: string[]
  rows: Array<Array<unknown>>
}

export interface AnswerPayload {
  prose: string
  chart?: ChartSpec | null
  table?: TableSpec | null
  code: string
  tokens?: { prompt: number; completion: number }
  cost_usd?: number
  daily_total_usd?: number
  uncertainty?: string | null
  clarifying_question?: string | null
  status?: string
  follow_ups?: string[]
}

export interface StepEvent {
  step_index: number
  total: number
  node: string
  status: 'tried' | 'failed' | 'worked' | string
  detail?: string
  code?: string
  result_summary?: string
}

export interface RunStarted {
  run_id: string
  max_steps: number
}

export interface RunSummary {
  run_id: string
  question: string
  status: string
  step_count: number
  cost_usd: number
  created_at: string
}

export interface UsageToday {
  date: string
  total_cost_usd: number
  total_tokens: number
  run_count: number
}

export interface RunDetail extends RunSummary {
  prose?: string
  code?: string
  chart?: ChartSpec | null
  table?: TableSpec | null
  steps?: StepEvent[]
}

interface Envelope<T> {
  data?: T
  detail?: { message?: string }
}

async function unwrap<T>(res: Response): Promise<T> {
  let body: Envelope<T>
  try {
    body = await res.json()
  } catch {
    throw new Error(`Request failed (${res.status})`)
  }
  if (!res.ok) {
    throw new Error(body?.detail?.message ?? `Request failed (${res.status})`)
  }
  return body.data as T
}

export async function uploadDataset(file: File, name?: string): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  if (name) form.append('name', name)
  const res = await fetch('/datasets', { method: 'POST', body: form })
  return unwrap<Dataset>(res)
}

export async function fetchRuns(datasetId: string): Promise<RunSummary[]> {
  const res = await fetch(`/datasets/${datasetId}/runs`)
  const data = await unwrap<{ runs: RunSummary[] }>(res)
  return data.runs ?? []
}

export async function fetchRunDetail(runId: string): Promise<RunDetail> {
  const res = await fetch(`/runs/${runId}`)
  return unwrap<RunDetail>(res)
}

export async function fetchUsageToday(): Promise<UsageToday> {
  const res = await fetch('/usage/today')
  return unwrap<UsageToday>(res)
}

// SSE callbacks for a streaming ask.
export interface AskHandlers {
  onRunStarted?: (e: RunStarted) => void
  onStep?: (e: StepEvent) => void
  onAnswer?: (e: AnswerPayload) => void
  onError?: (message: string) => void
  onDone?: () => void
}

// Streams POST /datasets/{id}/ask (text/event-stream) and dispatches parsed events.
export async function askStream(
  datasetId: string,
  question: string,
  handlers: AskHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let res: Response
  try {
    res = await fetch(`/datasets/${datasetId}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ question }),
      signal,
    })
  } catch {
    handlers.onError?.('Network error — is the server running?')
    return
  }

  if (!res.ok || !res.body) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      message = body?.detail?.message ?? message
    } catch {
      /* keep default */
    }
    handlers.onError?.(message)
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  const dispatch = (rawEvent: string) => {
    let eventName = 'message'
    const dataLines: string[] = []
    for (const line of rawEvent.split('\n')) {
      if (line.startsWith('event:')) eventName = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
    }
    if (dataLines.length === 0) return
    let payload: unknown
    try {
      payload = JSON.parse(dataLines.join('\n'))
    } catch {
      return
    }
    switch (eventName) {
      case 'run_started':
        handlers.onRunStarted?.(payload as RunStarted)
        break
      case 'step':
        handlers.onStep?.(payload as StepEvent)
        break
      case 'answer':
        handlers.onAnswer?.(payload as AnswerPayload)
        break
      case 'error':
        handlers.onError?.((payload as { message?: string }).message ?? 'Run failed')
        break
      case 'done':
        handlers.onDone?.()
        break
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      // SSE events are separated by a blank line.
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        if (rawEvent.trim()) dispatch(rawEvent)
      }
    }
    if (buffer.trim()) dispatch(buffer)
  } catch {
    if (!signal?.aborted) handlers.onError?.('Stream interrupted — is the server running?')
    return
  }
  handlers.onDone?.()
}
