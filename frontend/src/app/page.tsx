'use client'

import { useState } from 'react'
import {
  ApiError,
  askQuestion,
  createSession,
  estimateCost,
  getRun,
  listRuns,
  openRunProgress,
  rerunRun,
} from './lib/api'
import type {
  CostEstimate,
  Dataset,
  ProgressEvent,
  RunResult,
  RunSummary,
} from './lib/types'
import UploadBox from './components/UploadBox'
import ProfileCard from './components/ProfileCard'
import ChatInput from './components/ChatInput'
import AnswerBlock from './components/AnswerBlock'
import ProgressSteps from './components/ProgressSteps'
import CostMeter from './components/CostMeter'
import HistoryPanel from './components/HistoryPanel'
import { LibrarySidebar, DatasetSelector } from './components/stubs'

interface Turn {
  question: string
  run: RunResult | null
  error: string | null
  // Fresh, typed questions stream live progress; re-runs use a plain spinner.
  live: boolean
  progress: ProgressEvent[]
  progressDone: boolean
}

function fmtTokens(n: number): string {
  return n.toLocaleString('en-US')
}

function fmtUsd(n: number | null): string {
  if (n == null) return '—'
  if (n === 0) return '$0.00'
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(2)}`
}

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [history, setHistory] = useState<RunSummary[]>([])
  const [running, setRunning] = useState(false)
  const [pending, setPending] = useState<{ question: string; estimate: CostEstimate } | null>(null)
  const [selected, setSelected] = useState<
    { summary: RunSummary; run: RunResult | null; error: string | null } | null
  >(null)

  // --- Session cost roll-up (real, from completed runs) ---
  const completed = turns.filter(t => t.run && t.run.status !== 'failed')
  const totalTokens = completed.reduce((s, t) => s + (t.run!.tokens_used ?? 0), 0)
  const totalCost = completed.reduce((s, t) => s + (t.run!.cost_estimate_usd ?? 0), 0)
  const lastRun = completed.length > 0 ? completed[completed.length - 1].run! : null

  async function refreshHistory(datasetId: string, sId: string | null) {
    try {
      const items = await listRuns(datasetId, sId)
      setHistory(items)
    } catch {
      /* history refresh is non-fatal */
    }
  }

  // A new dataset starts a fresh session (memory + cost reset).
  async function handleDatasetLoaded(d: Dataset) {
    setDataset(d)
    setTurns([])
    setHistory([])
    setSelected(null)
    setPending(null)
    setSessionId(null)
    try {
      const session = await createSession(d.id)
      setSessionId(session.id)
      setHistory(session.runs ?? [])
    } catch {
      // Session creation failed — asking still works (the server threads a
      // session by dataset), memory just won't carry across turns. Non-fatal.
    }
  }

  // Pre-flight the cost estimate; only interrupt the flow when it warns.
  async function handleAsk(question: string) {
    if (!dataset) return
    try {
      const estimate = await estimateCost(dataset.id, question)
      if (estimate.warn) {
        setPending({ question, estimate })
        return
      }
    } catch {
      // Estimate is best-effort — proceed with the run if it fails.
    }
    await runQuestion(question)
  }

  async function runQuestion(question: string) {
    if (!dataset) return
    setPending(null)
    setRunning(true)
    const idx = turns.length
    const runId = crypto.randomUUID()
    setTurns(prev => [
      ...prev,
      { question, run: null, error: null, live: true, progress: [], progressDone: false },
    ])

    // Open the live-progress stream BEFORE the POST so early frames aren't missed.
    const es = openRunProgress(runId, evt => {
      setTurns(prev =>
        prev.map((t, i) =>
          i === idx
            ? {
                ...t,
                progress: evt.step === 'done' ? t.progress : [...t.progress, evt],
                progressDone: evt.step === 'done' ? true : t.progressDone,
              }
            : t,
        ),
      )
    })

    try {
      const run = await askQuestion(dataset.id, question, sessionId, runId)
      setTurns(prev => prev.map((t, i) => (i === idx ? { ...t, run, progressDone: true } : t)))
      await refreshHistory(dataset.id, sessionId)
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : 'Network error — is the server running?'
      setTurns(prev =>
        prev.map((t, i) => (i === idx ? { ...t, error: msg, progressDone: true } : t)),
      )
    } finally {
      es.close()
      setRunning(false)
    }
  }

  async function handleOpenHistory(summary: RunSummary) {
    setSelected({ summary, run: null, error: null })
    try {
      const run = await getRun(summary.run_id)
      setSelected({ summary, run, error: null })
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Could not load this run.'
      setSelected({ summary, run: null, error: msg })
    }
  }

  // Re-run appends a NEW turn to the conversation (a plain spinner — live SSE
  // progress is only wired for freshly-typed questions).
  async function handleRerun(summary: RunSummary) {
    if (!dataset) return
    setSelected(null)
    setRunning(true)
    const idx = turns.length
    setTurns(prev => [
      ...prev,
      { question: summary.question, run: null, error: null, live: false, progress: [], progressDone: false },
    ])
    try {
      const run = await rerunRun(summary.run_id)
      setTurns(prev => prev.map((t, i) => (i === idx ? { ...t, run } : t)))
      await refreshHistory(dataset.id, sessionId)
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : 'Re-run failed.'
      setTurns(prev => prev.map((t, i) => (i === idx ? { ...t, error: msg } : t)))
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="min-h-screen">
      {/* Top toolbar */}
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold tracking-tight text-gray-900">📊 DataChat</span>
            <span className="hidden text-sm text-gray-400 sm:inline">
              ask your spreadsheet anything
            </span>
          </div>
          <div className="hidden w-72 sm:block">
            <DatasetSelector />
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-6 lg:grid-cols-[16rem_1fr]">
        {/* Left sidebar — real History + Cost, plus the remaining Library stub */}
        <aside className="hidden space-y-4 lg:block">
          <HistoryPanel items={history} onOpen={handleOpenHistory} />
          <CostMeter
            lastTokens={lastRun?.tokens_used ?? null}
            lastCost={lastRun?.cost_estimate_usd ?? null}
            totalTokens={totalTokens}
            totalCost={totalCost}
            count={completed.length}
          />
          <LibrarySidebar />
        </aside>

        {/* Main column */}
        <main className="space-y-6">
          {!dataset ? (
            <EmptyState onLoaded={handleDatasetLoaded} />
          ) : (
            <>
              <ProfileCard dataset={dataset} />

              <section className="space-y-6" data-testid="conversation">
                {turns.map((turn, i) => (
                  <div key={i} className="space-y-3">
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl bg-blue-600 px-4 py-2 text-sm text-white">
                        {turn.question}
                      </div>
                    </div>

                    {turn.run ? (
                      <>
                        <AnswerBlock run={turn.run} />
                        {turn.run.status !== 'failed' && turn.run.tokens_used != null && (
                          <p className="px-1 text-xs text-gray-400" data-testid="turn-cost">
                            {fmtTokens(turn.run.tokens_used)} tokens ·{' '}
                            {fmtUsd(turn.run.cost_estimate_usd)} est.
                          </p>
                        )}
                      </>
                    ) : turn.error ? (
                      <div
                        role="alert"
                        data-testid="turn-error"
                        className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                      >
                        {turn.error}
                      </div>
                    ) : turn.live ? (
                      <ProgressSteps events={turn.progress} done={turn.progressDone} />
                    ) : (
                      <Analyzing />
                    )}
                  </div>
                ))}
              </section>

              <div className="sticky bottom-0 space-y-3 bg-gradient-to-t from-gray-50 via-gray-50 pt-4">
                {pending && (
                  <ExpensiveWarning
                    estimate={pending.estimate}
                    onCancel={() => setPending(null)}
                    onConfirm={() => runQuestion(pending.question)}
                  />
                )}
                <ChatInput onAsk={handleAsk} disabled={running} running={running} />
              </div>
            </>
          )}
        </main>
      </div>

      {/* History detail overlay — saved answer + re-run */}
      {selected && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/40 p-4 sm:p-8"
          role="dialog"
          aria-modal="true"
          onClick={() => setSelected(null)}
        >
          <div
            className="w-full max-w-3xl space-y-4 rounded-2xl bg-white p-6 shadow-xl"
            data-testid="history-detail"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Saved run
                </p>
                <h3 className="text-base font-semibold text-gray-900">
                  {selected.summary.question}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                aria-label="Close"
                className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700"
              >
                ✕
              </button>
            </div>

            {selected.run ? (
              <AnswerBlock run={selected.run} />
            ) : selected.error ? (
              <div
                role="alert"
                className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
              >
                {selected.error}
              </div>
            ) : (
              <Analyzing />
            )}

            <div className="flex justify-end gap-2 border-t border-gray-100 pt-4">
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="rounded-xl px-4 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100"
              >
                Close
              </button>
              <button
                type="button"
                data-testid="history-rerun"
                onClick={() => handleRerun(selected.summary)}
                disabled={running}
                className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Re-run against current data
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function ExpensiveWarning({
  estimate,
  onCancel,
  onConfirm,
}: {
  estimate: CostEstimate
  onCancel: () => void
  onConfirm: () => void
}) {
  return (
    <div
      role="alert"
      data-testid="expensive-warning"
      className="rounded-2xl border border-amber-300 bg-amber-50 p-4"
    >
      <p className="text-sm font-semibold text-amber-900">This may be an expensive question.</p>
      <p className="mt-1 text-sm text-amber-800">
        Estimated {estimate.estimated_tokens.toLocaleString('en-US')} tokens · about{' '}
        {fmtUsd(estimate.estimated_usd)}
        {estimate.threshold_usd
          ? ` (over the ${fmtUsd(estimate.threshold_usd)} threshold)`
          : ''}
        . Run anyway?
      </p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          data-testid="expensive-cancel"
          onClick={onCancel}
          className="rounded-xl px-4 py-2 text-sm font-medium text-amber-900 hover:bg-amber-100"
        >
          Cancel
        </button>
        <button
          type="button"
          data-testid="expensive-confirm"
          onClick={onConfirm}
          className="rounded-xl bg-amber-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-amber-700"
        >
          Run anyway
        </button>
      </div>
    </div>
  )
}

function EmptyState({ onLoaded }: { onLoaded: (d: Dataset) => void }) {
  return (
    <div className="mx-auto max-w-xl py-12 text-center" data-testid="empty-state">
      <h1 className="mb-2 text-2xl font-bold tracking-tight text-gray-900">
        Upload a dataset to begin
      </h1>
      <p className="mb-8 text-sm text-gray-500">
        Drop a CSV or Excel file and ask questions in plain language.
      </p>
      <UploadBox onLoaded={onLoaded} />
    </div>
  )
}

function Analyzing() {
  return (
    <div
      data-testid="analyzing"
      className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white p-5 text-sm text-gray-600 shadow-sm"
    >
      <div
        className="h-5 w-5 animate-spin rounded-full border-2 border-gray-300 border-t-blue-600"
        aria-label="loading"
      />
      <span className="font-medium">Analyzing…</span>
    </div>
  )
}
