export interface Dataset {
  id: string
  session_id: string
  table_name: string
  original_filename: string
  row_count: number
  column_names: string // JSON array string
  created_at: string
}

export interface QueryResult {
  id: string // audit_id
  question: string
  answer: string
  table: Record<string, unknown>[]
  sql: string
  timestamp: string
}

export interface AuditEntry {
  id: string
  session_id: string
  dataset_table: string
  question: string
  sql_generated: string | null
  row_count: number | null
  duration_ms: number | null
  error: string | null
  created_at: string
}
