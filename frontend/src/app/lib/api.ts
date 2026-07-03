// Same-origin fetch helpers. The static UI is served at /app/ by FastAPI, but
// `basePath` only rewrites next/link + next/image — NOT raw fetch() calls — so
// an absolute path like `/datasets` hits the API root, not `/app/datasets`.

import type {
  CostEstimate,
  Dataset,
  ProgressEvent,
  RunResult,
  RunSummary,
  Session,
} from './types'

export class ApiError extends Error {
  code?: string
  constructor(message: string, code?: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}

interface Envelope<T> {
  data: T
  error: string | null
}

/** Parse the skeleton envelope; throw ApiError with the server message on failure. */
async function parse<T>(res: Response): Promise<T> {
  let body: unknown
  try {
    body = await res.json()
  } catch {
    throw new ApiError(`Request failed (${res.status})`)
  }
  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } })?.detail
    throw new ApiError(detail?.message ?? `Request failed (${res.status})`, detail?.code)
  }
  return (body as Envelope<T>).data
}

export async function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/datasets', { method: 'POST', body: form })
  return parse<Dataset>(res)
}

export async function askQuestion(
  datasetId: string,
  question: string,
  sessionId?: string | null,
  runId?: string,
): Promise<RunResult> {
  const body: Record<string, unknown> = { dataset_id: datasetId, question }
  if (sessionId) body.session_id = sessionId
  if (runId) body.run_id = runId
  const res = await fetch('/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  return parse<RunResult>(res)
}

// --- Phase 2: sessions, history, cost, live progress ---

/** Create a conversation session for a dataset (threads follow-up memory). */
export async function createSession(datasetId: string): Promise<Session> {
  const res = await fetch('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId }),
  })
  return parse<Session>(res)
}

/** Fetch a session with its runs. */
export async function getSession(id: string): Promise<Session> {
  const res = await fetch(`/sessions/${id}`)
  return parse<Session>(res)
}

/** List past runs (newest-first), filtered by dataset and optionally session. */
export async function listRuns(
  datasetId: string,
  sessionId?: string | null,
): Promise<RunSummary[]> {
  const params = new URLSearchParams({ dataset_id: datasetId })
  if (sessionId) params.set('session_id', sessionId)
  const res = await fetch(`/runs?${params.toString()}`)
  return parse<RunSummary[]>(res)
}

/** Fetch a saved run's full detail (answer/chart/table/code). */
export async function getRun(id: string): Promise<RunResult> {
  const res = await fetch(`/runs/${id}`)
  return parse<RunResult>(res)
}

/** Re-run a saved question against the current data — creates a NEW run. */
export async function rerunRun(id: string): Promise<RunResult> {
  const res = await fetch(`/runs/${id}/rerun`, { method: 'POST' })
  return parse<RunResult>(res)
}

/** Pre-flight token/cost estimate with an expensive-run warning flag. */
export async function estimateCost(datasetId: string, question: string): Promise<CostEstimate> {
  const res = await fetch('/cost/estimate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, question }),
  })
  return parse<CostEstimate>(res)
}

/**
 * Open the live step-progress SSE stream for a client-supplied run id.
 * Each frame is JSON `{step, detail?}`; a terminal `{step: "done", status}` frame
 * ends the stream. Returns the EventSource so the caller can close it explicitly.
 * Open this BEFORE POST /runs so early frames aren't missed.
 */
export function openRunProgress(
  runId: string,
  onEvent: (evt: ProgressEvent) => void,
): EventSource {
  const es = new EventSource(`/runs/${runId}/progress`)
  es.onmessage = e => {
    try {
      const evt = JSON.parse(e.data) as ProgressEvent
      onEvent(evt)
      if (evt.step === 'done') es.close()
    } catch {
      /* ignore a malformed frame */
    }
  }
  es.onerror = () => {
    // Server closed the stream (or a transient error) — stop auto-reconnect.
    es.close()
  }
  return es
}
