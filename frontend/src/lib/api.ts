// API types and fetch wrappers for the Data Analysis Agent

export interface ColumnInfo {
  name: string
  dtype: string
}

export interface UploadResult {
  upload_id: string
  filename: string
  row_count: number
  col_count: number
  columns: ColumnInfo[]
  uploaded_at?: string
}

export interface UploadSummary extends UploadResult {
  uploaded_at: string
}

export interface AnalysisResult {
  analysis_id: string
  status: 'pending' | 'completed' | 'failed'
  analysis_type?: string
  summary: string | null
  chart_json: string | null
  table: Record<string, unknown>[] | null
  error: string | null
  error_message?: string | null
}

// --- Envelope helper ---

interface ApiEnvelope<T> {
  data: T | null
  error: { code: string; message: string } | null
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(path, init)
  } catch (err) {
    if (err instanceof TypeError) {
      throw new Error('Cannot reach the server. Is it running on port 8001?')
    }
    throw err
  }
  let envelope: ApiEnvelope<T>
  try {
    envelope = await res.json()
  } catch {
    throw new Error(`Server returned non-JSON (status ${res.status})`)
  }

  if (!res.ok || envelope.error) {
    const msg =
      envelope.error?.message ??
      `Request failed (${res.status})`
    throw new Error(msg)
  }

  if (envelope.data === null || envelope.data === undefined) {
    throw new Error('Empty response from server')
  }

  return envelope.data
}

// --- API wrappers ---

export async function uploadFile(file: File): Promise<UploadResult> {
  const form = new FormData()
  form.append('file', file)
  return apiFetch<UploadResult>('/uploads', {
    method: 'POST',
    body: form,
  })
}

export async function getUploads(): Promise<UploadSummary[]> {
  return apiFetch<UploadSummary[]>('/uploads')
}

export async function runAnalysis(
  uploadId: string,
  analysisType: string,
  params: object,
): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>('/analyses', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      upload_id: uploadId,
      analysis_type: analysisType,
      params,
      question: null,
    }),
  })
}

export async function getAnalysis(analysisId: string): Promise<AnalysisResult> {
  return apiFetch<AnalysisResult>(`/analyses/${analysisId}`)
}
