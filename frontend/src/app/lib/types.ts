// Shared types mirroring the spec/api.md response envelopes.

export interface ColumnProfile {
  name: string
  dtype: string
  null_count: number
  sample_values: unknown[]
}

export interface DatasetProfile {
  columns: ColumnProfile[]
  quality_flags: string[]
  sample_rows: Record<string, unknown>[]
}

export interface Dataset {
  id: string
  name: string
  row_count: number
  column_count: number
  file_format: string
  profile: DatasetProfile
}

export interface KeyNumber {
  label: string
  value: string | number
}

export type RunStatus = 'completed' | 'failed' | string

export interface RunResult {
  run_id: string
  dataset_id: string
  status: RunStatus
  answer_text: string | null
  narrative: string | null
  key_numbers: KeyNumber[] | null
  // Vega-Lite spec object (opaque here; passed straight to vega-embed).
  chart: Record<string, unknown> | null
  table: Record<string, unknown>[] | null
  code: string | null
  attempts: number
  error: string | null
  // Phase 2 additions.
  session_id: string | null
  tokens_used: number | null
  cost_estimate_usd: number | null
  created_at: string | null
}

// A lightweight run record for the history list (GET /runs).
export interface RunSummary {
  run_id: string
  question: string
  status: RunStatus
  created_at: string
  tokens_used: number | null
  cost_estimate_usd: number | null
}

// A conversation session scoped to one dataset (POST/GET /sessions).
export interface Session {
  id: string
  dataset_id: string
  created_at: string
  runs: RunSummary[]
}

// Pre-flight cost estimate (POST /cost/estimate).
export interface CostEstimate {
  estimated_tokens: number
  estimated_input_tokens: number
  estimated_output_tokens: number
  estimated_usd: number
  warn: boolean
  threshold_usd: number
}

// A single live-progress frame from the SSE stream (GET /runs/{id}/progress).
export interface ProgressEvent {
  step: string
  detail?: string
  status?: string
}
