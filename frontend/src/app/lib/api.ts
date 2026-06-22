// REST client for the Data Analyst Agent backend.
// All responses use the {data, error} envelope; helpers unwrap `.data`.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8001'

export type ColumnRows = { columns: string[]; rows: unknown[][] }

export type Dataset = {
  id: string
  name: string
  row_count: number
  created_at?: string
}

export type SchemaCol = { name: string; type: string }

export type SessionSummary = {
  id: string
  title: string
  updated_at?: string
  created_at?: string
}

export type ApiMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sql?: string | null
  result?: ColumnRows | null
  dataset_id?: string | null
  created_at?: string
}

export type QueryResponse = {
  message_id: string
  answer: string
  sql: string
  result: ColumnRows
  row_count: number
}

class ApiError extends Error {
  code?: string
  constructor(message: string, code?: string) {
    super(message)
    this.code = code
  }
}

async function unwrap<T>(res: Response): Promise<T> {
  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    throw new ApiError(`Request failed (${res.status})`)
  }
  const env = body as
    | { data?: T; error?: { code?: string; message?: string } | string }
    | undefined

  // Envelope error
  if (env && env.error) {
    if (typeof env.error === 'string') throw new ApiError(env.error)
    throw new ApiError(env.error.message ?? 'Request failed', env.error.code)
  }
  // FastAPI-style detail error on non-2xx
  if (!res.ok) {
    const detail = (body as { detail?: { message?: string; code?: string } })
      ?.detail
    throw new ApiError(detail?.message ?? `Request failed (${res.status})`, detail?.code)
  }
  if (env && 'data' in env) return env.data as T
  return body as T
}

export async function listDatasets(): Promise<Dataset[]> {
  const res = await fetch(`${API_BASE}/datasets`)
  const data = await unwrap<{ datasets: Dataset[] }>(res)
  return data.datasets ?? []
}

export async function uploadDataset(file: File): Promise<Dataset & { schema?: SchemaCol[] }> {
  const form = new FormData()
  form.append('file', file)
  const res = await fetch(`${API_BASE}/datasets`, { method: 'POST', body: form })
  return unwrap<Dataset & { schema?: SchemaCol[] }>(res)
}

export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_BASE}/sessions`)
  const data = await unwrap<{ sessions: SessionSummary[] }>(res)
  return data.sessions ?? []
}

export async function createSession(): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' })
  return unwrap<SessionSummary>(res)
}

export async function getMessages(sessionId: string): Promise<ApiMessage[]> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/messages`)
  const data = await unwrap<{ messages: ApiMessage[] }>(res)
  return data.messages ?? []
}

export async function askQuestion(
  sessionId: string,
  datasetId: string,
  question: string,
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/sessions/${sessionId}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, question }),
  })
  return unwrap<QueryResponse>(res)
}

export { ApiError }
