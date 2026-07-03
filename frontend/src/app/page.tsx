'use client'

import { useState } from 'react'
import { askQuestion, ApiError } from './lib/api'
import type { Dataset, RunResult } from './lib/types'
import UploadBox from './components/UploadBox'
import ProfileCard from './components/ProfileCard'
import ChatInput from './components/ChatInput'
import AnswerBlock from './components/AnswerBlock'
import {
  LibrarySidebar,
  HistoryPanel,
  CostMeter,
  ProgressSteps,
  DatasetSelector,
} from './components/stubs'

interface Turn {
  question: string
  run: RunResult | null
  error: string | null
}

export default function Home() {
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [turns, setTurns] = useState<Turn[]>([])
  const [running, setRunning] = useState(false)

  async function handleAsk(question: string) {
    setRunning(true)
    const idx = turns.length
    setTurns(prev => [...prev, { question, run: null, error: null }])
    try {
      const run = await askQuestion(dataset!.id, question)
      setTurns(prev => prev.map((t, i) => (i === idx ? { ...t, run } : t)))
    } catch (e) {
      const msg =
        e instanceof ApiError ? e.message : 'Network error — is the server running?'
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
        {/* Left sidebar — Phase-1 stubs */}
        <aside className="hidden space-y-4 lg:block">
          <LibrarySidebar />
          <HistoryPanel />
          <CostMeter />
          <ProgressSteps />
        </aside>

        {/* Main column */}
        <main className="space-y-6">
          {!dataset ? (
            <EmptyState onLoaded={setDataset} />
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
                      <AnswerBlock run={turn.run} />
                    ) : turn.error ? (
                      <div
                        role="alert"
                        data-testid="turn-error"
                        className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700"
                      >
                        {turn.error}
                      </div>
                    ) : (
                      <Analyzing />
                    )}
                  </div>
                ))}
              </section>

              <div className="sticky bottom-0 bg-gradient-to-t from-gray-50 via-gray-50 pt-4">
                <ChatInput onAsk={handleAsk} disabled={running} running={running} />
                <p className="mt-2 text-center text-xs text-gray-400">
                  Phase 1 shows a single spinner — live step-by-step progress arrives in Phase 2.
                </p>
              </div>
            </>
          )}
        </main>
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
