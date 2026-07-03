// Same-origin fetch helpers. The static UI is served at /app/ by FastAPI, but
// `basePath` only rewrites next/link + next/image — NOT raw fetch() calls — so
// an absolute path like `/datasets` hits the API root, not `/app/datasets`.

import type { Dataset, RunResult } from './types'

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

export async function askQuestion(datasetId: string, question: string): Promise<RunResult> {
  const res = await fetch('/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dataset_id: datasetId, question }),
  })
  return parse<RunResult>(res)
}
