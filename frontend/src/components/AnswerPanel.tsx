'use client'

import type { Question } from '@/lib/api'
import KeyNumbers from './KeyNumbers'
import ResultTable from './ResultTable'
import PlanView from './PlanView'
import CodeView from './CodeView'
import CostChip from './CostChip'
import StubCard from './StubCard'

interface AnswerPanelProps {
  question: Question | null
  loading: boolean
  error: string | null
  hasDataset: boolean
}

function StepProgress({ question }: { question: Question | null }) {
  const steps = question?.steps ?? []
  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/60 p-4" data-testid="loading-state">
      <div className="flex items-center gap-3">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
        <span className="text-sm font-medium text-blue-800">
          {steps.length === 0 ? 'Planning the analysis…' : `Running step ${steps.length}…`}
        </span>
      </div>
      {steps.length > 0 && (
        <ol className="mt-3 space-y-1 text-xs text-blue-700">
          {steps.map(s => (
            <li key={s.step_index} className="flex items-center gap-2">
              <span className="text-blue-400">Step {s.step_index + 1}</span>
              <span className="font-mono uppercase text-blue-500">{s.language}</span>
              {s.error ? (
                <span className="text-red-600">error</span>
              ) : (
                <span className="text-blue-500">done</span>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default function AnswerPanel({ question, loading, error, hasDataset }: AnswerPanelProps) {
  // Empty state
  if (!loading && !error && !question) {
    return (
      <section className="rounded-xl border border-gray-200 bg-white p-8 text-center shadow-sm">
        <p className="text-sm text-gray-400">
          {hasDataset
            ? 'Ask a question above and the answer, key numbers, table, plan, code, and cost will appear here.'
            : 'Upload a CSV and ask a question to see your first answer here.'}
        </p>
      </section>
    )
  }

  // Loading / pending (live step updates)
  if (loading) {
    return (
      <section className="space-y-4">
        <StepProgress question={question} />
      </section>
    )
  }

  // Hard request error (network / non-question API failure)
  if (error) {
    return (
      <section
        role="alert"
        className="rounded-xl border border-red-200 bg-red-50 p-5 shadow-sm"
        data-testid="error-state"
      >
        <h2 className="text-sm font-semibold text-red-800">Something went wrong</h2>
        <p className="mt-1 text-sm text-red-700">{error}</p>
      </section>
    )
  }

  if (!question) return null

  const failed = question.status === 'failed'

  return (
    <section className="space-y-4" data-testid="answer-panel">
      {question.cost_guard_warning && (
        <div
          className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
          data-testid="cost-guard-warning"
        >
          ⚠ {question.cost_guard_warning}
        </div>
      )}

      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        {failed ? (
          <div data-testid="failed-state">
            <h2 className="text-sm font-semibold text-red-800">Analysis failed</h2>
            <p className="mt-1 text-sm text-red-700">
              {question.error_message ?? 'The agent could not complete this analysis.'}
            </p>
            <p className="mt-2 text-xs text-gray-500">
              Here is what it tried before it got stuck:
            </p>
          </div>
        ) : (
          <>
            {question.answer && (
              <p className="text-base leading-relaxed text-gray-900" data-testid="answer-text">
                {question.answer}
              </p>
            )}
            {question.key_numbers?.length > 0 && (
              <div className="mt-4">
                <KeyNumbers items={question.key_numbers} />
              </div>
            )}
            {question.result_table && (
              <div className="mt-4">
                <ResultTable table={question.result_table} />
              </div>
            )}
          </>
        )}

        <div className="mt-5 space-y-2">
          <PlanView plan={question.plan} />
          <CodeView steps={question.steps} />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <CostChip cost={question.cost} />
        </div>
      </div>

      {/* Labelled non-functional stubs for later phases */}
      <div className="space-y-2">
        <StubCard
          title="Suggested follow-ups"
          phase="Phase 2"
          description="Smart, clickable follow-up questions based on this answer."
        />
        <div className="grid gap-2 sm:grid-cols-2">
          <StubCard
            title="Charts"
            phase="Phase 3"
            description="Interactive chart (zoom / hover / filter) for this result."
          />
          <StubCard
            title="Daily cost total"
            phase="Phase 4"
            description="Running total of today's analysis spend."
          />
        </div>
      </div>
    </section>
  )
}
