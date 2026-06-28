'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import {
  askStream,
  fetchUsageToday,
  type AnswerPayload,
  type Dataset,
  type StepEvent,
  type UsageToday,
} from '@/lib/api'
import UploadZone from '@/components/UploadZone'
import ProfilePanel from '@/components/ProfilePanel'
import StepViewer from '@/components/StepViewer'
import AnswerCard from '@/components/AnswerCard'
import QuestionInput from '@/components/QuestionInput'
import CostMeter from '@/components/CostMeter'
import HistoryDrawer from '@/components/HistoryDrawer'
import LibrarySidebar from '@/components/LibrarySidebar'

interface Turn {
  id: number
  question: string
  steps: StepEvent[]
  maxSteps: number | null
  answer: AnswerPayload | null
  error: string | null
  running: boolean
}

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [running, setRunning] = useState(false)
  const [pendingQuestion, setPendingQuestion] = useState('')
  const [usage, setUsage] = useState<UsageToday | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyKey, setHistoryKey] = useState(0)
  const turnSeq = useRef(0)
  const threadEnd = useRef<HTMLDivElement>(null)

  const refreshUsage = useCallback(() => {
    fetchUsageToday()
      .then(setUsage)
      .catch(() => {
        /* meter is best-effort */
      })
  }, [])

  useEffect(() => {
    refreshUsage()
  }, [refreshUsage])

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  function patchTurn(id: number, patch: Partial<Turn>) {
    setTurns(prev => prev.map(t => (t.id === id ? { ...t, ...patch } : t)))
  }

  function appendStep(id: number, step: StepEvent) {
    setTurns(prev =>
      prev.map(t => (t.id === id ? { ...t, steps: [...t.steps, step] } : t)),
    )
  }

  async function ask(question: string) {
    if (!dataset || running) return
    const id = ++turnSeq.current
    const turn: Turn = {
      id,
      question,
      steps: [],
      maxSteps: null,
      answer: null,
      error: null,
      running: true,
    }
    setTurns(prev => [...prev, turn])
    setRunning(true)
    setPendingQuestion('')

    await askStream(dataset.dataset_id, question, {
      onRunStarted: e => patchTurn(id, { maxSteps: e.max_steps }),
      onStep: e => appendStep(id, e),
      onAnswer: e => patchTurn(id, { answer: e }),
      onError: msg => patchTurn(id, { error: msg }),
    })

    patchTurn(id, { running: false })
    setRunning(false)
    refreshUsage()
    setHistoryKey(k => k + 1)
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
              ⌗
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-900">Data Analysis Agent</h1>
              <p className="text-[11px] text-slate-400">
                Ask your data anything · code runs locally, raw rows never leave your machine
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {dataset && (
              <button
                onClick={() => setHistoryOpen(true)}
                data-testid="open-history"
                className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 shadow-sm hover:bg-slate-50"
              >
                History
              </button>
            )}
            <CostMeter usage={usage} />
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl gap-6 px-6 py-6">
        <LibrarySidebar />

        <div className="min-w-0 flex-1 space-y-6">
          {!dataset ? (
            <div className="mx-auto max-w-2xl pt-10">
              <h2 className="mb-1 text-center text-xl font-semibold text-slate-800">
                Upload a dataset to begin
              </h2>
              <p className="mb-6 text-center text-sm text-slate-500">
                Drop a CSV or Excel file. We profile it instantly, then you can ask questions in
                plain language.
              </p>
              <UploadZone onUploaded={setDataset} />
            </div>
          ) : (
            <>
              <div className="flex items-start gap-3">
                <div className="flex-1">
                  <ProfilePanel dataset={dataset} />
                </div>
                <MultiFileStub />
              </div>

              {/* Chat thread */}
              <div className="space-y-6">
                {turns.length === 0 && (
                  <div
                    data-testid="empty-thread"
                    className="rounded-2xl border border-dashed border-slate-200 bg-white px-6 py-10 text-center"
                  >
                    <p className="text-sm font-medium text-slate-600">
                      Ask your first question
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      e.g. “What were total sales by region?” — watch the agent plan, write code,
                      run it, and answer.
                    </p>
                  </div>
                )}

                {turns.map(turn => (
                  <div key={turn.id} className="space-y-3" data-testid="turn">
                    <div className="flex justify-end">
                      <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5 text-sm text-white">
                        {turn.question}
                      </div>
                    </div>

                    <StepViewer
                      steps={turn.steps}
                      maxSteps={turn.maxSteps}
                      running={turn.running}
                    />

                    {turn.error && (
                      <div
                        data-testid="ask-error"
                        className="rounded-2xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"
                      >
                        <p className="font-semibold">Run failed</p>
                        <p className="mt-1">{turn.error}</p>
                        <p className="mt-1 text-xs text-red-500">
                          The partial run was still saved to history.
                        </p>
                      </div>
                    )}

                    {turn.answer && (
                      <AnswerCard answer={turn.answer} onFollowUp={setPendingQuestion} />
                    )}
                  </div>
                ))}
                <div ref={threadEnd} />
              </div>

              {/* Sticky input */}
              <div className="sticky bottom-0 -mx-6 border-t border-slate-200 bg-slate-50/95 px-6 py-4 backdrop-blur">
                <QuestionInput disabled={running} pending={pendingQuestion} onAsk={ask} />
                <p className="mt-2 text-center text-[11px] text-slate-400">
                  Follow-ups keep context from earlier in this session.
                </p>
              </div>
            </>
          )}
        </div>
      </main>

      {dataset && (
        <HistoryDrawer
          datasetId={dataset.dataset_id}
          open={historyOpen}
          onClose={() => setHistoryOpen(false)}
          refreshKey={historyKey}
        />
      )}
    </div>
  )
}

// NON-FUNCTIONAL Phase 1 stub — clearly labelled "Coming in Phase 3".
function MultiFileStub() {
  return (
    <div className="group relative">
      <button
        data-testid="multifile-stub"
        disabled
        aria-disabled="true"
        className="cursor-not-allowed rounded-xl border border-slate-200 bg-white px-4 py-3 text-xs font-medium text-slate-400 opacity-60"
      >
        + Add another file / Join files
      </button>
      <span
        data-testid="phase3-badge"
        className="absolute -top-2 right-2 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500"
      >
        Coming in Phase 3
      </span>
      <div className="pointer-events-none absolute right-0 top-full z-10 mt-1 w-48 rounded-lg bg-slate-800 px-3 py-2 text-[11px] text-white opacity-0 shadow-lg transition group-hover:opacity-100">
        Multi-file joins — coming in Phase 3
      </div>
    </div>
  )
}
