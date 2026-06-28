// Thin API client for the Local CSV Analyst.
//
// The frontend is a static export served same-origin with the FastAPI backend
// at http://localhost:8001/app/. All API calls therefore use RELATIVE,
// origin-rooted paths (`/datasets`, `/datasets/{id}/runs`, `/runs/{id}/stream`,
// `/runs/{id}`) — never an absolute host. The Next.js basePath ('/app') only
// affects asset/link routing, not raw fetch() / EventSource URLs.
//
// All JSON responses use the boilerplate envelope:
//   success: { "data": ..., "error": null }
//   error:   { "detail": { "code": "...", "message": "..." } }
// We unwrap `data` on success and surface `detail.message` on failure.

export interface SchemaColumn {
  name: string
  dtype: string
}

export interface Dataset {
  dataset_id: string
  filename: string
  row_count: number
  schema: SchemaColumn[]
  sample: Record<string, unknown>[]
}

export interface CreatedRun {
  run_id: string
  status: string
}

// SSE event payloads (see spec/api.md).
export interface PlanEvent {
  plan: string
}

export interface StepEvent {
  phase: 'generate_code' | 'execute_code'
  attempt: number
  message: string
}

export interface RetryEvent {
  attempt: number
  error: string
}

// Plotly figure shape — loose by design; ChartView passes it straight to Plotly.
export interface ChartSpec {
  data?: unknown[]
  layout?: Record<string, unknown>
  [key: string]: unknown
}

export interface FinalEvent {
  status: string
  answer: string
  chart_spec: ChartSpec | null
  table: Record<string, unknown>[]
  code: string
}

export interface ErrorEvent {
  status: string
  error: string
}

export interface RunStep {
  attempt: number
  code: string
  ok: boolean
  error: string | null
}

export interface Run {
  run_id: string
  dataset_id: string
  question: string
  plan: string | null
  status: string
  answer: string | null
  chart_spec: ChartSpec | null
  table: Record<string, unknown>[] | null
  steps: RunStep[]
  tokens: number | null
}

/** Thrown for any non-2xx API response; `message` is the human-facing copy. */
export class ApiError extends Error {
  code: string
  status: number
  constructor(message: string, code: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

const NETWORK_MESSAGE = 'Network error — is the server running?'

async function unwrap<T>(res: Response): Promise<T> {
  let body: unknown
  try {
    body = await res.json()
  } catch {
    if (!res.ok) {
      throw new ApiError(`Request failed (${res.status})`, 'bad_response', res.status)
    }
    throw new ApiError(NETWORK_MESSAGE, 'bad_response', res.status)
  }

  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } }).detail
    const message = detail?.message ?? `Request failed (${res.status})`
    const code = detail?.code ?? 'http_error'
    throw new ApiError(message, code, res.status)
  }

  const envelope = body as { data?: T; error?: unknown }
  if (envelope.data === undefined) {
    throw new ApiError('Malformed response from server.', 'bad_envelope', res.status)
  }
  return envelope.data
}

/** Wrap fetch so a thrown TypeError (connection refused / offline) becomes a clear message. */
async function safeFetch(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch {
    throw new ApiError(NETWORK_MESSAGE, 'network', 0)
  }
}

/** POST /datasets — upload a CSV, returns the created dataset + schema + sample. */
export async function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  const res = await safeFetch('/datasets', { method: 'POST', body: form })
  return unwrap<Dataset>(res)
}

/** POST /datasets/{id}/runs — ask a question; returns the run id + status. */
export async function createRun(datasetId: string, question: string): Promise<CreatedRun> {
  const res = await safeFetch(`/datasets/${datasetId}/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  return unwrap<CreatedRun>(res)
}

/** GET /runs/{id} — fetch the persisted run (audit trail). */
export async function getRun(runId: string): Promise<Run> {
  const res = await safeFetch(`/runs/${runId}`)
  return unwrap<Run>(res)
}

export interface StreamHandlers {
  onPlan?: (e: PlanEvent) => void
  onStep?: (e: StepEvent) => void
  onRetry?: (e: RetryEvent) => void
  onFinal?: (e: FinalEvent) => void
  onError?: (e: ErrorEvent) => void
  // Transport-level failure (connection dropped before a terminal event).
  onConnectionError?: (message: string) => void
}

/**
 * GET /runs/{id}/stream — open an SSE connection and dispatch typed events.
 * Closes the EventSource after a `final` or `error` event. Returns a `close()`
 * the caller can use to abort early (e.g. on unmount).
 */
export function streamRun(runId: string, handlers: StreamHandlers): () => void {
  const source = new EventSource(`/runs/${runId}/stream`)
  let closed = false

  const close = () => {
    if (!closed) {
      closed = true
      source.close()
    }
  }

  const parse = <T>(raw: string): T | null => {
    try {
      return JSON.parse(raw) as T
    } catch {
      return null
    }
  }

  source.addEventListener('plan', (ev) => {
    const data = parse<PlanEvent>((ev as MessageEvent).data)
    if (data) handlers.onPlan?.(data)
  })

  source.addEventListener('step', (ev) => {
    const data = parse<StepEvent>((ev as MessageEvent).data)
    if (data) handlers.onStep?.(data)
  })

  source.addEventListener('retry', (ev) => {
    const data = parse<RetryEvent>((ev as MessageEvent).data)
    if (data) handlers.onRetry?.(data)
  })

  source.addEventListener('final', (ev) => {
    const data = parse<FinalEvent>((ev as MessageEvent).data)
    if (data) handlers.onFinal?.(data)
    close()
  })

  source.addEventListener('error', (ev) => {
    // Distinguish an application `error` event (has a data payload) from a
    // transport error (EventSource fires a dataless `error` on disconnect).
    const message = (ev as MessageEvent).data
    if (typeof message === 'string' && message.length > 0) {
      const data = parse<ErrorEvent>(message)
      if (data) handlers.onError?.(data)
      close()
      return
    }
    // Transport error. If we haven't already closed on a terminal event,
    // surface a connection error and stop.
    if (!closed) {
      handlers.onConnectionError?.(NETWORK_MESSAGE)
      close()
    }
  })

  return close
}
