'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import ArtefactTabs, { type TabId } from '@/components/ArtefactTabs'
import PromptPanel, { CANONICAL_PROMPT, type PromptMode } from '@/components/PromptPanel'
import StatusLine from '@/components/StatusLine'
import StepTracker from '@/components/StepTracker'
import SuggestionChips from '@/components/SuggestionChips'
import TokenCostBadge from '@/components/TokenCostBadge'
import TurnHistory, { type TurnDetail } from '@/components/TurnHistory'
import { ApiError, createSession, fetchArtefactText, getRunSnapshot, listDesigns, runEventsUrl, submitDesign } from '@/lib/api'
import { subscribeToRun, type RunSubscription } from '@/lib/sse'
import {
  STEP_NAMES,
  type RunListItem,
  type RunSnapshot,
  type RunStatus,
  type StepName,
  type StepState,
} from '@/lib/types'

const SESSION_STORAGE_KEY = 'culvert.session_id'

// Fallback tags for skipped steps rehydrated from a snapshot (the live SSE
// `step` event carries the tag in `detail`; the snapshot may not).
const SKIPPED_STEP_TAG: Partial<Record<StepName, string>> = {
  Check: 'Coming in Phase 2',
  Review: 'Coming in Phase 2',
}

interface RunView {
  runId: string
  prompt: string
  status: RunStatus
  steps: Record<StepName, StepState>
  narration: string
  warnings: string[]
  clarificationQuestion: string | null
  svgMarkup: string | null
  dxfUrl: string | null
  runTokens: number
  runCostUsd: number
  errorMessage: string | null
}

function initialSteps(): Record<StepName, StepState> {
  return Object.fromEntries(
    STEP_NAMES.map(name => [name, { name, status: 'pending', detail: null }]),
  ) as Record<StepName, StepState>
}

function stepsFromSnapshot(snap: RunSnapshot): Record<StepName, StepState> {
  const steps = initialSteps()
  for (const s of snap.steps ?? []) {
    if (!(s.name in steps)) continue
    steps[s.name] = {
      name: s.name,
      status: s.status,
      detail: s.detail ?? (s.status === 'skipped' ? (SKIPPED_STEP_TAG[s.name] ?? 'Coming soon') : null),
    }
  }
  return steps
}

function terminalNarration(status: RunStatus): string | null {
  switch (status) {
    case 'completed':
      return 'Design complete — the GA drawing is ready in the Drawing tab.'
    case 'needs_input':
      return 'The agent needs one more detail — answer the question in the session panel.'
    case 'out_of_scope':
      return 'This request is outside the demonstrator’s scope — the agent’s reply is in the session panel.'
    default:
      return null
  }
}

function viewFromSnapshot(snap: RunSnapshot): RunView {
  const tokens = snap.tokens ?? { prompt_tokens: 0, completion_tokens: 0, cost_usd: 0 }
  return {
    runId: snap.run_id,
    prompt: snap.prompt,
    status: snap.status,
    steps: stepsFromSnapshot(snap),
    narration: terminalNarration(snap.status) ?? snap.plan_text ?? '',
    warnings: snap.warnings ?? [],
    clarificationQuestion: snap.clarification_question,
    svgMarkup: null,
    dxfUrl: snap.artefacts?.find(a => a.kind === 'ga_dxf')?.url ?? null,
    runTokens: (tokens.prompt_tokens ?? 0) + (tokens.completion_tokens ?? 0),
    runCostUsd: tokens.cost_usd ?? 0,
    errorMessage: snap.error_message,
  }
}

export default function DesignStudio() {
  const [booting, setBooting] = useState(true)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [turns, setTurns] = useState<RunListItem[]>([])
  const [turnDetails, setTurnDetails] = useState<Record<string, TurnDetail>>({})
  const [run, setRun] = useState<RunView | null>(null)
  const [elapsedMs, setElapsedMs] = useState(0)
  const [sessionCostUsd, setSessionCostUsd] = useState(0)
  const [promptValue, setPromptValue] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [activeTab, setActiveTab] = useState<TabId>('drawing')
  const [toast, setToast] = useState<string | null>(null)

  const subscriptionRef = useRef<RunSubscription | null>(null)
  const elapsedBaseRef = useRef({ baseMs: 0, wallStart: Date.now() })
  const runStatusRef = useRef<RunStatus | null>(null)
  runStatusRef.current = run?.status ?? null

  const isRunning = run?.status === 'running'

  const persistSession = useCallback((sid: string) => {
    setSessionId(sid)
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, sid)
    } catch {
      // private mode — session survives in memory only
    }
  }, [])

  const storeTurnDetail = useCallback((snap: RunSnapshot) => {
    setTurnDetails(prev => ({
      ...prev,
      [snap.run_id]: {
        scopeMessage: snap.scope_message,
        clarificationQuestion: snap.clarification_question,
      },
    }))
  }, [])

  const loadSvgArtefact = useCallback((runId: string, url: string) => {
    fetchArtefactText(url)
      .then(svg => setRun(prev => (prev && prev.runId === runId ? { ...prev, svgMarkup: svg } : prev)))
      .catch(() => {
        // artefact fetch failure is non-fatal; the tab keeps its waiting state
      })
  }, [])

  const refreshTurns = useCallback(async (sid: string) => {
    try {
      const listing = await listDesigns(sid)
      setTurns(listing.runs)
    } catch {
      // listing refresh is cosmetic — the live view already has the run
    }
  }, [])

  const finalizeRun = useCallback(
    async (runId: string, sid: string) => {
      try {
        const snap = await getRunSnapshot(runId)
        storeTurnDetail(snap)
        setRun(prev => {
          if (!prev || prev.runId !== runId) return prev
          const final = viewFromSnapshot(snap)
          return { ...final, svgMarkup: prev.svgMarkup, narration: terminalNarration(snap.status) ?? prev.narration }
        })
        if (snap.duration_ms != null) setElapsedMs(snap.duration_ms)
        const svgArt = snap.artefacts?.find(a => a.kind === 'ga_svg')
        if (svgArt) loadSvgArtefact(runId, svgArt.url)
      } catch {
        // snapshot fetch failure — the SSE-built state stands
      }
      await refreshTurns(sid)
    },
    [loadSvgArtefact, refreshTurns, storeTurnDetail],
  )

  const applyLiveSnapshot = useCallback(
    (snap: RunSnapshot) => {
      storeTurnDetail(snap)
      setRun(prev => {
        if (prev && prev.runId !== snap.run_id) return prev
        const next = viewFromSnapshot(snap)
        return { ...next, svgMarkup: prev?.svgMarkup ?? null, narration: prev?.narration || next.narration }
      })
      const svgArt = snap.artefacts?.find(a => a.kind === 'ga_svg')
      if (svgArt) loadSvgArtefact(snap.run_id, svgArt.url)
    },
    [loadSvgArtefact, storeTurnDetail],
  )

  const openStream = useCallback(
    (runId: string, sid: string) => {
      subscriptionRef.current?.close()
      subscriptionRef.current = subscribeToRun(runEventsUrl(runId), {
        onSnapshot: applyLiveSnapshot,
        onStep: event => {
          elapsedBaseRef.current = { baseMs: event.elapsed_ms, wallStart: Date.now() }
          setRun(prev => {
            if (!prev || prev.runId !== runId) return prev
            const steps = {
              ...prev.steps,
              [event.step]: { name: event.step, status: event.status, detail: event.detail ?? null },
            }
            return { ...prev, steps }
          })
        },
        onNarration: event => {
          setRun(prev => (prev && prev.runId === runId ? { ...prev, narration: event.text } : prev))
        },
        onWarning: event => {
          setRun(prev =>
            prev && prev.runId === runId ? { ...prev, warnings: [...prev.warnings, event.message] } : prev,
          )
        },
        onClarification: event => {
          setRun(prev => (prev && prev.runId === runId ? { ...prev, clarificationQuestion: event.question } : prev))
        },
        onArtefact: event => {
          if (event.kind === 'ga_svg') {
            loadSvgArtefact(runId, event.url)
          } else if (event.kind === 'ga_dxf') {
            setRun(prev => (prev && prev.runId === runId ? { ...prev, dxfUrl: event.url } : prev))
          }
        },
        onTokens: event => {
          setRun(prev =>
            prev && prev.runId === runId
              ? {
                  ...prev,
                  runTokens: (event.prompt_tokens ?? 0) + (event.completion_tokens ?? 0),
                  runCostUsd: event.cost_usd ?? 0,
                }
              : prev,
          )
          setSessionCostUsd(event.session_total_cost_usd ?? 0)
        },
        onDone: event => {
          setRun(prev =>
            prev && prev.runId === runId
              ? { ...prev, status: event.status, narration: terminalNarration(event.status) ?? prev.narration }
              : prev,
          )
          void finalizeRun(runId, sid)
        },
        onRunError: event => {
          setRun(prev =>
            prev && prev.runId === runId ? { ...prev, status: 'failed', errorMessage: event.message } : prev,
          )
          void finalizeRun(runId, sid)
        },
        onConnectionDrop: () => {
          if (runStatusRef.current !== 'running') return
          getRunSnapshot(runId)
            .then(snap => {
              applyLiveSnapshot(snap)
              if (snap.status !== 'running') {
                subscriptionRef.current?.close()
                void finalizeRun(runId, sid)
              }
            })
            .catch(() => {
              // server unreachable — EventSource keeps retrying
            })
        },
        onReconnected: () => setToast('Reconnected — live updates resumed'),
      })
    },
    [applyLiveSnapshot, finalizeRun, loadSvgArtefact],
  )

  const beginLiveRun = useCallback(
    (runId: string, sid: string, prompt: string) => {
      elapsedBaseRef.current = { baseMs: 0, wallStart: Date.now() }
      setElapsedMs(0)
      setActiveTab('drawing')
      setRun({
        runId,
        prompt,
        status: 'running',
        steps: initialSteps(),
        narration: '',
        warnings: [],
        clarificationQuestion: null,
        svgMarkup: null,
        dxfUrl: null,
        runTokens: 0,
        runCostUsd: 0,
        errorMessage: null,
      })
      setTurns(prev => [
        {
          run_id: runId,
          session_id: sid,
          prompt,
          status: 'running',
          verdict: null,
          params_summary: null,
          cost_usd: null,
          started_at: new Date().toISOString(),
          duration_ms: null,
        },
        ...prev,
      ])
      openStream(runId, sid)
    },
    [openStream],
  )

  const submitPrompt = useCallback(
    async (rawPrompt: string) => {
      const prompt = rawPrompt.trim()
      if (!prompt) {
        setFormError('Type a design request first — the placeholder shows a complete example.')
        return
      }
      if (submitting || runStatusRef.current === 'running') return
      setSubmitting(true)
      setFormError(null)
      try {
        let sid = sessionId
        if (!sid) {
          sid = (await createSession()).session_id
          persistSession(sid)
        }
        let response
        try {
          response = await submitDesign(sid, prompt)
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) {
            // Stored session no longer exists (fresh database) — start a new one.
            sid = (await createSession()).session_id
            persistSession(sid)
            setTurns([])
            setTurnDetails({})
            setSessionCostUsd(0)
            response = await submitDesign(sid, prompt)
          } else {
            throw error
          }
        }
        setPromptValue('')
        beginLiveRun(response.run_id, sid, prompt)
      } catch (error) {
        if (error instanceof ApiError) {
          if (error.code === 'RUN_ACTIVE') {
            setFormError('A run is already in progress in this session — wait for it to finish.')
          } else if (error.code === 'EMPTY_PROMPT') {
            setFormError('Type a design request first — the placeholder shows a complete example.')
          } else {
            setFormError(error.message)
          }
        } else {
          setFormError('Something went wrong submitting the request — try again.')
        }
      } finally {
        setSubmitting(false)
      }
    },
    [beginLiveRun, persistSession, sessionId, submitting],
  )

  const loadPastRun = useCallback(
    async (runId: string) => {
      if (runStatusRef.current === 'running') return
      try {
        const snap = await getRunSnapshot(runId)
        storeTurnDetail(snap)
        setRun(viewFromSnapshot(snap))
        setElapsedMs(snap.duration_ms ?? 0)
        setActiveTab('drawing')
        const svgArt = snap.artefacts?.find(a => a.kind === 'ga_svg')
        if (svgArt) loadSvgArtefact(runId, svgArt.url)
      } catch {
        setToast('Could not load that run — try again')
      }
    },
    [loadSvgArtefact, storeTurnDetail],
  )

  // Reload / SSE-drop rehydration: restore the stored session, its turn
  // history, and — if a run is still live — re-subscribe to its stream.
  useEffect(() => {
    let cancelled = false
    async function rehydrate() {
      let sid: string | null = null
      try {
        sid = localStorage.getItem(SESSION_STORAGE_KEY)
      } catch {
        sid = null
      }
      if (!sid) {
        setBooting(false)
        return
      }
      try {
        const listing = await listDesigns(sid)
        if (cancelled) return
        setSessionId(sid)
        setTurns(listing.runs)
        setSessionCostUsd(listing.runs.reduce((sum, r) => sum + (r.cost_usd ?? 0), 0))
        const latest = listing.runs[0]
        if (latest) {
          const snap = await getRunSnapshot(latest.run_id)
          if (cancelled) return
          storeTurnDetail(snap)
          setRun(viewFromSnapshot(snap))
          const svgArt = snap.artefacts?.find(a => a.kind === 'ga_svg')
          if (svgArt) loadSvgArtefact(snap.run_id, svgArt.url)
          if (snap.status === 'running') {
            const startedMs = snap.started_at ? Date.now() - Date.parse(snap.started_at) : 0
            elapsedBaseRef.current = { baseMs: Math.max(startedMs, 0), wallStart: Date.now() }
            openStream(snap.run_id, sid)
          } else {
            setElapsedMs(snap.duration_ms ?? 0)
          }
        }
      } catch {
        // Stale session (e.g. reset database) — start clean.
        try {
          localStorage.removeItem(SESSION_STORAGE_KEY)
        } catch {
          // ignore
        }
      } finally {
        if (!cancelled) setBooting(false)
      }
    }
    void rehydrate()
    return () => {
      cancelled = true
      subscriptionRef.current?.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Live elapsed-time ticker; freezes when the run leaves `running`.
  useEffect(() => {
    if (!isRunning) return
    const id = setInterval(() => {
      const base = elapsedBaseRef.current
      setElapsedMs(base.baseMs + (Date.now() - base.wallStart))
    }, 500)
    return () => clearInterval(id)
  }, [isRunning, run?.runId])

  useEffect(() => {
    if (!toast) return
    const id = setTimeout(() => setToast(null), 4000)
    return () => clearTimeout(id)
  }, [toast])

  const latestTurn = turns[0] ?? null
  const runIsLatest = !latestTurn || run?.runId === latestTurn.run_id

  const pendingQuestion = (() => {
    if (run?.status === 'needs_input' && run.clarificationQuestion && runIsLatest) return run.clarificationQuestion
    if (latestTurn?.status === 'needs_input') return turnDetails[latestTurn.run_id]?.clarificationQuestion ?? null
    return null
  })()

  const promptMode: PromptMode = pendingQuestion
    ? 'answer'
    : run?.status === 'completed' || turns.some(t => t.status === 'completed')
      ? 'refine'
      : 'design'

  const promptDisabled = submitting || isRunning
  const showHero = !booting && turns.length === 0 && !run

  const handleTryAgain = () => {
    if (run) setPromptValue(run.prompt)
    document.getElementById('prompt-input')?.focus()
  }

  return (
    <div className="flex h-screen flex-col bg-slate-100 text-slate-900">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700 bg-slate-900 px-6 py-3.5">
        <h1 className="text-xl font-bold tracking-tight text-white">IR Box Culvert Design &amp; Proof-Check Agent</h1>
        <TokenCostBadge
          runTokens={run?.runTokens ?? 0}
          runCostUsd={run?.runCostUsd ?? 0}
          sessionCostUsd={sessionCostUsd}
        />
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[24rem_minmax(0,1fr)]">
        <aside className="flex min-h-0 flex-col border-r border-slate-200 bg-slate-50" aria-label="Session panel">
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Session</h2>
            <TurnHistory
              turns={turns}
              details={turnDetails}
              selectedRunId={run?.runId ?? null}
              onSelect={runId => void loadPastRun(runId)}
              selectionDisabled={isRunning}
            />
          </div>
          <div className="space-y-3 border-t border-slate-200 bg-white p-4">
            <PromptPanel
              value={promptValue}
              onChange={value => {
                setPromptValue(value)
                if (formError) setFormError(null)
              }}
              onSubmit={() => void submitPrompt(promptValue)}
              mode={promptMode}
              disabled={promptDisabled}
              disabledReason={isRunning ? 'A design run is in progress — the prompt re-opens when it finishes.' : null}
              formError={formError}
              clarificationQuestion={pendingQuestion}
            />
            <SuggestionChips />
          </div>
        </aside>

        <main className="flex min-h-0 flex-col gap-4 overflow-y-auto p-5">
          {run?.status === 'failed' && (
            <div
              data-testid="error-banner"
              role="alert"
              className="rounded-xl border border-red-300 bg-red-50 px-5 py-4"
            >
              <p className="text-lg font-semibold text-red-800">The run failed</p>
              <p className="mt-1 text-base leading-relaxed text-red-900">
                {run.errorMessage ?? 'The agent stopped before completing the design.'}
              </p>
              <button
                type="button"
                onClick={handleTryAgain}
                className="mt-3 rounded-lg bg-red-700 px-4 py-2 text-base font-semibold text-white hover:bg-red-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-700"
              >
                Try again
              </button>
            </div>
          )}

          {showHero ? (
            <section className="mx-auto flex max-w-2xl flex-1 flex-col items-center justify-center gap-6 text-center">
              <h2 className="text-3xl font-bold leading-tight text-slate-900">
                Design a single-cell RCC box culvert from one sentence
              </h2>
              <p className="text-lg leading-relaxed text-slate-700">
                Describe the crossing — clear span, height, cushion, gauge, loading standard — and watch the agent
                plan, extract the parameters, size the barrel to IRS practice and draft a dimensioned GA drawing you
                can download as genuine DXF.
              </p>
              <button
                type="button"
                data-testid="hero-starter"
                onClick={() => void submitPrompt(CANONICAL_PROMPT)}
                disabled={submitting}
                className="w-full max-w-xl rounded-xl border border-indigo-200 bg-white px-6 py-5 text-left shadow-sm transition-colors hover:border-indigo-400 hover:bg-indigo-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-600 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <span className="block text-sm font-semibold uppercase tracking-wide text-indigo-600">
                  Run the canonical example
                </span>
                <span className="mt-2 block font-mono text-base leading-relaxed text-slate-800">
                  {CANONICAL_PROMPT}
                </span>
              </button>
              <p className="text-base text-slate-500">
                Full EUDL + CDA load checks and the proof-check memo arrive in Phase 2; the 3D model and library in
                Phase 3.
              </p>
            </section>
          ) : (
            <>
              <section
                aria-label="Run progress"
                className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
              >
                {booting ? (
                  <p className="text-lg text-slate-500">Restoring session…</p>
                ) : (
                  <>
                    <StepTracker
                      steps={run?.steps ?? initialSteps()}
                      runId={run?.runId ?? null}
                      elapsedMs={elapsedMs}
                      isRunning={isRunning}
                    />
                    <StatusLine text={run?.narration ?? ''} warnings={run?.warnings ?? []} />
                  </>
                )}
              </section>

              <section className="flex min-h-[28rem] flex-1 flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <ArtefactTabs
                  activeTab={activeTab}
                  onTabChange={setActiveTab}
                  svgMarkup={run?.svgMarkup ?? null}
                  dxfUrl={run?.dxfUrl ?? null}
                  isRunning={isRunning}
                  drawActive={run?.steps.Draw.status === 'active'}
                  runFailed={run?.status === 'failed'}
                  hasRun={!!run}
                />
              </section>
            </>
          )}
        </main>
      </div>

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 right-6 rounded-lg bg-slate-900 px-4 py-2.5 text-base text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  )
}
