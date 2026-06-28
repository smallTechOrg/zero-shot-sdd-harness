// API helpers for the Local Data Analyst.
//
// The frontend is a static export served under basePath `/app`, same-origin
// with the FastAPI backend at `http://localhost:8001`. The API routes live at
// the SERVER ROOT (not under /app), so we call them with leading-slash paths
// (e.g. `/datasets`, `/questions`) which resolve to the origin root.
//
// All JSON responses use the skeleton envelope `{ data, error }`; errors are
// raised as `{ detail: { code, message } }`.

export interface SchemaField {
  name: string
  type: string
}

export interface Dataset {
  id: string
  filename: string
  row_count: number
  column_count: number
  schema: SchemaField[]
  sample_rows: Record<string, unknown>[]
}

export interface KeyNumber {
  label: string
  value: string | number
}

export interface ResultTable {
  columns: string[]
  rows: (string | number | null)[][]
}

export interface AnalysisStep {
  step_index: number
  language: string
  code: string
  result: unknown
  error: string | null
  latency_ms: number | null
}

export interface Cost {
  tokens_in: number
  tokens_out: number
  estimated_usd: number
}

export type QuestionStatus = 'pending' | 'completed' | 'failed' | string

export interface Question {
  id: string
  status: QuestionStatus
  answer: string | null
  key_numbers: KeyNumber[]
  result_table: ResultTable | null
  plan: string[]
  steps: AnalysisStep[]
  cost: Cost | null
  cost_guard_warning: string | null
  error_message?: string | null
}

/** Thrown when the API returns a non-2xx status with a `{detail}` envelope. */
export class ApiError extends Error {
  code: string
  status: number
  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    if (!res.ok) {
      throw new ApiError('REQUEST_FAILED', `Request failed (${res.status})`, res.status)
    }
    throw new ApiError('BAD_RESPONSE', 'The server returned an unexpected response.', res.status)
  }

  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } })?.detail
    throw new ApiError(
      detail?.code ?? 'REQUEST_FAILED',
      detail?.message ?? `Request failed (${res.status})`,
      res.status,
    )
  }

  const envelope = body as { data?: T; error?: string | null }
  if (envelope?.error) {
    throw new ApiError('ERROR', envelope.error, res.status)
  }
  return envelope.data as T
}

/** Upload a CSV via multipart `POST /datasets`. */
export async function uploadDataset(file: File): Promise<Dataset> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch('/datasets', { method: 'POST', body: form })
  return unwrap<Dataset>(res)
}

/** Ask a question via `POST /questions`. */
export async function askQuestion(datasetId: string, text: string): Promise<Question> {
  const res = await fetch('/questions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, text }),
  })
  return unwrap<Question>(res)
}

/** Fetch a question's full payload via `GET /questions/{id}` (used for polling). */
export async function getQuestion(id: string): Promise<Question> {
  const res = await fetch(`/questions/${id}`, { method: 'GET' })
  return unwrap<Question>(res)
}

export function friendlyNetworkError(): string {
  return 'Network error — is the server running? Start it with `uv run python -m src`.'
}
