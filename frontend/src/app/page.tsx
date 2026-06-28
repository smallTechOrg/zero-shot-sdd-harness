'use client'

import { useCallback, useRef, useState } from 'react'
import {
  ApiError,
  createRun,
  streamRun,
  type ChartSpec,
  type Dataset,
} from '@/lib/api'
import UploadPanel from '@/components/UploadPanel'
import QuestionBox from '@/components/QuestionBox'
import StepStream, { type FeedItem } from '@/components/StepStream'
import AnswerCard, { FailureCard } from '@/components/AnswerCard'
import ChartView from '@/components/ChartView'
import TableView from '@/components/TableView'
import CodeAccordion from '@/components/CodeAccordion'
import LibraryStub from '@/components/LibraryStub'
import HistoryStub from '@/components/HistoryStub'
import FollowUpsStub from '@/components/FollowUpsStub'
import CostStub from '@/components/CostStub'

interface FinalResult {
  answer: string
  chartSpec: ChartSpec | null
  table: Record<string, unknown>[]
  code: string
}

interface FailureResult {
  attempts: number
  error: string
}

let feedSeq = 0
const nextId = () => `feed-${feedSeq++}`

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [streaming, setStreaming] = useState(false)
  const [feed, setFeed] = useState<FeedItem[]>([])
  const [result, setResult] = useState<FinalResult | null>(null)
  const [failure, setFailure] = useState<FailureResult | null>(null)
  const [topError, setTopError] = useState<string | null>(null)

  // Tracks the number of attempts seen, to label the failure card if the
  // `error` event's message doesn't carry an attempt count.
  const attemptsRef = useRef(1)
  const closeRef = useRef<(() => void) | null>(null)

  const handleUploaded = useCallback((ds: Dataset) => {
    // A fresh dataset resets the analysis surface.
    closeRef.current?.()
    setDataset(ds)
    setFeed([])
    setResult(null)
    setFailure(null)
    setTopError(null)
    setStreaming(false)
  }, [])

  const handleAsk = useCallback(
    async (question: string) => {
      if (!dataset) return
      // Reset run state.
      closeRef.current?.()
      setFeed([])
      setResult(null)
      setFailure(null)
      setTopError(null)
      attemptsRef.current = 1
      setStreaming(true)

      let run
      try {
        run = await createRun(dataset.dataset_id, question)
      } catch (err) {
        setStreaming(false)
        setTopError(err instanceof ApiError ? err.message : 'Failed to start the run.')
        return
      }

      closeRef.current = streamRun(run.run_id, {
        onPlan: (e) => {
          setFeed((f) => [...f, { kind: 'plan', id: nextId(), plan: e.plan }])
        },
        onStep: (e) => {
          attemptsRef.current = Math.max(attemptsRef.current, e.attempt)
          setFeed((f) => [
            ...f,
            { kind: 'step', id: nextId(), phase: e.phase, attempt: e.attempt, message: e.message },
          ])
        },
        onRetry: (e) => {
          attemptsRef.current = Math.max(attemptsRef.current, e.attempt)
          setFeed((f) => [...f, { kind: 'retry', id: nextId(), attempt: e.attempt, error: e.error }])
        },
        onFinal: (e) => {
          setFeed((f) => [...f, { kind: 'final', id: nextId() }])
          setResult({
            answer: e.answer,
            chartSpec: e.chart_spec ?? null,
            table: e.table ?? [],
            code: e.code,
          })
          setStreaming(false)
        },
        onError: (e) => {
          setFeed((f) => [...f, { kind: 'error', id: nextId(), error: e.error }])
          setFailure({ attempts: attemptsRef.current, error: e.error })
          setStreaming(false)
        },
        onConnectionError: (message) => {
          setFeed((f) => [...f, { kind: 'connection', id: nextId(), message }])
          setTopError(message)
          setStreaming(false)
        },
      })
    },
    [dataset],
  )

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-gray-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-lg font-bold tracking-tight text-gray-900">Local CSV Analyst</h1>
            <p className="text-xs text-gray-500">
              Your data never leaves this machine — only schema &amp; samples reach the model.
            </p>
          </div>
          <CostStub />
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-[16rem_1fr]">
          {/* Left sidebar — stubs only */}
          <aside className="space-y-4">
            <LibraryStub />
            <HistoryStub />
          </aside>

          {/* Main column */}
          <div className="space-y-6">
            <UploadPanel dataset={dataset} onUploaded={handleUploaded} disabled={streaming} />

            <QuestionBox enabled={!!dataset} streaming={streaming} onAsk={handleAsk} />

            {topError && (
              <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {topError}
              </div>
            )}

            <StepStream items={feed} streaming={streaming} />

            {failure && <FailureCard attempts={failure.attempts} error={failure.error} />}

            {result && (
              <>
                <AnswerCard answer={result.answer} />
                <ChartView chartSpec={result.chartSpec} />
                <TableView table={result.table} />
                <CodeAccordion code={result.code} />
              </>
            )}

            {/* Empty state for the analysis surface */}
            {!streaming && !result && !failure && feed.length === 0 && (
              <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50/60 p-8 text-center">
                <p className="text-sm text-gray-500">
                  {dataset
                    ? 'Ask a question above to see the agent plan, write & run pandas, and answer.'
                    : 'Upload a CSV to get started.'}
                </p>
              </div>
            )}

            <FollowUpsStub />
          </div>
        </div>
      </main>
    </div>
  )
}
