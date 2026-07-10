export type StepName = 'Understand' | 'Extract' | 'Analyse' | 'Check' | 'Draw' | 'Review'

export const STEP_NAMES: StepName[] = ['Understand', 'Extract', 'Analyse', 'Check', 'Draw', 'Review']

export type StepStatus = 'pending' | 'active' | 'done' | 'skipped' | 'failed'

export type RunStatus = 'running' | 'completed' | 'needs_input' | 'out_of_scope' | 'failed'

export interface StepState {
  name: StepName
  status: StepStatus
  detail: string | null
}

export interface StepEvent {
  step: StepName
  status: 'active' | 'done' | 'skipped' | 'failed'
  detail?: string | null
  elapsed_ms: number
}

export interface NarrationEvent {
  text: string
}

export interface WarningEvent {
  message: string
}

export interface ClarificationEvent {
  question: string
  missing_param?: string | null
}

export interface ArtefactEvent {
  kind: string
  filename: string
  url: string
}

export interface TokensEvent {
  prompt_tokens: number
  completion_tokens: number
  cost_usd: number
  session_total_cost_usd: number
}

export interface DoneEvent {
  status: 'completed' | 'needs_input' | 'out_of_scope'
  verdict: string | null
}

export interface RunErrorEvent {
  code: string
  message: string
}

export interface SnapshotStep {
  name: StepName
  status: StepStatus
  started_at?: string | null
  ended_at?: string | null
  detail?: string | null
}

export interface ArtefactRecord {
  kind: string
  filename: string
  url: string
  size_bytes?: number
}

export interface Assumption {
  field: string
  value: string
  source: string
  note?: string | null
}

export interface RunSnapshot {
  run_id: string
  session_id: string
  prompt: string
  status: RunStatus
  plan_text: string | null
  scope_message: string | null
  clarification_question: string | null
  params: Record<string, unknown> | null
  assumptions: Assumption[] | null
  warnings: string[] | null
  steps: SnapshotStep[]
  checks: unknown[] | null
  checklist: unknown[] | null
  verdict: string | null
  suggestions: string[] | null
  artefacts: ArtefactRecord[]
  tokens: { prompt_tokens: number; completion_tokens: number; cost_usd: number } | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export interface SubmitDesignResponse {
  run_id: string
  status: string
  events_url: string
  snapshot_url: string
}

export interface SessionInfo {
  session_id: string
  title: string
  created_at: string
}

export interface RunListItem {
  run_id: string
  session_id: string
  prompt: string
  status: RunStatus
  verdict: string | null
  params_summary: string | null
  cost_usd: number | null
  started_at: string | null
  duration_ms: number | null
}

export interface DesignListing {
  runs: RunListItem[]
  total: number
}
