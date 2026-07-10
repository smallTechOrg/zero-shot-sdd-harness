import type { DesignListing, RunSnapshot, SessionInfo, SubmitDesignResponse } from './types'

// All paths are root-relative on purpose: the app is served by FastAPI at /app,
// and a relative path would be corrupted by the basePath.

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(code: string, message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError('NETWORK', 'Could not reach the server — is it running on localhost:8001?', 0)
  }

  let body: unknown = null
  try {
    body = await res.json()
  } catch {
    // non-JSON body handled below
  }

  if (!res.ok) {
    const detail = (body as { detail?: { code?: string; message?: string } } | null)?.detail
    throw new ApiError(
      detail?.code ?? 'HTTP_ERROR',
      detail?.message ?? `Request failed with status ${res.status}`,
      res.status,
    )
  }

  return (body as { data: T }).data
}

export function createSession(title?: string): Promise<SessionInfo> {
  return apiFetch<SessionInfo>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify(title ? { title } : {}),
  })
}

export function submitDesign(sessionId: string, prompt: string): Promise<SubmitDesignResponse> {
  return apiFetch<SubmitDesignResponse>(`/api/sessions/${sessionId}/designs`, {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

export function getRunSnapshot(runId: string): Promise<RunSnapshot> {
  return apiFetch<RunSnapshot>(`/api/designs/${runId}`)
}

export function listDesigns(sessionId: string): Promise<DesignListing> {
  return apiFetch<DesignListing>(`/api/designs?session_id=${encodeURIComponent(sessionId)}`)
}

export function runEventsUrl(runId: string): string {
  return `/api/designs/${runId}/events`
}

export async function fetchArtefactText(url: string): Promise<string> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new ApiError('ARTEFACT_FETCH', `Could not load artefact (${res.status})`, res.status)
  }
  return res.text()
}
