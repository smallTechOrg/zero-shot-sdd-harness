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
}
